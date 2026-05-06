# Quanvest Backend

High-performance financial analysis API powering the [Quanvest](https://quanvest.me) platform. Built with **FastAPI**, backed by **PostgreSQL** and **MongoDB**, with AI-powered copilot features driven by **Google Gemini** and **LangChain**.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Getting Started](#getting-started)
  - [Running with Docker](#running-with-docker)
  - [Running Locally](#running-locally)
- [API Overview](#api-overview)
- [Authentication](#authentication)
- [Project Structure](#project-structure)
- [Architecture](#architecture)

---

## Features

- Real-time and historical **stock data**, **financial statements**, and **ratios**
- **AI Copilot** endpoint powered by Google Gemini for natural-language financial analysis
- **RAG (Retrieval-Augmented Generation)** over structured SQL tables (P&L, balance sheet, cashflow, dividends, stock prices, shareholding)
- **Vector search** using FAISS over annual reports and earnings-call transcripts
- Corporate governance data: board composition, committee composition, board meetings, RPT, insider trading, pledged shares
- API-key-secured endpoints with CORS configured for the Quanvest frontend

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115 + Uvicorn (uvloop) |
| Relational DB | PostgreSQL (psycopg2) |
| Document DB | MongoDB (pymongo) |
| Vector store | FAISS + sentence-transformers |
| AI / LLM | Google Gemini (`langchain-google-genai`, `google-genai`) |
| Orchestration | LangChain |
| Containerisation | Docker (Python 3.12) |
| Testing | pytest |

---

## Prerequisites

- Python 3.12+  **or** Docker
- A running **PostgreSQL** instance
- A running **MongoDB** instance
- A **Google Gemini API key**

---

## Environment Variables

Create a `.env` file in the project root (next to `requirements.txt`):

```dotenv
# PostgreSQL
POSTGRES_URL=postgresql://user:password@host:5432/dbname

# MongoDB
MONGO_URI=mongodb://localhost:27017/
DB_NAME=financial_documents
COLLECTION_NAME=classified_texts

# API security
API_ACCESS_KEY=your_secret_api_key_here

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## Getting Started

### Running with Docker

```bash
docker build -t quanvest-backend .
docker run --env-file .env -p 8000:8000 quanvest-backend
```

The API will be available at `http://localhost:8000`.

### Running Locally

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Start the server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Overview

All endpoints (except `/` and `/public_info`) require the `X-API-Key` header.

| Prefix | Description |
|---|---|
| `/home` | Home / summary data |
| `/stock_data` | OHLCV price data |
| `/financials` | Profit & Loss, Balance Sheet, Cash Flow |
| `/ratios` | Financial ratios |
| `/overview` | Company overview |
| `/charts` | Chart-ready data series |
| `/copilot` | AI copilot (natural language Q&A) |
| `/rag_flask` | SQL-context retrieval for RAG pipelines |
| `/search` | Company / ticker search |
| `/dividend` | Dividend history |
| `/shareholding_pattern` | Promoter & public shareholding |
| `/annual_files` | Annual report documents |
| `/quarterly_files` | Quarterly report documents |
| `/earning_calls` | Earnings-call transcripts |
| `/insider_trading` | Insider trading disclosures |
| `/pledged_data` | Pledged shares data |
| `/cg_board_composition` | Board composition |
| `/cg_committee_composition` | Committee composition |
| `/cg_board_meetings` | Board meeting records |
| `/cg_committee_meetings` | Committee meeting records |
| `/rpt` | Related-party transactions |

### Interactive Docs

Swagger UI and ReDoc are available at `/docs` and `/redoc` respectively. Both require the `X-API-Key` query parameter or header.

---

## Authentication

Every protected route reads the `X-API-Key` HTTP header and compares it against the `API_ACCESS_KEY` environment variable. Requests with a missing or invalid key receive `HTTP 401 Unauthorized`.

---

## Project Structure

```
quanvest_backend/
├── backend/
│   ├── main.py                      # FastAPI app, middleware, router registration
│   ├── db_setup.py                  # PostgreSQL connection helper
│   ├── db_mongo.py                  # MongoDB connection and helpers
│   ├── geminiapi.py                 # Gemini API wrappers (classify, summarise)
│   ├── make_vector_db_from_documents.py  # FAISS index builder
│   ├── ratio_creator.py             # Financial ratio calculation utilities
│   ├── ddl.py                       # Database schema / DDL helpers
│   ├── routers/                     # FastAPI routers (one per domain)
│   │   ├── home.py
│   │   ├── stock_data.py
│   │   ├── financials.py
│   │   ├── ratios.py
│   │   ├── overview.py
│   │   ├── charts.py
│   │   ├── copilot.py
│   │   ├── sql_rag.py
│   │   ├── search.py
│   │   ├── dividend.py
│   │   ├── shareholding_pattern.py
│   │   ├── annual_files.py
│   │   ├── quarterly_files.py
│   │   ├── earning_calls.py
│   │   ├── insider_trading.py
│   │   ├── pledged_data.py
│   │   ├── cg_board_composition.py
│   │   ├── cg_committee_composition.py
│   │   ├── cg_board_meetings.py
│   │   ├── cg_committee_meetings.py
│   │   └── rpt.py
│   ├── services/                    # Business logic layer
│   │   ├── security.py              # API-key authentication dependency
│   │   ├── financial_service.py
│   │   ├── stock_data_service.py
│   │   ├── chart_service.py
│   │   ├── copilot_service.py
│   │   └── ...                      # One service file per router
│   ├── tools/
│   │   └── query_intent_analyzer.py # LLM query intent classification
│   ├── faiss_annual/                # FAISS index — annual reports
│   └── faiss_earnings_quarters/     # FAISS index — earnings-call transcripts
├── Dockerfile
└── requirements.txt
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed breakdown of the system design.
