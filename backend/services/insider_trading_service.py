import logging
from typing import Dict, Any
from psycopg2.extras import RealDictCursor
from backend.db_setup import connect_to_db

logger = logging.getLogger(__name__)

def get_insider_trading_data(company_number: int) -> Dict[str, Any]:
    """
    Returns insider trading data for a given company_number.
    """
    conn = connect_to_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get company name from company_detail
        cursor.execute("""
            SELECT full_name FROM public.company_detail WHERE id = %s LIMIT 1
        """, (company_number,))
        company = cursor.fetchone()
        if not company:
            logger.warning(f"No company found for company_number={company_number}")
            return {"error": f"No company found for {company_number}"}
        company_name = company["full_name"]

        # Get insider trading data for this company name
        cursor.execute("""
            SELECT * FROM public.insider_trading WHERE company_name = %s LIMIT 1
        """, (company_name,))
        row = cursor.fetchone()
        if not row:
            logger.warning(f"No insider trading data found for company_name={company_name}")
            return {"error": f"No insider trading data found for {company_name}"}
        return row
    except Exception as e:
        logger.error(f"Error in get_insider_trading_data: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()