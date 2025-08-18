# Copilot Service - Updated for Hybrid RAG Integration
import os
import logging
import time  # Import time module
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


async def make_request_async(url: str, method: str = "POST", json_data: dict = None, headers: dict = None,
                             timeout: int = 20) -> Dict[
    str, Any]:
    """Async HTTP request to prevent thread pool starvation"""
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        # Always add X-API-Key header
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
    """Synchronous HTTP request - your original function"""
    try:
        # Always add X-API-Key header
        headers = headers or {}
        headers['X-API-Key'] = API_KEY

        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        else:
            response = requests.post(url, json=json_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"Request to {url} failed: {str(e)}")


def is_valid_response(response):
    'only for context for finding the correct template'
    return not (isinstance(response, dict) and response.get('error'))


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

            # Strategy 1: Try exact ticker match first
            cursor.execute(
                "SELECT id FROM company_detail WHERE UPPER(ticker) = UPPER(%s)",
                (ticker,)
            )
            result = cursor.fetchone()
            if result:
                company_numbers.append(result[0])
                continue

            # Strategy 2: Try fuzzy full_name matching
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


# def build_financials_url(base_url: str, endpoint_mode: str, company_id: int,
#                          statement_type: str, parameters: List[str] = None) -> str:
#     """Build appropriate financials URL based on endpoint mode"""
#     if endpoint_mode == "parameters" and parameters:
#         # The POST endpoint requires company_number and statement_type as query params
#         return f"{base_url}/parameters?company_number={company_id}&statement_type={statement_type}"
#     else:
#         return f"{base_url}?company_number={company_id}&statement_type={statement_type}&start_year=2021&end_year=2023"


# def build_ratios_url(base_url: str, endpoint_mode: str) -> str:
#     """Build appropriate ratios URL based on endpoint mode"""
#     if endpoint_mode == "parameters":
#         return f"{base_url}/parameters"
#     else:
#         return base_url

#
# def prepare_financials_payload(endpoint_mode: str, company_id: int, statement_type: str,
#                                parameters: List[str] = None) -> Dict[str, Any]:
#     """Prepare payload for financials request"""
#     if endpoint_mode == "parameters" and parameters:
#         # The payload only contains what's in the Pydantic model (body)
#         return {
#             "parameters": parameters,
#             "start_year": 2021,
#             "end_year": 2025
#         }
#     return None  # GET request, no payload needed


# def prepare_ratios_payload(endpoint_mode: str, company_ids: List[int],
#                            parameters: List[str] = None) -> Dict[str, Any]:
#     """Prepare payload for ratios request"""
#     if endpoint_mode == "parameters" and parameters:
#         return {
#             "company_numbers": company_ids,
#             "parameters": parameters,
#             "start_year": 2021,
#             "end_year": 2025
#         }
#     return None


def prepare_chart_request(chart_endpoint_type: str, company_ids: List[int],
                          parameters: List[str]) -> Dict[str, Any]:
    """Prepare chart request based on endpoint type"""
    return {
        "company_numbers": company_ids,
        "parameters": parameters[:5],  # Limit to 5 parameters for chart clarity
        "start_year": 2021,
        "end_year": 2025,
        "chart_type": "line"
    }


def build_endpoint_tasks(classification: Dict, company_ids_to_use: List[int]) -> List[Tuple[str, callable]]:
    tasks = []
    required_endpoints = classification.get('required_endpoints', [])

    for endpoint_config in required_endpoints:
        endpoint_type = endpoint_config['type']
        endpoint_mode = endpoint_config['mode']
        parameters = endpoint_config.get('parameters', [])

        if endpoint_type == 'financials':
            table = endpoint_config['table']
            for company_id in company_ids_to_use:
                if endpoint_mode == 'parameters' and parameters:
                    # Correct parameter separation
                    query_params = f"?company_number={company_id}&statement_type={table}"
                    body_payload = {
                        "parameters": parameters,
                        "start_year": 2021,
                        "end_year": 2025
                    }
                    task = lambda p=body_payload, q=query_params: http_sync(
                        f"{financials_base_url}/parameters{q}",  # Query params in URL
                        "POST",
                        p,  # Parameters in BODY
                        standard_headers
                    )
                    tasks.append((f'financials_{table}_{company_id}', task))
                else:
                    # Use base financials endpoint
                    url = f"{financials_base_url}?company_number={company_id}&statement_type={table}&start_year=2021&end_year=2025"
                    task = lambda u=url: http_sync(u, "GET", headers=standard_headers)
                    tasks.append((f'financials_{table}_{company_id}', task))

        elif endpoint_type == 'ratios':
            if endpoint_mode == 'parameters' and parameters:
                # Use filtered ratios endpoint
                payload = {
                    "company_numbers": company_ids_to_use,
                    "parameters": parameters,
                    "start_year": 2021,
                    "end_year": 2025
                }
                task = lambda p=payload: http_sync(
                    f"{ratio_base_url}/parameters",
                    "POST",
                    p,
                    standard_headers
                )
                tasks.append(('ratios_filtered', task))
            else:
                # Use base ratios endpoint
                for company_id in company_ids_to_use:
                    url = f"{ratio_base_url}?company_number={company_id}&start_year=2021&end_year=2025"
                    task = lambda u=url: http_sync(u, "GET", headers=standard_headers)
                    tasks.append((f'ratios_{company_id}', task))

        elif endpoint_type == 'shareholding':
            for company_id in company_ids_to_use:
                url = f"{shareholding_base_url}?company_number={company_id}"
                task = lambda u=url: http_sync(u, "GET", headers=standard_headers)
                tasks.append((f'shareholding_{company_id}', task))

    return tasks


def filter_data_fetching_by_intent(classification: Dict, user_query: str) -> Dict:
    """Priority waala
    Filter data fetching based on query intent to avoid unnecessary API calls
    """
    try:
        from backend.tools.query_intent_analyzer import analyze_query_intent_and_priority

        # Analyze intent and get priority filtering
        intent_match, priority_filtering = analyze_query_intent_and_priority(user_query, classification)

        # Update display recommendations based on intent
        filtered_display = {}

        # Start with original recommendations
        original_display = classification.get('display_components', {})

        # Apply intent-based filtering
        primary_components = priority_filtering['primary']['components']
        skip_components = priority_filtering['skip']['components']

        for component, should_display in original_display.items():
            if component in skip_components:
                filtered_display[component] = False
                logger.info(f"Skipping {component} due to intent priority")
            elif component in primary_components:
                filtered_display[component] = True
                logger.info(f"Prioritizing {component} for intent {intent_match.intent_type}")
            else:
                filtered_display[component] = should_display

        # Update classification with filtered components
        classification['display_components'] = filtered_display
        classification['intent_analysis'] = {
            'detected_intent': intent_match.intent_type,
            'confidence': intent_match.confidence,
            'priority_filtering': priority_filtering
        }

        logger.info(f"Intent-based filtering applied: {filtered_display}")
        return classification

    except Exception as e:
        logger.error(f"Intent-based filtering failed: {str(e)}, using original classification")
        return classification


# Alias for make_request to match http_sync usage in new code
http_sync = make_request

# Ensure these variables are available at module level for build_endpoint_tasks
# (They are already defined in ask_copilot, so move their definition up)
overview_base_url = os.getenv("OVERVIEW_BASE_URL", "https://api.quanvest.me/overview/company")
charts_base_url = os.getenv("CHARTS_BASE_URL", "https://api.quanvest.me/charts")
flask_url = os.getenv("FLASK_SERVER_URL", "http://localhost:5000")  # Default to local Flask server
financials_base_url = os.getenv("FINANCIALS_BASE_URL", "https://api.quanvest.me/financials")
ratio_base_url = os.getenv("RATIO_BASE_URL", "https://api.quanvest.me/ratios")
shareholding_base_url = os.getenv("SHAREHOLDING_BASE_URL", "https://api.quanvest.me/shareholding_pattern")

standard_headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
}
ngrok_headers = {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
    'X-API-Key': API_KEY
}


@router.post("/ask")
async def ask_copilot(request: CopilotRequest):
    """Enhanced copilot with multi-endpoint support"""
    request_start_time = time.time()
    logger.info("Copilot /ask endpoint called.")

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
            ngrok_headers,  # ← async version
            timeout=25
        )
        colab_call_duration = time.time() - colab_call_start_time
        logger.info(f"Flask /enhanced_retrieve call completed in {colab_call_duration:.2f} seconds.")

        enhanced_context_data = enhanced_response
        combined_context = enhanced_response.get('combined_context', '')
        classification = enhanced_response.get('classification', {})
        display_recommendations = classification.get('display_components', {})

        logger.info(f"Classification: {classification} ")
        logger.info(f"Display recommendations: {display_recommendations}")

    except Exception as e:
        logger.error(f"Enhanced retrieve failed: {str(e)}")
        enhanced_context_data = {"error": str(e)}

        # Fix: Don't use empty context, create minimal context from classification
        if "timeout" in str(e).lower():
            combined_context = f"Query classified as: {request.user_query}\nDataSource: hybrid analysis requested\nNote: Some context retrieval timed out but continuing with available data."
        else:
            combined_context = f"Processing query: {request.user_query}\nFallback context due to retrieval issues."

        display_recommendations = {
            "llm_response": True,
            "table": False,
            "chart": False,
            "company_overview": False,
            "shareholding": False
        }
        classification = {
            "required_sql_tables": [],
            "endpoint_type": "financials",
            "endpoint_mode": "base"
        }

        try:
            classification = filter_data_fetching_by_intent(classification, request.user_query)
            display_recommendations = classification.get('display_components', {})
            logger.info(f"Updated display recommendations after intent filtering: {display_recommendations}")
        except Exception as e:
            logger.error(f"Intent filtering failed: {str(e)}")

    
    # Step 2: Extract classification details
    endpoint_type = classification.get('endpoint_type', 'financials')
    endpoint_mode = classification.get('endpoint_mode', 'base')
    chart_endpoint_type = classification.get('chart_endpoint_type', 'parameters')
    chart_parameters = classification.get('chart_parameters', [])
    identified_parameters = classification.get('identified_parameters', {})
    required_sql_tables = classification.get('required_sql_tables', [])

    # Step 3: Determine company IDs
    company_ids_to_use = []
    resolved_companies = enhanced_context_data.get('resolved_companies', [])
    if resolved_companies:
        company_ids_to_use = get_company_numbers_from_db(resolved_companies)
        logger.info(f"Extracted company IDs: {company_ids_to_use}")

    # Step 4: Check if shareholding data is needed based on classification
    fetch_shareholding = 'shareholder' in required_sql_tables
    if fetch_shareholding:
        display_recommendations['shareholding'] = True
        logger.info("Shareholding data fetch enabled based on query classification")

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

    # Shareholding Pattern tasks (conditional) - Using classification data
    if fetch_shareholding and company_ids_to_use:
        for company_id in company_ids_to_use:
            if isinstance(company_id, int) and company_id > 0:
                shareholding_url = f"{shareholding_base_url}?company_number={company_id}"
                all_tasks_lambdas.append(
                    lambda url=shareholding_url: make_request(url, "GET", headers=standard_headers)
                )
                task_order.append('shareholding')
        logger.info(f"Added {len(company_ids_to_use)} shareholding pattern tasks")

    # Chart tasks (conditional with intelligent endpoint selection)
    if display_recommendations.get('chart', False) and company_ids_to_use and chart_parameters:
        chart_url = f"{charts_base_url}/{chart_endpoint_type}"
        chart_payload = prepare_chart_request(chart_endpoint_type, company_ids_to_use, chart_parameters)

        all_tasks_lambdas.append(
            lambda: http_sync(chart_url, "POST", chart_payload, standard_headers)
        )
        task_order.append('chart')
        logger.info(f"Added chart task for {chart_endpoint_type}")
    else:
        all_tasks_lambdas.append(lambda: {})
        task_order.append('chart')

    # Multi-endpoint financial data tasks
    if display_recommendations.get('table', False) and company_ids_to_use:
        endpoint_tasks = build_endpoint_tasks(classification, company_ids_to_use)

        for task_name, task_func in endpoint_tasks:
            all_tasks_lambdas.append(task_func)
            task_order.append(f'financial_{task_name}')

        logger.info(f"Added {len(endpoint_tasks)} financial endpoint tasks")
    else:
        all_tasks_lambdas.append(lambda: {})
        task_order.append('financial')

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
    shareholding_data = []
    chart_data = {}
    financial_data = []

    # Segment responses based on task_order
    response_idx = 0
    for task_type in task_order:
        if response_idx >= len(all_responses):
            break

        if task_type == 'overview':
            company_overviews.append(all_responses[response_idx])
            response_idx += 1
        elif task_type == 'shareholding':
            shareholding_data.append(all_responses[response_idx])
            response_idx += 1
        elif task_type == 'chart':
            chart_data = all_responses[response_idx]
            response_idx += 1
        elif task_type == 'financial':
            financial_data.append(all_responses[response_idx])
            response_idx += 1
    consolidated_financials = consolidate_financial_data(all_responses, task_order, classification)

    # Then replace your existing financial_data with:
    financial_data = consolidated_financials['financial_statements']
    ratios_data = consolidated_financials['ratios']
    shareholding_data = consolidated_financials['shareholding']  # Replaces your existing shareholding_data

    # Step 9: Return raw data if requested
    if request.raw_only:
        return {
            "llm_response": None,
            "enhanced_context_data": enhanced_context_data,
            "company_overviews": company_overviews,
            "shareholding_data": shareholding_data,
            "ratios_data": ratios_data,
            "chart_data": chart_data,
            "financial_data": financial_data,
            "display_recommendations": display_recommendations,
            "classification": classification
        }

    # Step 10: Prepare data context for Gemini (future custom templates)
    context_data = {
        "endpoint_type": endpoint_type,
        "endpoint_mode": endpoint_mode,
        "identified_parameters": identified_parameters,
        "required_sql_tables": required_sql_tables,
        "company_count": len(company_ids_to_use) if company_ids_to_use else 0,
        "has_charts": bool(chart_data and not chart_data.get('error')),
        "has_ratios": bool(ratios_data) and any(is_valid_response(d) for d in ratios_data.values()),
        "has_financials": bool(financial_data) and any(
            is_valid_response(d)
            for table_data in financial_data.values()
            for d in table_data),
        "has_shareholding": bool(
            shareholding_data and not any(isinstance(d, dict) and d.get('error') for d in shareholding_data)),
        "query_type": classification.get('query_type', 'comprehensive')
    }

    # Step 11: Generate LLM response
    try:
        gemini_call_start_time = time.time()
        gemini_result = await get_copilot_response(
            user_query=request.user_query,
            refined_context=combined_context,
            context_data=context_data  # Pass context data for future template selection
        )
        gemini_call_duration = time.time() - gemini_call_start_time
        logger.info(f"Gemini API call completed in {gemini_call_duration:.2f} seconds.Gemini Response:{gemini_result.get("response", "")}")
    except Exception as e:
        logger.error(f"Gemini call failed: {str(e)}")
        return {
            "error": f"Gemini call failed: {str(e)}",
            "enhanced_context_data": enhanced_context_data,
            "company_overviews": company_overviews,
            "shareholding_data": shareholding_data,
            "ratios_data": ratios_data,
            "chart_data": chart_data,
            "financial_data": financial_data,
            "display_recommendations": display_recommendations,
            "classification": classification,
            "company_ids": company_ids_to_use
        }

    # Step 12: Process LLM response for structured output
    processed_llm_response = process_llm_response(
        llm_response_text=gemini_result.get("response", ""),
        display_recommendations=display_recommendations,
        classification=classification,
        company_overviews=company_overviews,
        shareholding_data=shareholding_data,
        ratios_data=ratios_data,
        chart_data=chart_data,
        financial_data=financial_data
    )

    # Step 13: Return comprehensive response
    total_request_duration = time.time() - request_start_time
    logger.info(f"Total copilot request processed in {total_request_duration:.2f} seconds.")
    return {
        "llm_response": processed_llm_response,
        "enhanced_context_data": enhanced_context_data,
        "company_overviews": company_overviews,
        "shareholding_data": shareholding_data,
        "ratios_data": ratios_data,
        "chart_data": chart_data,
        "financial_data": financial_data,
        "display_recommendations": display_recommendations,
        "classification": classification,
        "company_ids": company_ids_to_use,
        "context_info": {
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
                "shareholding_patterns": len(
                    [d for d in shareholding_data if not (isinstance(d, dict) and d.get('error'))]),
                "charts": 1 if chart_data and not chart_data.get('error') else 0,
                "financial_tables": len([d for d in financial_data if not (isinstance(d, dict) and d.get('error'))])
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
    shareholding_data: List,
    ratios_data: Dict,
    chart_data: Dict,
    financial_data: Dict
) -> List[Any]:
    """
    Process the LLM response to split it by placeholders and inject metadata.
    """
    placeholder_patterns = [
        '~OVERVIEW_STATS_TABLE~', '~COMPARISON_TABLE~', '~SHAREHOLDING_TABLE~',
        '~RATIOS_TABLE~', '~COMPREHENSIVE_RATIOS_TABLE~', '~FINANCIAL_PARAMETERS_TABLE~',
        '~CHARTS_SECTION~', '~FINANCIAL_DATA_TABLE~'
    ]

    # Create a regex to find any of the placeholders
    regex = re.compile(f"({'|'.join(re.escape(p) for p in placeholder_patterns)})")
    parts = regex.split(llm_response_text)

    output = []
    processed_placeholders = set()  # Keep track of processed placeholders

    for part in parts:
        if not part:
            continue

        if part in placeholder_patterns:
            placeholder = part
            if placeholder in processed_placeholders:
                # If this placeholder has been processed, skip it to avoid duplication
                continue

            metadata = {"placeholder": placeholder, "type": "error", "data": "Error loading table/chart"}

            # Determine the type and check for data availability
            if placeholder == '~CHARTS_SECTION~':
                if display_recommendations.get('chart', False) and chart_data and not chart_data.get('error'):
                    metadata = {
                        "placeholder": placeholder,
                        "type": "chart",
                        "chart_type": classification.get('chart_endpoint_type', 'parameters'),
                        "parameters": classification.get('chart_parameters', [])
                    }
                else:
                    metadata["data"] = "Chart data is not available or not recommended for display."

            else:  # It's a table
                table_type = "unknown"
                data_available = False

                if placeholder == '~OVERVIEW_STATS_TABLE~':
                    table_type = "company_overview"
                    if display_recommendations.get('company_overview', False) and any(
                            is_valid_response(d) for d in company_overviews):
                        data_available = True

                elif placeholder == '~SHAREHOLDING_TABLE~':
                    table_type = "shareholding"
                    if display_recommendations.get('shareholding', False) and any(
                            is_valid_response(d) for d in shareholding_data):
                        data_available = True

                elif placeholder in ['~RATIOS_TABLE~', '~COMPREHENSIVE_RATIOS_TABLE~', '~COMPARISON_TABLE~']:
                    table_type = "ratios"
                    if display_recommendations.get('table', False) and any(
                            is_valid_response(d) for d in ratios_data.values()):
                        data_available = True

                elif placeholder in ['~FINANCIAL_PARAMETERS_TABLE~', '~FINANCIAL_DATA_TABLE~']:
                    table_type = "financials"
                    if display_recommendations.get('table', False) and any(
                            is_valid_response(d) for table_data in financial_data.values() for d in table_data):
                        data_available = True

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
            processed_placeholders.add(placeholder)  # Mark as processed
        else:
            output.append(part.strip())

    # Filter out empty strings that may result from splitting
    return [item for item in output if item]


def consolidate_financial_data(results: List, task_order: List[str], classification: Dict) -> Dict:
    """
    Consolidate data from multiple endpoints into organized structure
    """
    consolidated = {
        'company_overviews': [],
        'chart_data': {},
        'financial_statements': {},
        'ratios': {},
        'shareholding': []
    }

    response_idx = 0
    for task_type in task_order:
        if response_idx >= len(results):
            break

        if task_type == 'overview':
            consolidated['company_overviews'].append(results[response_idx])
        elif task_type == 'chart':
            consolidated['chart_data'] = results[response_idx]
        elif task_type.startswith('financial_'):
            # Parse the task name to categorize data
            parts = task_type.split('_')
            if len(parts) >= 3:
                data_type = parts[1]  # financials, ratios, shareholding
                table_or_id = parts[2]

                if data_type == 'financials':
                    table_name = table_or_id
                    if table_name not in consolidated['financial_statements']:
                        consolidated['financial_statements'][table_name] = []
                    consolidated['financial_statements'][table_name].append(results[response_idx])
                elif data_type == 'ratios':
                    consolidated['ratios'][table_or_id] = results[response_idx]
                elif data_type == 'shareholding':
                    consolidated['shareholding'].append(results[response_idx])

        response_idx += 1

    return consolidated
