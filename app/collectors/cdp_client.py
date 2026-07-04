"""
Chrome DevTools Protocol (CDP) client.

Connects to a Chrome/Chromium browser via the CDP WebSocket endpoint,
enables the Network and Page domains, and provides helpers for listening
to network events and retrieving response bodies.

No Facebook-specific logic lives here. This is a generic CDP client.
"""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any, Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from app.core.logger import logger

# How long (seconds) to wait for the browser to become responsive.
CONNECT_TIMEOUT = 30.0
# How long (seconds) between automatic reconnect attempts.
RECONNECT_DELAY = 2.0
# Maximum number of reconnect attempts before giving up.
MAX_RECONNECT_ATTEMPTS = 5


class CDPError(Exception):
    """Raised on any CDP protocol error."""


class CDPTimeoutError(CDPError):
    """Raised when a CDP command does not receive a response in time."""


class CDPClient:
    """
    Async Chrome DevTools Protocol client.

    Connects to the browser WebSocket endpoint returned by AdsPower
    and manages:
      - Sending CDP commands
      - Receiving CDP events
      - Automatic reconnection on disconnect
      - Dispatching named event callbacks

    Usage:
        client = CDPClient(ws_url="ws://127.0.0.1:9222/devtools/browser/...")
        await client.connect()
        await client.enable_network()
        client.on("Network.responseReceived", my_handler)
        await client.wait_until_ready()
        ...
        await client.disconnect()
    """

    def __init__(
        self,
        ws_url: str,
        connect_timeout: float = CONNECT_TIMEOUT,
        reconnect_delay: float = RECONNECT_DELAY,
        max_reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS,
        prefer_url_fragment: Optional[str] = None,
    ) -> None:
        self._ws_url = ws_url
        self._connect_timeout = connect_timeout
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_attempts = max_reconnect_attempts
        self._prefer_url_fragment = prefer_url_fragment

        self._ws: Optional[Any] = None
        self._cmd_id: int = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._listeners: dict[str, list[Callable]] = {}
        self._recv_task: Optional[asyncio.Task] = None
        self._connected: bool = False
        self._target_id: Optional[str] = None
        self._session_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Open the CDP WebSocket connection and start the background
        receive loop.

        On the browser-level WebSocket we first discover available
        targets (pages), attach to the first page target, and obtain
        a session ID for subsequent commands.
        """
        logger.info("Connecting to CDP WebSocket...")
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(  # type: ignore[attr-defined]
                    self._ws_url,
                    max_size=50 * 1024 * 1024,  # 50 MB — large GraphQL payloads
                    ping_interval=20,
                    ping_timeout=20,
                ),
                timeout=self._connect_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise CDPTimeoutError(
                f"Timed out connecting to CDP after {self._connect_timeout}s: {self._ws_url}"
            ) from exc
        except (WebSocketException, OSError) as exc:
            raise CDPError(f"Failed to connect to CDP WebSocket: {exc}") from exc

        self._connected = True
        self._recv_task = asyncio.create_task(self._receive_loop())
        logger.info("CDP WebSocket connected.")

        # Discover page targets and open a session on the first page.
        await self._attach_to_page(self._prefer_url_fragment)

    async def _attach_to_page(self, prefer_url_fragment: Optional[str] = None) -> None:
        """
        Enumerate browser targets and attach to the best available page.
        Prefers a tab whose URL contains prefer_url_fragment if provided,
        falls back to the first page target.
        """
        targets_resp = await self._send_browser("Target.getTargets", {})
        target_infos = targets_resp.get("targetInfos", [])

        page_targets = [t for t in target_infos if t.get("type") == "page"]
        if not page_targets:
            raise CDPError("No page targets found in the browser. Is a tab open?")

        # Prefer a tab already showing Ads Manager
        chosen = None
        if prefer_url_fragment:
            for t in page_targets:
                if prefer_url_fragment in t.get("url", ""):
                    chosen = t
                    logger.info(
                        f"Found preferred tab: {t.get('url', '')[:80]}"
                    )
                    break

        if chosen is None:
            chosen = page_targets[0]

        self._target_id = chosen["targetId"]
        logger.info(f"Attaching to page target: {self._target_id}")

        attach_resp = await self._send_browser(
            "Target.attachToTarget",
            {"targetId": self._target_id, "flatten": True},
        )
        self._session_id = attach_resp.get("sessionId")
        if not self._session_id:
            raise CDPError("Failed to obtain a CDP session ID.")

        logger.info(f"CDP session established: {self._session_id}")

    async def disconnect(self) -> None:
        """
        Cleanly close the WebSocket and cancel the background receive task.
        """
        logger.info("Disconnecting from CDP...")
        self._connected = False

        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        logger.info("CDP disconnected.")

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._cmd_id += 1
        return self._cmd_id

    async def _send_raw(self, message: dict) -> dict:
        """
        Send a raw CDP message and await its response.
        All commands share a single WebSocket connection — responses
        are matched to callers by the 'id' field.
        """
        cmd_id = message["id"]
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = future

        try:
            await self._ws.send(json.dumps(message))
        except (ConnectionClosed, WebSocketException) as exc:
            del self._pending[cmd_id]
            raise CDPError(f"WebSocket send failed: {exc}") from exc

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError as exc:
            self._pending.pop(cmd_id, None)
            raise CDPTimeoutError(
                f"CDP command '{message.get('method')}' timed out."
            ) from exc

    async def _send_browser(self, method: str, params: dict) -> dict:
        """Send a command at the browser level (no sessionId)."""
        msg = {"id": self._next_id(), "method": method, "params": params}
        result = await self._send_raw(msg)
        return result.get("result", {})

    async def _send(self, method: str, params: dict) -> dict:
        """Send a command scoped to the current page session."""
        if not self._session_id:
            raise CDPError("Not attached to a page session. Call connect() first.")
        msg = {
            "id": self._next_id(),
            "method": method,
            "params": params,
            "sessionId": self._session_id,
        }
        result = await self._send_raw(msg)
        return result.get("result", {})

    # ------------------------------------------------------------------
    # Receive loop
    # ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """
        Background task that reads all incoming CDP messages.
        Routes responses to waiting futures and events to registered handlers.
        """
        reconnect_attempts = 0

        while self._connected:
            try:
                raw = await self._ws.recv()
                message = json.loads(raw)
                await self._dispatch(message)
                reconnect_attempts = 0  # Reset on successful receive

            except ConnectionClosed:
                if not self._connected:
                    break
                logger.warning("CDP WebSocket connection lost. Attempting reconnect...")
                reconnected = await self._reconnect(reconnect_attempts)
                if not reconnected:
                    logger.error("CDP reconnect failed. Stopping receive loop.")
                    self._connected = False
                    break
                reconnect_attempts += 1

            except json.JSONDecodeError as exc:
                logger.warning(f"CDP received invalid JSON: {exc}")

            except asyncio.CancelledError:
                break

            except Exception as exc:
                logger.error(f"Unexpected error in CDP receive loop: {exc}")

    async def _reconnect(self, attempt: int) -> bool:
        """Attempt to re-establish the WebSocket connection."""
        if attempt >= self._max_reconnect_attempts:
            return False

        await asyncio.sleep(self._reconnect_delay)
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(  # type: ignore[attr-defined]
                    self._ws_url,
                    max_size=50 * 1024 * 1024,
                    ping_interval=20,
                    ping_timeout=20,
                ),
                timeout=self._connect_timeout,
            )
            await self._attach_to_page()
            logger.info("CDP reconnected successfully.")
            return True
        except Exception as exc:
            logger.warning(f"CDP reconnect attempt {attempt + 1} failed: {exc}")
            return False

    async def _dispatch(self, message: dict) -> None:
        """Route an incoming CDP message to the correct recipient."""
        # It's a response to a pending command
        if "id" in message:
            cmd_id = message["id"]
            future = self._pending.pop(cmd_id, None)
            if future and not future.done():
                if "error" in message:
                    future.set_exception(
                        CDPError(f"CDP error: {message['error']}")
                    )
                else:
                    future.set_result(message)
            return

        # It's a session-wrapped event (flat mode)
        if "method" in message and message.get("method") == "Target.receivedMessageFromTarget":
            inner_raw = message.get("params", {}).get("message", "{}")
            try:
                inner = json.loads(inner_raw)
                await self._dispatch(inner)
            except json.JSONDecodeError:
                pass
            return

        # It's a plain event
        if "method" in message:
            method = message["method"]
            params = message.get("params", {})
            handlers = self._listeners.get(method, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(params))
                    else:
                        handler(params)
                except Exception as exc:
                    logger.warning(f"Event handler for '{method}' raised: {exc}")

    # ------------------------------------------------------------------
    # Domain management
    # ------------------------------------------------------------------

    async def enable_network(self) -> None:
        """Enable the Network domain to start receiving network events."""
        logger.info("Enabling CDP Network domain...")
        await self._send("Network.enable", {})
        logger.info("CDP Network domain enabled.")

    async def enable_page(self) -> None:
        """Enable the Page domain (required for navigation)."""
        logger.info("Enabling CDP Page domain...")
        await self._send("Page.enable", {})
        logger.info("CDP Page domain enabled.")

    async def wait_until_ready(self, timeout: float = 30.0) -> None:
        """
        Wait until the current page finishes loading.
        Uses Page.loadEventFired as the signal.
        """
        logger.info("Waiting for page to be ready (Page.loadEventFired)...")
        load_event = asyncio.Event()

        async def on_load(_params: dict) -> None:
            load_event.set()

        self.on("Page.loadEventFired", on_load)

        try:
            await asyncio.wait_for(load_event.wait(), timeout=timeout)
            logger.info("Page load event fired.")
        except asyncio.TimeoutError:
            logger.warning(
                f"Page did not fire loadEventFired within {timeout}s. Proceeding anyway."
            )
        finally:
            self.off("Page.loadEventFired", on_load)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> None:
        """Navigate the current page to a URL."""
        logger.info(f"Navigating to: {url}")
        await self._send("Page.navigate", {"url": url})

    async def reload(self) -> None:
        """Reload the current page."""
        logger.info("Reloading current page...")
        await self._send("Page.reload", {"ignoreCache": True})

    async def get_current_url(self) -> Optional[str]:
        """Return the current URL of the attached page target."""
        try:
            targets_resp = await self._send_browser("Target.getTargets", {})
            for t in targets_resp.get("targetInfos", []):
                if t.get("targetId") == self._target_id:
                    return t.get("url", "")
        except CDPError:
            pass
        return None

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------

    async def get_response_body(self, request_id: str) -> Optional[str]:
        """
        Retrieve the raw response body for a completed network request.

        Args:
            request_id: The Network.requestId from a responseReceived event.

        Returns:
            Body string (may be base64-encoded for binary responses).
            Returns None if retrieval fails.
        """
        try:
            result = await self._send(
                "Network.getResponseBody", {"requestId": request_id}
            )
            body: str = result.get("body", "")
            is_base64: bool = result.get("base64Encoded", False)
            if is_base64:
                import base64
                body = base64.b64decode(body).decode("utf-8", errors="replace")
            return body
        except (CDPError, CDPTimeoutError) as exc:
            logger.warning(f"Could not retrieve response body for {request_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Event subscription
    # ------------------------------------------------------------------

    def on(self, event: str, handler: Callable) -> None:
        """Register a handler for a CDP event name (e.g. 'Network.responseReceived')."""
        self._listeners.setdefault(event, []).append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """Unregister a previously registered event handler."""
        handlers = self._listeners.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def once(self, event: str, handler: Callable) -> None:
        """Register a handler that fires only once, then auto-removes itself."""
        async def _wrapper(params: dict) -> None:
            self.off(event, _wrapper)
            if asyncio.iscoroutinefunction(handler):
                await handler(params)
            else:
                handler(params)

        self.on(event, _wrapper)
