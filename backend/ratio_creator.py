#!/usr/bin/env python3
"""
Enhanced Financial Ratio Calculator
Calculates comprehensive financial ratios including stock price-based ratios
"""

import psycopg2
from typing import Dict, Optional, Any
import re
from datetime import datetime, timedelta
from backend.db_setup import connect_to_db
import logging

# Configure basic logging (if you want more control, configure in a central place)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Company numbers to process
COMPANY_NUMBERS = [
    42, 4, 96, 70, 80, 83, 10, 7, 9, 90, 45, 15, 6, 26, 12, 57, 24, 81, 19, 61,
    101, 93, 36, 69, 25, 31, 94, 30, 21, 102, 14, 97, 3, 66, 17, 20, 22, 59, 1,
    76, 5, 18, 64, 2, 55, 23, 56, 11, 8
]

# Year columns and their corresponding years for stock price lookup
YEAR_COLUMNS = ['mar_16', 'mar_17', 'mar_18', 'mar_19', 'mar_20', 'mar_21', 'mar_22', 'mar_23', 'mar_24', 'mar_25']
YEAR_MAPPING = {
    'mar_16': 2016, 'mar_17': 2017, 'mar_18': 2018, 'mar_19': 2019, 'mar_20': 2020,
    'mar_21': 2021, 'mar_22': 2022, 'mar_23': 2023, 'mar_24': 2024, 'mar_25': 2025
}

# Enhanced parameter mapping
PARAMETER_MAPPING = {
    # From Balance Sheet
    'total_assets': 'Total Assets',
    'total_liabilities': 'Total Liabilities',
    'total_equity': 'Total Equity',
    'equity_share_capital': 'Common Stock, Total',
    'reserves': 'Retained Earnings',
    'cash_and_bank': 'Cash And Equivalents',
    'receivables': 'Accounts Receivable, Total',
    'inventory': 'Inventory',
    'current_assets': 'Total Current Assets',
    'current_liabilities': 'Total Current Liabilities',
    'net_block': 'Net Property Plant And Equipment',
    'borrowings': 'Long-Term Debt',
    'short_term_borrowings': 'Short-term Borrowings',
    'investments': 'Total investments',
    'other_assets': 'Other Long-Term Assets, Total',
    'payables': 'Accounts Payable, Total',
    'minority_share': 'Minority Interest',

    # From Profit & Loss
    'net_profit': 'Net Income',
    'sales': 'Total Revenues',
    'operating_income': 'Operating Income',
    'profit_before_tax': 'EBT, Excl. Unusual Items',
    'interest': 'Interest Expense, Total',
    'tax': 'Income Tax Expense',
    'depreciation': 'Depreciation & Amortization',
    'cost_of_goods_sold': 'Cost of Goods Sold, Total',
    'gross_profit': 'Gross Profit',
    'ebitda': 'EBITDA',
    'other_income': 'Other Revenues, Total',
    'employee_cost': 'Salaries And Other Employee Benefits',
    'other_expenses': 'Other Operating Expenses, Total',
    'eps': 'EPS',
    'shares_outstanding': 'Total Shares Outstanding',
    'interest_and_investment_income': 'Interest And Investment Income',

    # From Cashflow
    'cash_from_operating_activity': 'Cash from Operations',
    'cash_from_investing_activity': 'Cash from Investing',
    'cash_from_financing_activity': 'Cash from Financing',
    'capital_expenditure': 'Capital Expenditure',
    'net_cash_flow': 'Net Change in Cash',
    'dividends_paid': 'Common Dividends Paid',
    'debt_issued': 'Total Debt Issued',
    'debt_repaid': 'Total Debt Repaid'
}

# Comprehensive ratio formulas with percentage indicators
RATIO_FORMULAS = {
    # Profitability Ratios (mostly percentages)
    'net_profit_margin': {'formula': 'net_profit / sales', 'is_percentage': True},
    'gross_profit_margin': {'formula': 'gross_profit / sales', 'is_percentage': True},
    'operating_profit_margin': {'formula': 'operating_income / sales', 'is_percentage': True},
    'ebitda_margin': {'formula': 'ebitda / sales', 'is_percentage': True},
    'ebit_margin': {'formula': 'operating_income / sales', 'is_percentage': True},
    # Using Operating Income as EBIT proxy
    'employee_cost_ratio': {'formula': 'employee_cost / sales', 'is_percentage': True},
    'other_expense_ratio': {'formula': 'other_expenses / sales', 'is_percentage': True},
    'depreciation_to_sales': {'formula': 'depreciation / sales', 'is_percentage': True},
    'effective_tax_rate': {'formula': 'tax / profit_before_tax', 'is_percentage': True},
    'other_income_to_sales': {'formula': 'other_income / sales', 'is_percentage': True},
    'minority_interest_to_net_profit': {'formula': 'minority_share / net_profit', 'is_percentage': True},
    'depreciation_to_net_profit': {'formula': 'depreciation / net_profit', 'is_percentage': True},
    'effective_interest_burden': {'formula': 'interest / profit_before_tax', 'is_percentage': True},
    'tax_burden': {'formula': 'tax / profit_before_tax', 'is_percentage': True},

    # Return Ratios (percentages)
    'return_on_assets': {'formula': 'net_profit / total_assets', 'is_percentage': True},
    'return_on_equity': {'formula': 'net_profit / total_equity', 'is_percentage': True},
    'return_on_investment': {'formula': 'net_profit / (total_equity + borrowings)', 'is_percentage': True},
    'cash_return_on_equity': {'formula': 'cash_from_operating_activity / total_equity', 'is_percentage': True},
    'cash_return_on_assets': {'formula': 'cash_from_operating_activity / total_assets', 'is_percentage': True},

    # Liquidity Ratios (ratios, not percentages)
    'current_ratio': {'formula': 'current_assets / current_liabilities', 'is_percentage': False},
    'quick_ratio': {'formula': '(current_assets - inventory) / current_liabilities', 'is_percentage': False},
    'cash_ratio': {'formula': 'cash_and_bank / current_liabilities', 'is_percentage': False},

    # Leverage/Solvency Ratios
    'debt_to_equity': {'formula': 'borrowings / total_equity', 'is_percentage': False},
    'debt_to_assets': {'formula': 'total_liabilities / total_assets', 'is_percentage': True},
    'equity_ratio': {'formula': 'total_equity / total_assets', 'is_percentage': True},
    'financial_leverage': {'formula': 'total_assets / total_equity', 'is_percentage': False},
    'interest_coverage': {'formula': 'operating_income / interest', 'is_percentage': False},
    'reserves_to_equity': {'formula': 'reserves / equity_share_capital', 'is_percentage': False},
    'shareholder_funds_to_total_assets': {'formula': 'total_equity / total_assets', 'is_percentage': True},

    # Efficiency/Activity Ratios
    'asset_turnover': {'formula': 'sales / total_assets', 'is_percentage': False},
    'receivables_turnover': {'formula': 'sales / receivables', 'is_percentage': False},
    'inventory_turnover': {'formula': 'cost_of_goods_sold / inventory', 'is_percentage': False},
    'fixed_asset_turnover': {'formula': 'sales / net_block', 'is_percentage': False},
    'investment_to_assets_ratio': {'formula': 'investments / total_assets', 'is_percentage': True},
    'asset_efficiency_ratio': {'formula': 'sales / total_assets', 'is_percentage': False},  # Same as asset_turnover

    # Cash Flow Ratios
    'operating_cash_flow_ratio': {'formula': 'cash_from_operating_activity / current_liabilities',
                                  'is_percentage': False},
    'cash_flow_margin': {'formula': 'cash_from_operating_activity / sales', 'is_percentage': True},
    'free_cash_flow': {'formula': 'cash_from_operating_activity - capital_expenditure', 'is_percentage': False},
    'cash_flow_to_debt': {'formula': 'cash_from_operating_activity / borrowings', 'is_percentage': False},
    'capex_to_operating_cash_flow': {'formula': 'capital_expenditure / cash_from_operating_activity',
                                     'is_percentage': True},
    'dividend_coverage_ratio': {'formula': 'cash_from_operating_activity / dividends_paid', 'is_percentage': False},
    'net_income_to_operating_cf_ratio': {'formula': 'net_profit / cash_from_operating_activity',
                                         'is_percentage': False},
    'net_profit_to_cash_flow_conversion': {'formula': 'net_profit / cash_from_operating_activity',
                                           'is_percentage': False},

    # Per Share Ratios (absolute values)
    'earnings_per_share': {'formula': 'net_profit / shares_outstanding', 'is_percentage': False},
    'book_value_per_share': {'formula': 'total_equity / shares_outstanding', 'is_percentage': False},
    'dividend_per_share': {'formula': 'dividends_paid / shares_outstanding', 'is_percentage': False},
    'cash_earnings_per_share': {'formula': '(net_profit + depreciation) / shares_outstanding', 'is_percentage': False},

    # Other Important Ratios
    'dividend_payout_ratio': {'formula': 'dividends_paid / net_profit', 'is_percentage': True},
    'retention_ratio': {'formula': '(net_profit - dividends_paid) / net_profit', 'is_percentage': True},
    'retained_earnings_ratio': {'formula': '(net_profit - dividends_paid) / net_profit', 'is_percentage': True},
    'dividend_payout_coverage': {'formula': 'cash_from_operating_activity / dividends_paid', 'is_percentage': False},

    # Calculated Working Capital Ratios
    'net_working_capital': {'formula': 'current_assets - current_liabilities', 'is_percentage': False},
    'working_capital_to_total_assets': {'formula': '(current_assets - current_liabilities) / total_assets',
                                        'is_percentage': True},

    # Additional Derived Ratios
    'sustainable_growth_rate': {'formula': '(net_profit / total_equity) * ((net_profit - dividends_paid) / net_profit)',
                                'is_percentage': True},
    'retained_earnings_to_equity': {'formula': '(net_profit - dividends_paid) / total_equity', 'is_percentage': True},

    # Market-based ratios (will be calculated separately with stock price data)
    'dividend_yield': {'formula': 'market_based', 'is_percentage': True},
    'price_to_earnings_ratio': {'formula': 'market_based', 'is_percentage': False},
    'price_to_book_value': {'formula': 'market_based', 'is_percentage': False}
}


def safe_float_convert(value):
    """Safely convert text value to float, return None if conversion fails"""
    if value is None or value == '—' or value == 'None':
        return None
    try:
        cleaned_value = str(value).replace(',', '').replace('(', '-').replace(')', '').strip()
        if cleaned_value == '' or cleaned_value == '-':
            return None
        return float(cleaned_value)
    except (ValueError, TypeError):
        return None


def get_parameter_value(conn, table_name: str, company_number: int, parameter: str, year_column: str) -> Optional[
    float]:
    """Get parameter value from specified table for given company and year"""
    try:
        cursor = conn.cursor()
        logger.debug(f"Fetching '{parameter}' from '{table_name}' for company_number={company_number} year_col={year_column}")
        query = f"""
        SELECT {year_column}
        FROM {table_name}
        WHERE company_number = %s AND account = %s
        """
        cursor.execute(query, (company_number, parameter))
        result = cursor.fetchone()
        if result and result[0]:
            return safe_float_convert(result[0])
        return None
    except Exception as e:
        logger.error(f"Error fetching {parameter} from {table_name} for {company_number}: {e}")
        return None


def find_parameter_in_tables(conn, company_number: int, parameter: str, year_column: str) -> Optional[float]:
    """Search for parameter across all three tables"""
    tables = ['balance_sheet', 'profit_and_loss', 'cashflow']
    for table in tables:
        value = get_parameter_value(conn, table, company_number, parameter, year_column)
        if value is not None:
            return value
    return None


def get_stock_price_for_year(conn, company_number: int, year: int) -> Optional[float]:
    """Get stock price closest to March 31st of the given year"""
    try:
        cursor = conn.cursor()
        start_date = f"{year}-03-27"
        end_date = f"{year}-04-04"

        query = """
        SELECT value 
        FROM stock_price 
        WHERE company_number = %s 
        AND date BETWEEN %s AND %s 
        ORDER BY ABS(date - %s::date)
        LIMIT 1
        """
        cursor.execute(query, (company_number, start_date, end_date, f"{year}-03-31"))
        result = cursor.fetchone()
        if result:
            return safe_float_convert(result[0])
        return None
    except Exception as e:
        print(f"Error fetching stock price for company {company_number}, year {year}: {e}")
        conn.rollback()
        return None


def calculate_ratio(formula: str, parameters: Dict[str, float]) -> Optional[float]:
    """Calculate ratio using the formula string and parameter values"""
    try:
        calc_formula = formula
        for param_name, param_value in parameters.items():
            if param_value is not None:
                calc_formula = calc_formula.replace(param_name, str(param_value))


        if re.search(r'[a-zA-Z_]', calc_formula):
            # print(f"Invalid formula detected: {calc_formula}")
            return None

        try:
            result = eval(calc_formula)
            if result == float('inf') or result == float('-inf') or str(result) == 'nan':
                return None
            return round(result, 6)
        except ZeroDivisionError:
            return None
        except:
            return None
    except Exception as e:
        return None


def calculate_market_based_ratios(conn, company_number: int, year_column: str, parameters: Dict[str, float]) -> Dict[
    str, float]:
    """Calculate market-based ratios using stock price data"""
    market_ratios = {}
    year = YEAR_MAPPING.get(year_column)
    if not year:
        return market_ratios

    stock_price = get_stock_price_for_year(conn, company_number, year)
    if stock_price is None:
        return market_ratios

    # Calculate market-based ratios
    if parameters.get('dividends_paid') and parameters.get('shares_outstanding'):
        dividend_per_share = parameters['dividends_paid'] / parameters['shares_outstanding']
        market_ratios['dividend_yield'] = (dividend_per_share / stock_price) * 100  # Percentage

    if parameters.get('net_profit') and parameters.get('shares_outstanding'):
        eps = parameters['net_profit'] / parameters['shares_outstanding']
        if eps != 0:
            market_ratios['price_to_earnings_ratio'] = stock_price / eps

    if parameters.get('total_equity') and parameters.get('shares_outstanding'):
        book_value_per_share = parameters['total_equity'] / parameters['shares_outstanding']
        if book_value_per_share != 0:
            market_ratios['price_to_book_value'] = stock_price / book_value_per_share

    return market_ratios


def get_all_parameters_for_company_year(conn, company_number: int, year_column: str) -> Dict[str, float]:
    """Get all available parameters for a company for a specific year"""
    parameters = {}
    for old_name, new_name in PARAMETER_MAPPING.items():
        value = find_parameter_in_tables(conn, company_number, new_name, year_column)
        if value is not None:
            parameters[old_name] = value
    return parameters


def calculate_all_ratios_for_company_year(conn, company_number: int, year_column: str) -> Dict[str, Dict[str, Any]]:
    """Calculate all possible ratios for a company for a specific year"""
    parameters = get_all_parameters_for_company_year(conn, company_number, year_column)
    if not parameters:
        return {}

    calculated_ratios = {}

    # Calculate standard ratios
    for ratio_name, ratio_info in RATIO_FORMULAS.items():
        if ratio_info['formula'] == 'market_based':
            continue  # Handle separately

        ratio_value = calculate_ratio(ratio_info['formula'], parameters)
        if ratio_value is not None:
            calculated_ratios[ratio_name] = {
                'value': ratio_value,
                'is_percentage': ratio_info['is_percentage']
            }

    # Calculate market-based ratios
    market_ratios = calculate_market_based_ratios(conn, company_number, year_column, parameters)
    for ratio_name, ratio_value in market_ratios.items():
        calculated_ratios[ratio_name] = {
            'value': ratio_value,
            'is_percentage': RATIO_FORMULAS[ratio_name]['is_percentage']
        }

    return calculated_ratios


def insert_ratios_to_db(conn, company_number: int, ratios_by_year: Dict[str, Dict[str, Dict[str, Any]]]):
    """Insert calculated ratios into financial_ratios table with percentage indicator"""
    try:
        cursor = conn.cursor()

        # Get all unique ratio names across all years
        all_ratio_names = set()
        for year_ratios in ratios_by_year.values():
            all_ratio_names.update(year_ratios.keys())

        # Insert each ratio as a separate row
        for ratio_name in all_ratio_names:
            # Prepare values for all years
            values = [company_number, ratio_name]

            # Determine if this ratio is a percentage (use first available year's data)
            is_percentage = False
            for year_col in YEAR_COLUMNS:
                if year_col in ratios_by_year and ratio_name in ratios_by_year[year_col]:
                    is_percentage = ratios_by_year[year_col][ratio_name]['is_percentage']
                    break

            # Add values for each year column
            for year_col in YEAR_COLUMNS:
                ratio_data = ratios_by_year.get(year_col, {}).get(ratio_name)
                ratio_value = ratio_data['value'] if ratio_data else None
                if ratio_value is not None:
                    values.append(f"{ratio_value:.6f}")
                else:
                    values.append(None)

            # Add percentage indicator
            values.append(is_percentage)

            # Create insert query with PostgreSQL UPSERT syntax
            columns = 'company_number, name, ' + ', '.join(YEAR_COLUMNS) + ', percent_or_not'
            placeholders = ', '.join(['%s' for _ in values])

            insert_query = f"""
            INSERT INTO financial_ratios ({columns})
            VALUES ({placeholders})
            ON CONFLICT (company_number, name) DO UPDATE SET
            {', '.join([f'{col} = EXCLUDED.{col}' for col in YEAR_COLUMNS])},
            percent_or_not = EXCLUDED.percent_or_not
            """

            cursor.execute(insert_query, values)

        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting ratios for company {company_number}: {e}")
        conn.rollback()
        return False

def process_single_company(conn, company_number: int) -> bool:
    """Process a single company - calculate all ratios for all years"""
    logger.info(f"Starting ratio calculation for company_number={company_number}")
    ratios_by_year = {}
    total_ratios_calculated = 0

    # Calculate ratios for each year
    for year_column in YEAR_COLUMNS:
        year_ratios = calculate_all_ratios_for_company_year(conn, company_number, year_column)
        ratios_by_year[year_column] = year_ratios
        total_ratios_calculated += len(year_ratios)
        logger.info(f"Company {company_number}, {year_column}: {len(year_ratios)} ratios")

    if total_ratios_calculated > 0:
        success = insert_ratios_to_db(conn, company_number, ratios_by_year)
        if success:
            logger.info(f"Inserted {total_ratios_calculated} ratio entries for company {company_number}")
            return True
        else:
            logger.warning(f"Failed to insert ratios for company {company_number}")
            return False
    else:
        logger.warning(f"No ratios could be calculated for company {company_number}")
        return False


def main():
    """Main function to process all companies and calculate financial ratios"""
    logger.info("=== Enhanced Financial Ratio Calculation Started ===")
    logger.debug(f"Company list count: {len(COMPANY_NUMBERS)}")
    logger.debug(f"Ratio formulas count: {len(RATIO_FORMULAS)}")
    print(f"Processing {len(COMPANY_NUMBERS)} companies")
    print(f"Calculating {len(RATIO_FORMULAS)} different ratios")
    print(f"For years: {', '.join(YEAR_COLUMNS)}")
    print("=" * 50)

    successful_companies = 0
    failed_companies = 0

    try:
        conn = connect_to_db()

        for company_number in COMPANY_NUMBERS:
            try:
                success = process_single_company(conn, company_number)
                if success:
                    successful_companies += 1
                else:
                    failed_companies += 1
            except Exception as e:
                print(f"Error processing company {company_number}: {e}")
                failed_companies += 1

        conn.close()
    except Exception as e:
        print(f"Database connection error: {e}")
        return False

    print("=" * 50)
    print("=== Processing Summary ===")
    print(f"Successful companies: {successful_companies}")
    print(f"Failed companies: {failed_companies}")
    print(f"Total companies processed: {successful_companies + failed_companies}")
    return True


if __name__ == "__main__":
    main()
