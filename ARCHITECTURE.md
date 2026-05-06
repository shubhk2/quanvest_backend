# Architecture

This document describes the architecture of the Quanvest Backend — a high-performance financial data API built on FastAPI.

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [Layer Breakdown](#2-layer-breakdown)
   - [Entry Point & Application Bootstrap](#21-entry-point--application-bootstrap)
   - [Routers](#22-routers)
   - [Services](#23-services)
   - [Database Layer](#24-database-layer)
   - [AI & Vector Search Layer](#25-ai--vector-search-layer)
   - [Tools](#26-tools)
3. [Request Lifecycle](#3-request-lifecycle)
4. [Data Flow Diagrams](#4-data-flow-diagrams)
   - [Standard API Request](#standard-api-request)
   - [AI Copilot Request](#ai-copilot-request)
   - [FAISS Index Build Pipeline](#faiss-index-build-pipeline)
5. [Domain Modules](#5-domain-modules)
6. [Security Model](#6-security-model)
7. [Concurrency Model](#7-concurrency-model)
8. [Infrastructure & Deployment](#8-infrastructure--deployment)
9. [Environment & Configuration](#9-environment--configuration)

---

## 1. High-Level Overview

```
┌────────────────────────────────────────────────────────────────┐
│                         Clients                                │
│  Quanvest Frontend (Vercel)  │  External RAG services          │
└───────────────┬──────────────┴─────────────────┬──────────────┘
                │  HTTPS / X-API-Key              │
                ▼                                 ▼
┌───────────────────────────────────────────────────────────────┐
│                      FastAPI Application                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Routers    │  │   Services   │  │      Tools         │  │
│  │  (HTTP I/O)  │─▶│ (Business    │  │ (query intent,     │  │
│  │              │  │   logic)     │  │  FAISS search)     │  │
│  └──────────────┘  └──────┬───────┘  └────────────────────┘  │
└─────────────────────────── │ ─────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────────┐
          ▼                  ▼                       ▼
   ┌────────────┐    ┌──────────────┐     ┌──────────────────┐
   │ PostgreSQL │    │   MongoDB    │     │  Google Gemini   │
   │ (relational│    │  (documents  │     │  LLM / LangChain │
   │  financials│    │  & vectors)  │     │                  │
   └────────────┘    └──────────────┘     └──────────────────┘
                                                    │
                                          ┌─────────▼─────────┐
                                          │   FAISS Indexes   │
                                          │  faiss_annual/    │
                                          │  faiss_earnings_  │
                                          │  quarters/        │
                                          └───────────────────┘
```

---

## 2. Layer Breakdown

### 2.1 Entry Point & Application Bootstrap

**File:** `backend/main.py`

- Creates the `FastAPI` application instance with custom lifespan management.
- On startup:
  - Sets the asyncio event loop policy to **uvloop** for higher throughput.
  - Configures a `ThreadPoolExecutor` (50 workers) as the default executor, allowing sync I/O (PostgreSQL, MongoDB) to run without blocking the event loop.
- Registers **CORS** middleware (allowed origins: Quanvest Vercel frontend, `localhost:3000`, `api.quanvest.me`).
- Attaches an HTTP middleware that records `X-Process-Time` on every response and emits a warning log for requests exceeding 5 seconds.
- Protects `/docs`, `/redoc`, and `/openapi.json` with API-key authentication (key may be supplied via query-string for browser access).
- Registers all domain routers with `Depends(get_api_key)` applied globally.

---

### 2.2 Routers

**Directory:** `backend/routers/`

Each file defines a single `APIRouter` that groups HTTP endpoints for one business domain. Routers are thin: they validate the incoming request shape (Pydantic models), call the corresponding service function, and return the response.

| Router file | Prefix | Responsibility |
|---|---|---|
| `home.py` | `/home` | Summary / landing data |
| `stock_data.py` | `/stock_data` | OHLCV & stock price series |
| `financials.py` | `/financials` | P&L, balance sheet, cash flow |
| `ratios.py` | `/ratios` | Computed financial ratios |
| `overview.py` | `/overview` | Company overview & metadata |
| `charts.py` | `/charts` | Chart-ready data aggregations |
| `copilot.py` | `/copilot` | AI-powered Q&A copilot |
| `sql_rag.py` | `/rag_flask` | SQL context retrieval for RAG |
| `search.py` | *(root)* | Ticker / company search |
| `dividend.py` | `/dividend` | Dividend history |
| `shareholding_pattern.py` | `/shareholding_pattern` | Promoter & public holdings |
| `annual_files.py` | `/annual_files` | Annual report documents |
| `quarterly_files.py` | `/quarterly_files` | Quarterly report documents |
| `earning_calls.py` | `/earning_calls` | Earnings-call transcripts |
| `insider_trading.py` | `/insider_trading` | Insider trade disclosures |
| `pledged_data.py` | `/pledged_data` | Pledged share data |
| `cg_board_composition.py` | `/cg_board_composition` | Board composition |
| `cg_committee_composition.py` | `/cg_committee_composition` | Committee composition |
| `cg_board_meetings.py` | `/cg_board_meetings` | Board meeting records |
| `cg_committee_meetings.py` | `/cg_committee_meetings` | Committee meeting records |
| `rpt.py` | `/rpt` | Related-party transactions |

---

### 2.3 Services

**Directory:** `backend/services/`

The business logic layer. Each service module mirrors its router and owns:

- Database queries (SQL or MongoDB).
- Data transformation and aggregation.
- Calls to external services (Gemini API, FAISS).
- Error handling before the result is returned to the router.

`security.py` is a special service that exposes two FastAPI dependency functions:
- `get_api_key` — validates `X-API-Key` header for all protected routes.
- `get_api_key_docs` — additionally accepts the key as a query parameter (for browser-based Swagger UI access).

---

### 2.4 Database Layer

#### PostgreSQL

**File:** `backend/db_setup.py`

- Provides `connect_to_db()` which reads `POSTGRES_URL` from the environment and returns a `psycopg2` connection.
- Used by: financial statements, ratios, stock data, shareholding, dividends, corporate governance, insider trading, and the RAG context retrieval router.
- All synchronous DB calls are dispatched via `run_in_threadpool` inside async route handlers to avoid blocking the event loop.

Key tables (inferred from services and `sql_rag.py`):

| Table | Contents |
|---|---|
| `company_detail` | Master list of companies (id, ticker, full_name) |
| `profit_and_loss` | Annual/quarterly P&L statements |
| `balance_sheet` | Balance sheet data |
| `cashflow` | Cash flow statements |
| `financial_ratios` | Pre-computed financial ratios |
| `stock_price` | Daily closing prices |
| `stock_dma50` | 50-day moving average |
| `stock_dma200` | 200-day moving average |
| `stock_volume` | Daily trading volume |
| `dividend` | Dividend payment records |
| `share_holder` | Shareholding pattern snapshots |

#### MongoDB

**File:** `backend/db_mongo.py`

- Provides `get_database()` which connects to `MONGO_URI` and returns the configured collection.
- `save_to_mongodb()` upserts a classified financial document (from Gemini classification).
- `get_classified_data()` retrieves documents filtered by ticker and date.

Primary collections:
- `classified_texts` — Gemini-classified sections of annual reports.
- `earnings_calls_fy25` — Full-text earnings-call transcripts (source for FAISS index).

---

### 2.5 AI & Vector Search Layer

#### Google Gemini

**File:** `backend/geminiapi.py`

Three main functions built on `google-genai`:

| Function | Purpose |
|---|---|
| `classify_with_gemini(text, categories)` | Returns category labels + confidence scores for a text segment |
| `summarize_with_gemini(text)` | Generates a concise summary (≤ 400 chars) |
| `classify_and_summarize_with_gemini(text, categories)` | Single-call classify + detailed summaries per category |

Model used: `gemini-2.0-flash-thinking-exp-01-21`.

Categories supported: `MDnA`, `Risk_Factors`, `Company_Segment`, `Company_Infrastructure`, `Shareholder_Performance`, `Company_Subsidiaries`, `ESG`, `Employee_Info`, `Letter_To_Shareholders`, `Business_Overview`, `Corporate_Governance_Report`, `Corporate_Social_Responsibility`, `Auditor_Report`, `Shareholder_Information`.

#### LangChain + FAISS

**File:** `backend/make_vector_db_from_documents.py`

Offline pipeline to build the FAISS vector index from earnings-call transcripts stored in MongoDB:

1. Connect to MongoDB collection `earnings_calls_fy25`.
2. Split each document into 1 000-character chunks (100-character overlap) using `RecursiveCharacterTextSplitter`.
3. Embed chunks with `sentence-transformers/all-MiniLM-L6-v2` via `HuggingFaceEmbeddings`.
4. Build and persist a `FAISS` index to `backend/faiss_earnings_quarters/`.

Analogous processing produces `backend/faiss_annual/` for annual report documents.

Both indexes are loaded at runtime by `copilot_service.py` to provide semantic retrieval over unstructured financial text.

#### Query Intent Analyzer

**File:** `backend/tools/query_intent_analyzer.py`

`QueryIntentAnalyzer` classifies free-text user queries into structured intents before they reach the LLM, enabling the copilot to select the correct retrieval strategy and prompt template. Intent categories include `RATIO_ANALYSIS`, `CHART_VISUALIZATION`, and others, each carrying priority levels, keyword lists, primary/context data requirements, and recommended prompt templates.

---

### 2.6 Tools

**Directory:** `backend/tools/`

Utility modules used by services:

| File | Purpose |
|---|---|
| `query_intent_analyzer.py` | Classifies user query intent; maps to data requirements and LLM templates |

---

## 3. Request Lifecycle

```
Client
  │
  │  HTTP request + X-API-Key header
  ▼
FastAPI middleware
  ├─ CORS check
  ├─ API-key validation (get_api_key dependency)
  └─ Request timing (X-Process-Time)
  │
  ▼
Router (backend/routers/<domain>.py)
  │  Parse & validate request body / path params via Pydantic
  ▼
Service (backend/services/<domain>_service.py)
  │  Business logic, DB queries, external API calls
  │
  ├─── PostgreSQL (via run_in_threadpool)
  ├─── MongoDB
  ├─── Gemini API
  └─── FAISS index
  │
  ▼
Router
  │  Serialize response via Pydantic model
  ▼
Client
```

---

## 4. Data Flow Diagrams

### Standard API Request

```
GET /financials?ticker=RELIANCE
        │
        ▼
  financials.py router
        │
        ▼
  financial_service.py
        │ SELECT * FROM profit_and_loss WHERE ...
        ▼
  PostgreSQL
        │
        ▼
  JSON response → Client
```

### AI Copilot Request

```
POST /copilot  { "query": "How is Infosys performing?", "ticker": "INFY" }
        │
        ▼
  copilot.py router
        │
        ▼
  copilot_service.py
        ├─ QueryIntentAnalyzer → determine required data tables
        ├─ POST /rag_flask/retrieve_sql_context → structured financial context
        ├─ FAISS similarity search (annual + earnings indexes)
        └─ LangChain chain → Gemini LLM
                │  prompt: intent template + structured context + vector context
                ▼
        Gemini response (natural-language analysis)
        │
        ▼
  JSON response → Client
```

### FAISS Index Build Pipeline

```
MongoDB (earnings_calls_fy25)
        │  raw transcript documents
        ▼
make_vector_db_from_documents.py
        │  RecursiveCharacterTextSplitter (1 000 chars / 100 overlap)
        ▼
  HuggingFaceEmbeddings (all-MiniLM-L6-v2)
        │
        ▼
  FAISS.from_documents(...)
        │
        ▼
  backend/faiss_earnings_quarters/  (persisted index)
```

---

## 5. Domain Modules

### Financial Statements
Covers P&L, balance sheet, and cash flow data stored in PostgreSQL. Services read pre-computed context strings and return them directly to the caller (or to the RAG pipeline via `/rag_flask`).

### Ratios
Pre-computed financial ratios (ROE, ROA, PE, PB, current ratio, debt-to-equity, etc.) served from the `financial_ratios` PostgreSQL table.

### Stock Data & Charts
OHLCV price data with 50 DMA and 200 DMA. Chart service aggregates data into series suitable for frontend charting libraries (Plotly).

### AI Copilot
Natural-language financial analyst powered by LangChain orchestrating Gemini LLM, FAISS vector retrieval, and SQL context retrieval. Uses `QueryIntentAnalyzer` to route queries to the correct prompt template.

### RAG SQL Context
`/rag_flask/retrieve_sql_context` is consumed by external RAG services (e.g., a separate Flask-based LLM pipeline). It accepts a company ticker and a list of table names and returns formatted textual context from those tables.

### Corporate Governance
Board and committee composition, meeting minutes, related-party transactions, insider trading disclosures, and pledged shares — all sourced from PostgreSQL.

### Document Store
Annual reports and earnings-call transcripts are stored in MongoDB, classified/summarised by Gemini, and indexed in FAISS for semantic retrieval.

---

## 6. Security Model

- **API Key**: All business endpoints require `X-API-Key: <key>` header. The key is validated against the `API_ACCESS_KEY` environment variable.
- **Docs Protection**: `/docs`, `/redoc`, and `/openapi.json` accept the key via header or query string.
- **CORS**: Only the Quanvest frontend (Vercel + custom domain) and `localhost:3000` are allowed origins. Credentials are permitted.
- **No secrets in code**: All sensitive values (DB URLs, API keys) are loaded from environment variables via `python-dotenv`.

---

## 7. Concurrency Model

| Concern | Approach |
|---|---|
| Event loop | uvloop (replaces asyncio default loop for higher throughput) |
| Sync I/O (PostgreSQL, MongoDB) | `run_in_threadpool` / `ThreadPoolExecutor` (50 workers) |
| Server workers | 4 Uvicorn workers in production (`--workers 4`) |
| Async routes | All route handlers are `async def` |

---

## 8. Infrastructure & Deployment

```
Docker container (Python 3.12)
├─ Uvicorn + uvloop (4 workers, port 8000)
├─ FastAPI application
├─ Embedded FAISS indexes (faiss_annual/, faiss_earnings_quarters/)
└─ output/ directory (for generated artefacts)
```

The container reads all configuration from environment variables, making it compatible with any container orchestration platform (ECS, GKE, Railway, Fly.io, etc.).

---

## 9. Environment & Configuration

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_URL` | Yes | Full PostgreSQL connection string |
| `MONGO_URI` | Yes | MongoDB connection URI |
| `DB_NAME` | No | MongoDB database name (default: `financial_documents`) |
| `COLLECTION_NAME` | No | MongoDB collection name (default: `classified_texts`) |
| `API_ACCESS_KEY` | Yes | Shared secret for API-key authentication |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
