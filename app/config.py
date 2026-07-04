from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Meta Ads Reporter"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Alert Worker Settings
    BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    ADSPOWER_PROFILE_ID: str = "k1dvlyr0"
    MONITOR_ACCOUNT_IDS: str = "1559140139101704,2489049668183097"
    ALERT_POLL_INTERVAL_SECONDS: int = 300

    @property
    def monitor_accounts(self) -> list[str]:
        return [acc.strip() for acc in self.MONITOR_ACCOUNT_IDS.split(",") if acc.strip()]


settings = Settings()
