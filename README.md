# Meta Ads Reporter

A lightweight, modular backend service that fetches real-time Facebook Ads campaign data from an AdsPower browser session and exposes it through a REST API.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| Backend | FastAPI |
| Server | Uvicorn |
| HTTP Client | httpx |
| Validation | Pydantic v2 |
| Config | Pydantic Settings |
| Env Vars | python-dotenv |
| Logging | Loguru |
| Utilities | Rich, Typer |
| Code Quality | Black, Ruff, isort |
| Testing | pytest, pytest-asyncio |

---

## Folder Structure

```
meta-ads-reporter/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI application entry point
│   ├── config.py         # Pydantic Settings configuration
│   ├── dependencies.py   # Shared FastAPI dependencies
│   ├── routers/          # API route modules
│   ├── services/         # Business logic layer
│   ├── collectors/       # Data collection from AdsPower/Meta
│   ├── models/           # Domain models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── core/
│   │   └── logger.py     # Centralized Loguru logger
│   └── utils/            # Shared utility functions
├── tests/                # pytest test suite
├── .env.example          # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd meta-ads-reporter
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in the values:

```env
APP_NAME=Meta Ads Reporter
APP_ENV=development
HOST=0.0.0.0
PORT=8000
DEBUG=False
```

---

## Run Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- `http://localhost:8000/` — Root endpoint
- `http://localhost:8000/health` — Health check
- `http://localhost:8000/docs` — Swagger UI

---

## Future Roadmap

| Phase | Feature |
|---|---|
| Phase 1 | AdsPower browser session integration |
| Phase 2 | Meta Ads data collection (campaigns, ad sets, ads) |
| Phase 3 | Telegram Bot reporting |
| Phase 4 | Next.js Dashboard |
| Phase 5 | AI-powered reporting |
| Phase 6 | Historical reports & analytics |
