import os
import logging
import time
import re
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
import asyncio
import requests
from concurrent.futures import ThreadPoolExecutor
from backend.services.copilot_service import get_copilot_response
from backend.db_setup import connect_to_db
import aiohttp

logger = logging.getLogger(__name__)
router = APIRouter()


class CopilotRequest(BaseModel):
    user_query: str
    company_ids: Optional[List[int]] = None
    context: Optional[dict] = None
    raw_only: bool = False


# Get API key for internal requests
API_KEY = os.environ.get("API_ACCESS_KEY", "YOUR_GENERATED_API_KEY_HERE")

# ===== NEW: DISPLAY-ONLY TABLES (No Gemini API calls) =====
DISPLAY_ONLY_TABLES = {
    'cg_board_composition',
    'cg_committee_composition',
    'cg_board_meetings',
    'cg_committee_meetings',
    'insider_trading',
    'rpt',
    'pledged_data'
}

# ===== ENDPOINT CONFIGURATIONS =====
# Base URLs for all endpoints
overview_base_url = os.getenv("OVERVIEW_BASE_URL", "https://api.quanvest.me/overview/company")
charts_base_url = os.getenv("CHARTS_BASE_URL", "https://api.quanvest.me/charts")
stock_charts_base_url = os.getenv("STOCK_CHARTS_BASE_URL", "https://api.quanvest.me/stock_data")
flask_url = os.getenv("FLASK_SERVER_URL", "http://localhost:5000")
financials_base_url = os.getenv("FINANCIALS_BASE_URL", "https://api.quanvest.me/financials")
ratio_base_url = os.getenv("RATIO_BASE_URL", "https://api.quanvest.me/ratios")
shareholding_base_url = os.getenv("SHAREHOLDING_BASE_URL", "https://api.quanvest.me/shareholding_pattern")
dividend_base_url = os.getenv("DIVIDEND_BASE_URL", "https://api.quanvest.me/dividend")
insider_trading_base_url = os.getenv("INSIDER_TRADING_BASE_URL", "https://api.quanvest.me/insider_trading")
rpt_base_url = os.getenv("RPT_BASE_URL", "https://api.quanvest.me/rpt")
pledged_data_base_url = os.getenv("PLEDGED_DATA_BASE_URL", "https://api.quanvest.me/pledged_data")

# Corporate Governance endpoints
cg_board_composition_base_url = os.getenv("CG_BOARD_COMPOSITION_BASE_URL",
                                          "https://api.quanvest.me/cg_board_composition")
cg_committee_composition_base_url = os.getenv("CG_COMMITTEE_COMPOSITION_BASE_URL",
                                              "https://api.quanvest.me/cg_committee_composition")
cg_board_meetings_base_url = os.getenv("CG_BOARD_MEETINGS_BASE_URL", "https://api.quanvest.me/cg_board_meetings")
cg_committee_meetings_base_url = os.getenv("CG_COMMITTEE_MEETINGS_BASE_URL",
                                           "https://api.quanvest.me/cg_committee_meetings")

standard_headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
}

ngrok_headers = {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
    'X-API-Key': API_KEY
}


async def make_request_async(url: str, method: str = "POST", json_data: dict = None, headers: dict = None,
                             timeout: int = 20) -> Dict[str, Any]:
    """Async HTTP request to prevent thread pool starvation"""
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        headers = headers or {}
        headers['X-API-Key'] = API_KEY

        async with aiohttp.ClientSession(timeout=timeout) as session:
            if method.upper() == "GET":
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                async with session.post(url, json=json_data, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
    except Exception as e:
        raise Exception(f"Async request to {url} failed: {str(e)}")


def make_request(url: str, method: str = "GET", json_data: dict = None, headers: dict = None) -> Dict[str, Any]:
    """Synchronous HTTP request"""
    try:
        headers = headers or {}
        headers['X-API-Key'] = API_KEY

        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
            print(f"GET {url} - {response.json()}")
        else:
            response = requests.post(url, json=json_data, headers=headers, timeout=30)

        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"Request to {url} failed: {str(e)}")


def is_valid_response(response):
    """Check if response is valid (not an error and has data)"""
    if isinstance(response, dict):
        if response.get('error'):
            return False
        # Check for non-empty 'data' key
        if 'data' in response and isinstance(response['data'], list):
            return len(response['data']) > 0
    return bool(response)
def get_company_numbers_from_db(resolved_companies: List[Dict[str, Any]]) -> List[int]:
    """Get company_numbers from PostgreSQL using resolved companies."""
    if not resolved_companies:
        return []

    conn = None
    cursor = None
    company_numbers = []

    try:
        conn = connect_to_db()
        cursor = conn.cursor()

        for company in resolved_companies:
            ticker = company.get('ticker', '')
            full_name = company.get('full_name', '').lower()

            # Try exact ticker match first
            cursor.execute(
                "SELECT id FROM company_detail WHERE UPPER(ticker) = UPPER(%s)",
                (ticker,)
            )
            result = cursor.fetchone()
            if result:
                company_numbers.append(result[0])
                continue

            # Try fuzzy full_name matching
            cursor.execute(
                "SELECT id FROM company_detail WHERE lower(company_detail.full_name) ILIKE %s LIMIT 1",
                (f"%{full_name}%",)
            )
            result = cursor.fetchone()
            if result:
                company_numbers.append(result[0])

    except Exception as e:
        logger.error(f"Database error: {str(e)}", exc_info=True)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return company_numbers


def prepare_chart_request(chart_endpoint_type: str, company_ids: List[int],
                          parameters: List[str], query_type: str = None) -> Dict[str, Any]:
    """Prepare chart request based on endpoint type and query type"""

    # Default chart request for financial/ratio charts
    chart_request = {
        "company_numbers": company_ids,
        "parameters": parameters[:5],  # Limit to 5 parameters for clarity
        "start_year": 2021,
        "end_year": 2025,
        "chart_type": "line"
    }

    # Special handling for stock charts
    if query_type == "stock_analysis":
        # Determine data_type based on parameters or default to price
        data_type = "price"  # Default

        if any('dma50' in param.lower() for param in parameters):
            data_type = "dma50"
        elif any('dma200' in param.lower() for param in parameters):
            data_type = "dma200"
        elif any('volume' in param.lower() for param in parameters):
            data_type = "price"  # For volume queries, use price data type

        # Stock chart request format
        stock_chart_request = {
            "data_type": data_type,
            "period": "10yr",  # Default period
            "company_number": company_ids[0] if company_ids else None  # Stock charts are per company
        }
        return stock_chart_request

    return chart_request


def get_endpoint_url_and_method(endpoint_type: str, endpoint_mode: str, table_name: str = None) -> Tuple[str, str]:
    """Get appropriate URL and HTTP method for endpoint"""

    endpoint_mapping = {
        'financials': (financials_base_url, 'GET'),
        'ratios': (ratio_base_url, 'GET'),
        'shareholding_pattern': (shareholding_base_url, 'GET'),
        'dividend': (dividend_base_url, 'GET'),
        'insider_trading': (insider_trading_base_url, 'GET'),
        'rpt': (rpt_base_url, 'GET'),
        'pledged_data': (pledged_data_base_url, 'GET'),
        'cg_board_composition': (cg_board_composition_base_url, 'GET'),
        'cg_committee_composition': (cg_committee_composition_base_url, 'GET'),
        'cg_board_meetings': (cg_board_meetings_base_url, 'GET'),
        'cg_committee_meetings': (cg_committee_meetings_base_url, 'GET'),
        'stock_data': (stock_charts_base_url, 'GET')
    }

    base_url, default_method = endpoint_mapping.get(endpoint_type, (financials_base_url, 'GET'))

    # Handle parameter mode for specific endpoints
    if endpoint_mode == 'parameters':
        if endpoint_type in ['financials', 'ratios']:
            return f"{base_url}/parameters", 'POST'

    return base_url, default_method


def build_endpoint_tasks(classification: Dict, company_ids_to_use: List[int]) -> List[Tuple[str, callable]]:
    """Build endpoint tasks based on classification"""
    tasks = []
    required_endpoints = classification.get('required_endpoints', [])

    for endpoint_config in required_endpoints:
        endpoint_type = endpoint_config['type']
        endpoint_mode = endpoint_config['mode']
        parameters = endpoint_config.get('parameters', [])
        table = endpoint_config.get('table', '')

        # Get endpoint URL and method
        url, method = get_endpoint_url_and_method(endpoint_type, endpoint_mode, table)

        if endpoint_type == 'financials':
            for company_id in company_ids_to_use:
                if endpoint_mode == 'parameters' and parameters:
                    query_params = f"?company_number={company_id}&statement_type={table}"
                    body_payload = {
                        "parameters": parameters,
                        "start_year": 2021,
                        "end_year": 2025
                    }
                    task = lambda p=body_payload, q=query_params: make_request(
                        f"{url}{q}", "POST", p, standard_headers)
                    tasks.append((f'financials_{table}_{company_id}', task))
                else:
                    full_url = f"{url}?company_number={company_id}&statement_type={table}&start_year=2021&end_year=2025"
                    task = lambda u=full_url: make_request(u, "GET", headers=standard_headers)
                    tasks.append((f'financials_{table}_{company_id}', task))

        elif endpoint_type == 'ratios':
            if endpoint_mode == 'parameters' and parameters:
                payload = {
                    "company_numbers": company_ids_to_use,
                    "parameters": parameters,
                    "start_year": 2021,
                    "end_year": 2025
                }
                task = lambda p=payload: make_request(f"{url}", "POST", p, standard_headers)
                tasks.append(('ratios_filtered', task))
            else:
                for company_id in company_ids_to_use:
                    full_url = f"{url}?company_number={company_id}&start_year=2021&end_year=2025"
                    task = lambda u=full_url: make_request(u, "GET", headers=standard_headers)
                    tasks.append((f'ratios_{company_id}', task))

        else:
            # Handle all other domain-specific endpoints
            for company_id in company_ids_to_use:
                full_url = f"{url}?company_number={company_id}"
                task = lambda u=full_url: make_request(u, "GET", headers=standard_headers)
                tasks.append((f'{endpoint_type}_{company_id}', task))

    return tasks


def should_skip_gemini_call(classification: Dict) -> bool:
    """Determine if we should skip Gemini API call for display-only queries"""
    required_tables = classification.get('required_sql_tables', [])

    # If ALL required tables are display-only, skip Gemini
    if required_tables and all(table in DISPLAY_ONLY_TABLES for table in required_tables):
        return True

    return False


def generate_display_only_response(classification: Dict, resolved_companies: List[Dict]) -> str:
    """Generate simple text response for display-only tables"""
    query_type = classification.get('query_type', '')
    company_names = [comp.get('full_name', comp.get('ticker', 'Company')) for comp in resolved_companies]
    company_text = ', '.join(company_names)

    response_templates = {
        'pledged_data_analysis': f"Here is the latest pledged data for {company_text}:\n~PLEDGED_DATA_TABLE~",
        'insider_trading_analysis': f"Here are the insider trading details for {company_text}:\n~INSIDER_TRADING_TABLE~",
        'rpt_analysis': f"Here are the related party transactions for {company_text}:\n~RPT_TABLE~",
        'corporate_governance': f"Here is the corporate governance information for {company_text}:\n~CORPORATE_GOVERNANCE_TABLE~",
    }

    return response_templates.get(query_type, f"Here is the requested information for {company_text}:")


# Alias for consistency
http_sync = make_request


@router.post("/ask")
async def ask_copilot(request: CopilotRequest):
    """Enhanced copilot with comprehensive endpoint support"""
    request_start_time = time.time()
    logger.info("Copilot /ask endpoint called with final integration.")

    # Step 1: Get enhanced context from Flask
    enhanced_context_data = {}
    display_recommendations = {}
    classification = {}

    try:
        logger.info("Calling Flask /enhanced_retrieve for hybrid context")
        colab_call_start_time = time.time()

        enhanced_response = await make_request_async(
            f"{flask_url}/enhanced_retrieve",
            "POST",
            {"query": request.user_query},
            ngrok_headers,
            timeout=25
        )

        colab_call_duration = time.time() - colab_call_start_time
        logger.info(f"Flask /enhanced_retrieve call completed in {colab_call_duration:.2f} seconds.")

        enhanced_context_data = enhanced_response
        combined_context = enhanced_response.get('combined_context', '')
        classification = enhanced_response.get('classification', {})
        display_recommendations = classification.get('display_components', {})

        logger.info(f"Classification: {classification.get('query_type', 'unknown')}")
        logger.info(f"Display recommendations: {display_recommendations}")

    except Exception as e:
        logger.error(f"Enhanced retrieve failed: {str(e)}")
        enhanced_context_data = {"error": str(e)}

        # Create fallback context
        if "timeout" in str(e).lower():
            combined_context = f"Query classified as: {request.user_query}\nDataSource: hybrid analysis requested\nNote: Some context retrieval timed out but continuing with available data."
        else:
            combined_context = f"Processing query: {request.user_query}\nFallback context due to retrieval issues."

        display_recommendations = {
            "llm_response": True,
            "table": False,
            "chart": False,
            "company_overview": False
        }

        classification = {
            "required_sql_tables": [],
            "query_type": "company_overview",
            "endpoint_type": "overview",
            "endpoint_mode": "base"
        }

    # Step 2: Extract classification details
    query_type = classification.get('query_type', 'company_overview')
    endpoint_type = classification.get('endpoint_type', 'overview')
    endpoint_mode = classification.get('endpoint_mode', 'base')
    chart_endpoint_type = classification.get('chart_endpoint_type', 'parameters')
    chart_parameters = classification.get('chart_parameters', [])
    identified_parameters = classification.get('identified_parameters', {})
    required_sql_tables = classification.get('required_sql_tables', [])
    is_comparison = classification.get('is_comparison_query', False)

    # Step 3: Determine company IDs
    company_ids_to_use = []
    resolved_companies = enhanced_context_data.get('resolved_companies', [])
    if resolved_companies:
        company_ids_to_use = get_company_numbers_from_db(resolved_companies)
        logger.info(f"Extracted company IDs: {company_ids_to_use}")

    # Step 4: Check if this is a display-only query
    skip_gemini = should_skip_gemini_call(classification)
    logger.info(f"Skip Gemini API call: {skip_gemini}")

    # Step 5: Build all required endpoint tasks
    all_tasks_lambdas = []
    task_order = []

    # Company Overview tasks (conditional)
    if display_recommendations.get('company_overview', False) and company_ids_to_use:
        for company_id in company_ids_to_use:
            if isinstance(company_id, int) and company_id > 0:
                current_overview_url = f"{overview_base_url}/{company_id}"
                all_tasks_lambdas.append(
                    lambda url=current_overview_url: http_sync(url, "GET", headers=standard_headers)
                )
        task_order.append('overview')
        logger.info(f"Added {len(company_ids_to_use)} overview tasks")

    # Chart tasks (conditional with intelligent endpoint selection)
    chart_data = {}
    if display_recommendations.get('chart', False) and company_ids_to_use and chart_parameters:
        # Determine chart URL based on query type
        if query_type == "stock_analysis":
            # Use stock charts endpoint
            chart_request = prepare_chart_request(chart_endpoint_type, company_ids_to_use,
                                                  chart_parameters, query_type)
            chart_url = f"{stock_charts_base_url}/{chart_request['data_type']}/{chart_request['period']}/chart"
            # Add company_number as query parameter
            chart_url += f"?company_number={chart_request['company_number']}"
            all_tasks_lambdas.append(
                lambda: http_sync(chart_url, "GET", headers=standard_headers)
            )
        else:
            # Use regular financial/ratio charts
            if query_type in ['ratio_analysis', 'comprehensive'] or 'ratio' in chart_endpoint_type:
                chart_url = f"{charts_base_url}/ratios"
            else:
                chart_url = f"{charts_base_url}/parameters"

            chart_payload = prepare_chart_request(chart_endpoint_type, company_ids_to_use, chart_parameters)
            all_tasks_lambdas.append(
                lambda: http_sync(chart_url, "POST", chart_payload, standard_headers)
            )

        task_order.append('chart')
        logger.info(f"Added chart task for {query_type}")
    else:
        all_tasks_lambdas.append(lambda: {})
        task_order.append('chart')

    # Multi-endpoint data tasks
    if display_recommendations.get('table', False) and company_ids_to_use:
        endpoint_tasks = build_endpoint_tasks(classification, company_ids_to_use)
        for task_name, task_func in endpoint_tasks:
            all_tasks_lambdas.append(task_func)
            task_order.append(f'data_{task_name}')
        logger.info(f"Added {len(endpoint_tasks)} data endpoint tasks")
    else:
        all_tasks_lambdas.append(lambda: {})
        task_order.append('data')

    # Step 6: Execute parallel tasks
    loop = asyncio.get_event_loop()
    results = []
    if all_tasks_lambdas:
        parallel_fetch_start_time = time.time()
        with ThreadPoolExecutor(max_workers=len(all_tasks_lambdas)) as executor:
            futures = [loop.run_in_executor(executor, task_lambda) for task_lambda in all_tasks_lambdas]
            results = await asyncio.gather(*futures, return_exceptions=True)

        parallel_fetch_duration = time.time() - parallel_fetch_start_time
        logger.info(
            f"Parallel data fetch completed in {parallel_fetch_duration:.2f} seconds for {len(all_tasks_lambdas)} tasks.")

    # Step 7: Process results
    all_responses = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Error in parallel fetch: {str(r)}")
            all_responses.append({"error": str(r)})
        else:
            all_responses.append(r)

    # Step 8: Segment response data based on task order
    company_overviews = []
    chart_data = {}
    consolidated_data = {
        'financial_statements': {},
        'ratios': {},
        'shareholding': [],
        'dividend': [],
        'insider_trading': [],
        'rpt': [],
        'pledged_data': [],
        'corporate_governance': []
    }

    # Process responses based on task_order
    response_idx = 0
    for task_type in task_order:
        if response_idx >= len(all_responses):
            break

        if task_type == 'overview':
            overview_data = all_responses[response_idx]
            company_overviews.append(overview_data)

            # Add stats to context if available
            if overview_data and not overview_data.get('error'):
                stats_obj = overview_data.get('stats')
                if stats_obj and isinstance(stats_obj, dict):
                    stats_str = format_company_stats(stats_obj)
                    if stats_str:
                        combined_context += f"\n\nCompany Stats:\n{stats_str}"
            response_idx += 1

        elif task_type == 'chart':
            chart_data = all_responses[response_idx]
            response_idx += 1


        elif task_type.startswith('data_'):

            # Process data endpoint results with robust parsing for names containing underscores

            data_result = all_responses[response_idx]

            parts = task_type.split('_')

            # strip leading 'data'

            parts = parts[1:] if parts and parts[0] == 'data' else parts

            if not parts:
                response_idx += 1

                continue

            primary = parts[0]

            if primary == 'financials':

                # table name may contain underscores; company_id is the last token

                company_id = parts[-1] if len(parts) >= 2 else 'unknown'

                table_name = '_'.join(parts[1:-1]) if len(parts) > 2 else 'unknown'

                if table_name not in consolidated_data['financial_statements']:
                    consolidated_data['financial_statements'][table_name] = []

                consolidated_data['financial_statements'][table_name].append(data_result)


            elif primary == 'ratios':

                # company id or 'filtered' is the last token

                company_id = parts[-1] if len(parts) >= 2 else 'filtered'

                consolidated_data['ratios'][company_id] = data_result


            else:

                # endpoint types like 'pledged_data', 'insider_trading', 'rpt', 'cg_*' can contain underscores

                data_type = '_'.join(parts[:-1]) if len(parts) > 1 else parts[0]

                consolidated_data.setdefault(data_type, [])

                consolidated_data[data_type].append(data_result)

            response_idx += 1

    # Step 9: Return raw data if requested
    if request.raw_only:
        return {
            "llm_response": None,
            "enhanced_context_data": enhanced_context_data,
            "company_overviews": company_overviews,
            "chart_data": chart_data,
            "consolidated_data": consolidated_data,
            "display_recommendations": display_recommendations,
            "classification": classification
        }

    # Step 10: Generate LLM response or display-only response
    if skip_gemini:
        # Generate simple display-only response
        llm_response_text = generate_display_only_response(classification, resolved_companies)
        processed_llm_response = process_llm_response( llm_response_text=llm_response_text,
                display_recommendations=display_recommendations,
                classification=classification,
                company_overviews=company_overviews,
                consolidated_data=consolidated_data,
                chart_data=chart_data)
        logger.info("Generated display-only response (no Gemini API call)")
    else:
        # Prepare context data for Gemini
        context_data = {
            "query_type": query_type,
            "endpoint_type": endpoint_type,
            "endpoint_mode": endpoint_mode,
            "identified_parameters": identified_parameters,
            "required_sql_tables": required_sql_tables,
            "company_count": len(company_ids_to_use) if company_ids_to_use else 0,
            "has_charts": bool(chart_data and not chart_data.get('error')),
            "has_ratios": bool(consolidated_data['ratios']) and any(
                is_valid_response(d) for d in consolidated_data['ratios'].values()),
            "has_financials": bool(consolidated_data['financial_statements']) and any(
                is_valid_response(d) for table_data in consolidated_data['financial_statements'].values()
                for d in table_data),
            "has_shareholding": bool(consolidated_data['shareholding']) and any(
                is_valid_response(d) for d in consolidated_data['shareholding']),
            "has_dividend": bool(consolidated_data['dividend']) and any(
                is_valid_response(d) for d in consolidated_data['dividend']),
            "has_corporate_governance": bool(consolidated_data['corporate_governance']) and any(
                is_valid_response(d) for d in consolidated_data['corporate_governance']),
            "is_comparison": is_comparison
        }

        # Generate LLM response
        try:
            gemini_call_start_time = time.time()
            gemini_result = await get_copilot_response(
                user_query=request.user_query,
                refined_context=combined_context,
                context_data=context_data
            )
            gemini_call_duration = time.time() - gemini_call_start_time
            logger.info(f"Gemini API call completed in {gemini_call_duration:.2f} seconds.")

            # Process LLM response for structured output
            processed_llm_response = process_llm_response(
                llm_response_text=gemini_result.get("response", ""),
                display_recommendations=display_recommendations,
                classification=classification,
                company_overviews=company_overviews,
                consolidated_data=consolidated_data,
                chart_data=chart_data
            )

        except Exception as e:
            logger.error(f"Gemini call failed: {str(e)}")
            processed_llm_response = [
                f"I apologize, but I encountered an error while generating the response: {str(e)}"]

    # Step 11: Return comprehensive response
    total_request_duration = time.time() - request_start_time
    logger.info(f"Total copilot request processed in {total_request_duration:.2f} seconds.")

    return {
        "llm_response": processed_llm_response,
        "enhanced_context_data": enhanced_context_data,
        "company_overviews": company_overviews,
        "chart_data": chart_data,
        "consolidated_data": consolidated_data,
        "display_recommendations": display_recommendations,
        "classification": classification,
        "company_ids": company_ids_to_use,
        "context_info": {
            "query_type": query_type,
            "is_comparison": is_comparison,
            "skip_gemini": skip_gemini,
            "endpoint_routing": {
                "endpoint_type": endpoint_type,
                "endpoint_mode": endpoint_mode,
                "chart_endpoint_type": chart_endpoint_type
            },
            "parameter_filtering": {
                "total_parameters": sum(len(params) for params in identified_parameters.values()),
                "filtered_tables": list(identified_parameters.keys()),
                "chart_parameters": chart_parameters
            },
            "data_availability": {
                "company_overviews": len(
                    [d for d in company_overviews if not (isinstance(d, dict) and d.get('error'))]),
                "charts": 1 if chart_data and not chart_data.get('error') else 0,
                "financial_statements": len(consolidated_data.get('financial_statements', {})),
                "ratios": len(consolidated_data.get('ratios', {})),
                "shareholding": len(consolidated_data.get('shareholding', [])),
                "dividend": len(consolidated_data.get('dividend', [])),
                "insider_trading": len(consolidated_data.get('insider_trading', [])),
                "rpt": len(consolidated_data.get('rpt', [])),
                "pledged_data": len(consolidated_data.get('pledged_data', [])),
                "corporate_governance": len(consolidated_data.get('corporate_governance', []))
            },
            "resolved_companies": enhanced_context_data.get("resolved_companies", []),
            "total_context_length": len(combined_context)
        }
    }


def process_llm_response(
        llm_response_text: str,
        display_recommendations: Dict,
        classification: Dict,
        company_overviews: List,
        consolidated_data: Dict,
        chart_data: Dict
) -> List[Any]:
    """Process the LLM response to split it by placeholders and inject metadata."""

    placeholder_patterns = [
        '~OVERVIEW_STATS_TABLE~', '~COMPARISON_TABLE~', '~SHAREHOLDING_TABLE~',
        '~RATIOS_TABLE~', '~COMPREHENSIVE_RATIOS_TABLE~', '~FINANCIAL_PARAMETERS_TABLE~',
        '~CHARTS_SECTION~', '~FINANCIAL_DATA_TABLE~', '~DIVIDEND_TABLE~',
        '~INSIDER_TRADING_TABLE~', '~RPT_TABLE~', '~PLEDGED_DATA_TABLE~',
        '~CORPORATE_GOVERNANCE_TABLE~', '~STOCK_CHART_SECTION~'
    ]

    # Create regex to find placeholders
    regex = re.compile(f"({'|'.join(re.escape(p) for p in placeholder_patterns)})")
    parts = regex.split(llm_response_text)

    output = []
    processed_placeholders = set()

    for part in parts:
        if not part:
            continue

        if part in placeholder_patterns:
            placeholder = part
            if placeholder in processed_placeholders:
                continue

            metadata = {"placeholder": placeholder, "type": "error", "data": "Error loading table/chart"}

            # Determine type and check data availability
            if placeholder in ['~CHARTS_SECTION~', '~STOCK_CHART_SECTION~']:
                if display_recommendations.get('chart', False) and chart_data and not chart_data.get('error'):
                    chart_type = "stock_chart" if placeholder == '~STOCK_CHART_SECTION~' else "financial_chart"
                    metadata = {
                        "placeholder": placeholder,
                        "type": "chart",
                        "chart_type": chart_type,
                        "parameters": classification.get('chart_parameters', [])
                    }
                else:
                    metadata["data"] = "Chart data is not available or not recommended for display."

            else:
                # Handle table placeholders
                table_type = "unknown"
                data_available = False

                if placeholder == '~OVERVIEW_STATS_TABLE~':
                    table_type = "company_overview"
                    data_available = display_recommendations.get('company_overview', False) and any(
                        is_valid_response(d) for d in company_overviews)

                elif placeholder == '~SHAREHOLDING_TABLE~':
                    table_type = "shareholding"
                    data_available = bool(consolidated_data.get('shareholding')) and any(
                        is_valid_response(d) for d in consolidated_data['shareholding'])

                elif placeholder == '~DIVIDEND_TABLE~':
                    table_type = "dividend"
                    data_available = bool(consolidated_data.get('dividend')) and any(
                        is_valid_response(d) for d in consolidated_data['dividend'])

                elif placeholder == '~INSIDER_TRADING_TABLE~':
                    table_type = "insider_trading"
                    data_available = bool(consolidated_data.get('insider_trading')) and any(
                        is_valid_response(d) for d in consolidated_data['insider_trading'])

                elif placeholder == '~RPT_TABLE~':
                    table_type = "rpt"
                    data_available = bool(consolidated_data.get('rpt')) and any(
                        is_valid_response(d) for d in consolidated_data['rpt'])

                elif placeholder == '~PLEDGED_DATA_TABLE~':
                    table_type = "pledged_data"
                    data_available = bool(consolidated_data.get('pledged_data')) and any(
                        is_valid_response(d) for d in consolidated_data['pledged_data'])

                elif placeholder == '~CORPORATE_GOVERNANCE_TABLE~':
                    table_type = "corporate_governance"
                    data_available = bool(consolidated_data.get('corporate_governance')) and any(
                        is_valid_response(d) for d in consolidated_data['corporate_governance'])

                elif placeholder in ['~RATIOS_TABLE~', '~COMPREHENSIVE_RATIOS_TABLE~', '~COMPARISON_TABLE~']:
                    table_type = "ratios"
                    data_available = bool(consolidated_data.get('ratios')) and any(
                        is_valid_response(d) for d in consolidated_data['ratios'].values())

                elif placeholder in ['~FINANCIAL_PARAMETERS_TABLE~', '~FINANCIAL_DATA_TABLE~']:
                    table_type = "financials"
                    data_available = bool(consolidated_data.get('financial_statements')) and any(
                        is_valid_response(d) for table_data in consolidated_data['financial_statements'].values()
                        for d in table_data)

                if data_available:
                    metadata = {
                        "placeholder": placeholder,
                        "type": "table",
                        "table_type": table_type,
                        "parameters": classification.get('identified_parameters', {})
                    }
                else:
                    metadata["data"] = f"Table data for '{table_type}' is not available or not recommended for display."

            output.append(metadata)
            processed_placeholders.add(placeholder)
        else:
            output.append(part.strip())

    # Filter out empty strings
    return [item for item in output if item]


def format_company_stats(stats: dict) -> str:
    """Convert stats dict into readable string for LLM context."""
    if not stats or not isinstance(stats, dict):
        return ""

    lines = []
    for table, data in stats.items():
        lines.append(f"**{table.replace('_', ' ').title()}**")
        columns = data.get("columns", [])
        values = data.get("values", [])

        if columns and values:
            col_line = " | ".join(columns)
            lines.append(col_line)
            lines.append("-" * len(col_line))

            for row in values:
                row_line = " | ".join(str(x) if x is not None else "" for x in row)
                lines.append(row_line)

        lines.append("")  # Blank line between tables

    return "\n".join(lines)
