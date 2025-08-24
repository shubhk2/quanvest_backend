# FastAPI Backend for SQL Context Retrieval - No Classes Version
# This will be added to your main FastAPI server as new endpoints

from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import time  # Import time module
from psycopg2.extras import RealDictCursor
from backend.db_setup import connect_to_db # Ensure this is correctly set up in your db_setup module
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration


# Valid tables for context retrieval
VALID_TABLES = [
    'profit_and_loss',
    'balance_sheet',
    'cashflow',
    'financial_ratios',
    'shareholder',
    # NEW: dividend context table
    'dividend',
    # NEW: stock tables (for last 1 month data snapshot)
    'stock_price',
    'stock_dma50',
    'stock_dma200',
    'stock_volume'
]


# Request/Response models
class SQLContextRequest(BaseModel):
    company_ticker: str
    required_tables: List[str]


class SQLContextResponse(BaseModel):
    status: str
    company_ticker: str
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    contexts: Dict[str, str]
    error: Optional[str] = None


# Database helper functions
def get_db_connection():
    """Get database connection"""
    try:
        conn = connect_to_db()
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


def get_company_info(ticker: str) -> Optional[Dict]:
    """
    Get company ID and name from company_detail table
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Query to get company information
        query = """
        SELECT id, ticker, full_name
        FROM company_detail
        WHERE UPPER(ticker) = UPPER(%s)
        """
        start_time = time.time()
        cursor.execute(query, (ticker,))
        result = cursor.fetchone()
        duration = time.time() - start_time
        logger.info(f"DB query for company_info on ticker '{ticker}' took {duration:.4f} seconds.")

        cursor.close()
        conn.close()

        if result:
            return {
                'id': result['id'],
                'ticker': result['ticker'],
                'full_name': result['full_name']
            }
        else:
            logger.warning(f"Company not found for ticker: {ticker}")
            return None

    except Exception as e:
        logger.error(f"Error getting company info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving company info: {str(e)}")


async def retrieve_table_context_async(company_id: int, table_name: str) -> Optional[str]:
    """Fully async version of table context retrieval"""
    if table_name not in VALID_TABLES:
        logger.warning(f"Invalid table name: {table_name}")
        return None

    try:
        async with get_async_db_connection() as conn:
            cursor = await run_in_threadpool(conn.cursor, cursor_factory=RealDictCursor)

            # Handle stock tables: return last 1 month of date,value pairs
            if table_name in {'stock_price', 'stock_dma50', 'stock_dma200', 'stock_volume'}:
                try:
                    # 1) Find latest date for this company in the selected stock table
                    await run_in_threadpool(cursor.execute,
                                            f"SELECT MAX(date) AS latest_date FROM {table_name} WHERE company_number = %s",
                                            (company_id,))
                    latest_row = await run_in_threadpool(cursor.fetchone)
                    latest_date = latest_row and latest_row.get('latest_date')
                    if not latest_date:
                        await run_in_threadpool(cursor.close)
                        return None

                    # 2) Compute start date = latest_date - 30 days
                    start_date = latest_date - timedelta(days=30)

                    # 3) Fetch rows in the last month
                    await run_in_threadpool(
                        cursor.execute,
                        f"""
                        SELECT date, value
                        FROM {table_name}
                        WHERE company_number = %s AND date >= %s AND date <= %s
                        ORDER BY date ASC
                        """,
                        (company_id, start_date, latest_date)
                    )
                    rows = await run_in_threadpool(cursor.fetchall)
                    await run_in_threadpool(cursor.close)

                    if not rows:
                        return None

                    # 4) Format as compact CSV-like text for LLM context
                    header = f"{table_name} • last_1_month • {start_date.date()} → {latest_date.date()}"
                    lines = ["date,value"]
                    for r in rows:
                        d = r['date'].strftime('%Y-%m-%d') if isinstance(r['date'], datetime) else str(r['date'])
                        lines.append(f"{d},{r['value']}")
                    return header + "\n" + "\n".join(lines)
                except Exception as stock_err:
                    logger.error(f"Error retrieving stock data for {table_name}: {stock_err}")
                    await run_in_threadpool(cursor.close)
                    return None

            # Handle dividend context: table 'dividend' with company_no
            if table_name == 'dividend':
                query = """
                SELECT context
                FROM dividend
                WHERE company_no = %s
                AND context IS NOT NULL
                AND context != ''
                """
                start_time = time.time()
                await run_in_threadpool(cursor.execute, query, (company_id,))
                results = await run_in_threadpool(cursor.fetchall)
                duration = time.time() - start_time
                await run_in_threadpool(cursor.close)
                logger.info(f"🔍 DB query for {table_name} took {duration:.4f} seconds")
                if results:
                    contexts = [result['context'] for result in results if result.get('context')]
                    combined_context = "\n\n".join(contexts)
                    logger.info(f"📊 Retrieved {table_name} context: {len(combined_context)} characters")
                    return combined_context
                return None

            # Existing handlers
            if table_name != 'shareholder':
                query = f"""
                SELECT context
                FROM {table_name}
                WHERE company_number = %s
                AND context IS NOT NULL
                AND context != ''
                """
            else:
                query = f"""
                SELECT context
                FROM share_holder
                WHERE company_no = %s
                AND context IS NOT NULL
                """

            start_time = time.time()
            await run_in_threadpool(cursor.execute, query, (company_id,))
            results = await run_in_threadpool(cursor.fetchall)
            duration = time.time() - start_time

            await run_in_threadpool(cursor.close)

            logger.info(f"🔍 DB query for {table_name} took {duration:.4f} seconds")

            if results:
                contexts = [result['context'] for result in results if result.get('context')]
                combined_context = "\n\n".join(contexts)
                logger.info(f"📊 Retrieved {table_name} context: {len(combined_context)} characters")
                return combined_context
            else:
                logger.info(f"📭 No context found in {table_name} for company {company_id}")
                return None

    except Exception as e:
        logger.error(f"💥 Error retrieving context from {table_name}: {str(e)}")
        return None

async def retrieve_all_contexts(company_id: int, required_tables: List[str]) -> Dict[str, str]:
    contexts: dict[str, str] = {}
    tasks = []

    for table_name in required_tables:
        tasks.append((table_name, retrieve_table_context_async(company_id, table_name)))

    results = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
    for (table_name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            contexts[table_name] = f"Error: {str(result)}"
        elif result is None:
            contexts[table_name] = ""
        else:
            contexts[table_name] = str(result)

    return contexts
# --- New synchronous helper functions for async execution ---

def check_db_connection():
    """Synchronous function to check DB connection."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    cursor.fetchone()
    cursor.close()
    conn.close()
    return True


def get_all_companies(limit: int):
    """Synchronous function to list available companies."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = "SELECT id, ticker, full_name FROM company_detail ORDER BY ticker LIMIT %s"
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in results]


def calculate_table_stats():
    """Synchronous function to get statistics about context availability."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    stats = {}
    for table in VALID_TABLES:
        try:
            # Special handling for stock tables (no 'context' column)
            if table in {'stock_price', 'stock_dma50', 'stock_dma200', 'stock_volume'}:
                cursor.execute(
                    f"SELECT COUNT(*) AS total_rows, MAX(date) AS latest_date FROM {table}"
                )
                result = cursor.fetchone()
                latest_date = result.get('latest_date')
                recent_rows = 0
                if latest_date:
                    start_date = latest_date - timedelta(days=30)
                    cursor.execute(
                        f"SELECT COUNT(*) AS cnt FROM {table} WHERE date >= %s AND date <= %s",
                        (start_date, latest_date)
                    )
                    recent_rows = cursor.fetchone().get('cnt', 0)
                stats[table] = {
                    "total_rows": result['total_rows'],
                    "rows_with_context": recent_rows,
                    "context_coverage": 100.0 if result['total_rows'] else 0.0,
                    "latest_date": latest_date.strftime('%Y-%m-%d') if latest_date else None
                }
                continue

            # Default: tables with 'context' column
            query = f"""
            SELECT
                COUNT(*) as total_rows,
                COUNT(CASE WHEN context IS NOT NULL AND context != '' THEN 1 END) as rows_with_context
            FROM {table}
            """
            cursor.execute(query)
            result = cursor.fetchone()
            stats[table] = {
                "total_rows": result['total_rows'],
                "rows_with_context": result['rows_with_context'],
                "context_coverage": round(
                    (result['rows_with_context'] / result['total_rows'] * 100), 2) if result['total_rows'] > 0 else 0
            }
        except Exception as e:
            stats[table] = {"error": str(e)}
    cursor.close()
    conn.close()
    return stats


# Create router for RAG endpoints
router = APIRouter(prefix="/rag_flask", tags=["rag_flask"])


@router.get("/")
async def rag_root():
    """Root endpoint for RAG Flask integration"""
    return {"message": "Financial Data SQL Context API for RAG Flask Integration", "version": "1.0.0"}


@router.get("/health")
async def rag_health_check():
    """Health check endpoint for RAG integration"""
    try:
        # Test database connection in a thread pool
        await run_in_threadpool(check_db_connection)
        return {
            "status": "healthy",
            "database_connection": "ok",
            "valid_tables": VALID_TABLES,
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "database_connection": "failed",
            "error": str(e)
        }


@router.post("/retrieve_sql_context", response_model=SQLContextResponse)
async def retrieve_sql_context_endpoint(request: SQLContextRequest):
    """
    Enhanced async endpoint for SQL context retrieval with better concurrency
    """
    request_start_time = time.time()

    try:
        logger.info(f"🔄 Processing SQL context request for {request.company_ticker}, tables: {request.required_tables}")

        # Validate request
        if not request.company_ticker or not request.required_tables:
            raise HTTPException(status_code=400, detail="company_ticker and required_tables are required")

        # Validate table names
        invalid_tables = [t for t in request.required_tables if t not in VALID_TABLES]
        if invalid_tables:
            raise HTTPException(status_code=400, detail=f"Invalid tables: {invalid_tables}")

        # Execute company lookup and context retrieval concurrently

        company_info = await run_in_threadpool(get_company_info, request.company_ticker)

        if not company_info:
            logger.warning(f"❌ Company not found: {request.company_ticker}")
            return SQLContextResponse(
                status="error",
                company_ticker=request.company_ticker,
                contexts={},
                error=f"Company not found: {request.company_ticker}"
            )

        logger.info(f"✅ Found company: {company_info['full_name']} (ID: {company_info['id']})")

        # Retrieve contexts from all tables concurrently
        tasks = [retrieve_table_context_async(company_info["id"], t) for t in request.required_tables]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Wait for all context retrievals concurrently
        contexts = {t: r or "" for t, r in zip(request.required_tables, results) if not isinstance(r, Exception)}

        for table, value in contexts.items():
            if isinstance(value, Exception):
                logger.error(f"❌ Failed to retrieve context for {table}: {value}")
            elif value:
                logger.info(f"✅ Retrieved {table} context: {len(value)} chars")
            else:
                logger.info(f"⚠️ No context found for {table}")

        total_duration = time.time() - request_start_time
        logger.info(
            f"🎉 Successfully retrieved contexts for {len(contexts)}/{len(request.required_tables)} tables in {total_duration:.2f}s")

        response = SQLContextResponse(
            status="success",
            company_ticker=request.company_ticker,
            company_id=company_info['id'],
            company_name=company_info['full_name'],
            contexts=contexts
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in retrieve_sql_context: {str(e)}")
        total_duration = time.time() - request_start_time
        logger.error(f"💥 Request failed after {total_duration:.2f}s")

        return SQLContextResponse(
            status="error",
            company_ticker=request.company_ticker,
            contexts={},
            error=f"Internal server error: {str(e)}"
        )


@router.post("/company_lookup")
async def company_lookup(ticker: str):
    """Test endpoint to verify company lookup"""
    try:
        company_info = await run_in_threadpool(get_company_info, ticker)
        if company_info:
            return {
                "status": "found",
                "company_info": company_info
            }
        else:
            return {
                "status": "not_found",
                "ticker": ticker
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@asynccontextmanager
async def get_async_db_connection():
    """Async context manager for database connections"""
    conn = None
    try:
        conn = await run_in_threadpool(get_db_connection)
        yield conn
    finally:
        if conn:
            await run_in_threadpool(conn.close)

@router.post("/table_context")
async def table_context(company_id: int, table_name: str):
    """Test endpoint to check context availability for specific table"""
    try:
        if table_name not in VALID_TABLES:
            return {
                "status": "error",
                "error": f"Invalid table name. Valid tables: {VALID_TABLES}"
            }

        context = await retrieve_table_context_async(company_id, table_name)
        return {
            "status": "success",
            "company_id": company_id,
            "table_name": table_name,
            "context_available": context is not None,
            "context_length": len(context) if context else 0,
            "context_preview": context[:200] + "..." if context and len(context) > 200 else context
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/list_companies")
async def list_companies(limit: int = 10):
    """List available companies in the database"""
    try:
        results = await run_in_threadpool(get_all_companies, limit)
        return {
            "status": "success",
            "companies": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error listing companies: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/table_stats")
async def get_table_stats():
    """Get statistics about context availability in each table"""
    try:
        stats = await run_in_threadpool(calculate_table_stats)
        return {
            "status": "success",
            "table_statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting table stats: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


# Instructions for integration into your main FastAPI app:
"""
To integrate this into your main FastAPI application (main.py), add these lines:

from fastapi_sql_context_no_classes import rag_router

app = FastAPI()
app.include_router(rag_router)

This will add all the RAG-related endpoints under the /rag_flask prefix:
- /rag_flask/retrieve_sql_context (main endpoint)
- /rag_flask/health
- /rag_flask/test_company_lookup
- /rag_flask/test_table_context
- /rag_flask/list_companies
- /rag_flask/table_stats

Your Flask server will call: https://quanvest.me/rag_flask/retrieve_sql_context
"""

# Standalone app for testing (you can remove this when integrating)
if __name__ == "__main__":
    import uvicorn

    # Create standalone app for testing
    test_app = FastAPI(title="RAG SQL Context Service - Standalone Test")
    test_app.include_router(router)

    print("Starting FastAPI SQL Context Retrieval Service...")
    print(f"Valid tables: {VALID_TABLES}")
    print("Available endpoints:")
    print("  - /rag_flask/retrieve_sql_context")
    print("  - /rag_flask/health")
    print("  - /rag_flask/test_company_lookup")
    print("  - /rag_flask/list_companies")

    uvicorn.run(test_app, host="0.0.0.0", port=8000)