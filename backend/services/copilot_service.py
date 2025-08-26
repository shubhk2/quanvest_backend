import os
import asyncio
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from jinja2 import Template

load_dotenv()


def strip_md_tables(text: str, default_placeholder: str = "~FINANCIAL_DATA_TABLE~") -> str:
    """Remove any Markdown table the model still sneaks in and replace with placeholder"""
    md_table_regex = re.compile(r"^(?:\s*\|.*\|\s*$\n?)+", re.MULTILINE)
    if md_table_regex.search(text):
        text = md_table_regex.sub("", text)
        paras = text.split("\n\n")
        if default_placeholder not in text:
            if paras:
                paras.insert(1, default_placeholder)
            text = "\n\n".join(paras)
    return text


def enforce_bullet_format(text: str) -> str:
    """Convert paragraphs to bullet points"""
    text = re.sub(r'^\d+\.\s+', '- ', text, flags=re.MULTILINE)

    if '\n\n' in text and not text.strip().startswith('-'):
        paragraphs = text.split('\n\n')
        bullet_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith('-') and not para.startswith('~') and not para.startswith('**'):
                sentences = para.split('. ')
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence and not sentence.startswith('-'):
                        bullet_paragraphs.append(f"- {sentence}")
            else:
                bullet_paragraphs.append(para)
        return '\n\n'.join(bullet_paragraphs)
    return text


def highlight_key_parameters(text: str, params: list) -> str:
    """Bold key parameters in response"""
    for param in params:
        if param and len(param) > 2:
            text = re.sub(fr'\b{re.escape(param)}\b', f'**{param}**', text, flags=re.IGNORECASE)
    return text


def determine_template_type(user_query: str, context_data: dict = None) -> str:
    """Enhanced template selection with comprehensive query type support"""
    query_lower = user_query.lower()

    # Edge case detection
    edge_cases = {
        'news': ['news', 'recent news', 'latest news', 'breaking news'],
        'forecasting': ['forecast', 'forecasting', 'predict', 'prediction', 'future', 'valuation',
                        'modelling', 'intrinsic value', 'dcf', 'fair value'],
        'stock_market': ['stock price', 'share price', 'market data', 'stock market', 'trading',
                         'volume', 'technical analysis'],
        'non_finance': ['weather', 'sports', 'entertainment', 'politics', 'technology news',
                        'india vs pakistan']
    }

    for case_type, keywords in edge_cases.items():
        if any(keyword in query_lower for keyword in keywords):
            return case_type

    if not context_data:
        return 'default_financial'

    # Extract context data
    query_type = context_data.get('query_type', 'company_overview')
    company_count = context_data.get('company_count', 0)
    is_comparison = context_data.get('is_comparison', False)
    has_charts = context_data.get('has_charts', False)
    has_financials = context_data.get('has_financials', False)
    has_shareholding = context_data.get('has_shareholding', False)
    has_dividend = context_data.get('has_dividend', False)
    has_corporate_governance = context_data.get('has_corporate_governance', False)

    # Priority-based template selection using query_type

    # 1. Domain-specific templates (highest priority)
    if query_type == 'stock_analysis':
        return 'stock_analysis'
    elif query_type == 'dividend_analysis':
        return 'dividend_analysis'
    elif query_type == 'insider_trading_analysis':
        return 'insider_trading_analysis'
    elif query_type == 'rpt_analysis':
        return 'rpt_analysis'
    elif query_type == 'pledged_data_analysis':
        return 'pledged_data_analysis'
    elif query_type == 'corporate_governance':
        return 'corporate_governance'
    elif query_type == 'shareholder_info':
        return 'shareholding_analysis'

    # 2. Comparison handling (second priority)
    if is_comparison or company_count > 1:
        if query_type == 'ratio_analysis':
            return 'multi_company_ratios'
        else:
            return 'comparative_analysis'

    # 3. Chart-focused templates
    if has_charts:
        if query_type == 'stock_analysis':
            return 'stock_chart_analysis'
        elif 'trend' in query_lower or 'growth' in query_lower:
            return 'trend_analysis_with_charts'
        elif has_financials:
            return 'comprehensive_with_charts'
        else:
            return 'chart_focused_analysis'

    # 4. Financial statement specific templates
    if query_type == 'ratio_analysis':
        if context_data.get('endpoint_mode') == 'parameters':
            return 'ratio_analysis_specific'
        else:
            return 'ratio_analysis_comprehensive'
    elif query_type == 'balance_sheet':
        return 'balance_sheet_analysis'
    elif query_type == 'profit_and_loss':
        return 'profit_loss_analysis'
    elif query_type == 'cash_flow':
        return 'cash_flow_analysis'
    elif query_type == 'comprehensive':
        return 'comprehensive_financial_analysis'

    # 5. Company overview and defaults
    if query_type == 'company_overview' or 'overview' in query_lower:
        return 'company_overview'
    elif context_data.get('endpoint_mode') == 'parameters':
        return 'parameter_specific_analysis'
    elif has_financials:
        return 'tabular_analysis'
    else:
        return 'default_financial'


def get_template_content(template_type: str) -> str:
    """Return enhanced Jinja2 template content with comprehensive template coverage"""

    # System instruction for all templates
    system_instruction = (
        "SYSTEM: Only answer the user's real query if the provided context is relevant and sufficient. "
        "If the context is not relevant or does not contain the required information, do NOT fabricate or repeat the context. "
        "Always follow the rules and formatting instructions for the current query type. "
        "If the context is not needed for the query, ignore it and answer as per the rules. "
        "Do not provide a response just because context is present; respond only if it is appropriate and required.\n\n"
        "CRITICAL PLACEHOLDER RULES:\n"
        "- Insert each placeholder exactly once and only where shown in the template below.\n"
        "- Do not invent or duplicate placeholders.\n"
        "- Placeholders must appear on their own line with no surrounding prose or bullets.\n\n"
    )

    templates = {
        'news': """
Sorry, we currently don't provide news analysis or recent news updates. Our platform focuses on financial statement analysis, ratios, and company fundamentals.

For the latest company news and market updates, please refer to financial news sources or our upcoming news section.
""",

        'forecasting': """
Sorry, we don't provide forecasting, valuation modeling, or intrinsic value calculations at this time. Our platform specializes in historical financial analysis and ratio computations.

For valuation models and forecasting, please consult specialized financial modeling tools or professional analysts.
""",

        'stock_market': """
For real-time stock prices, trading data, and market information, please visit our dedicated **Stock Data** page at `/stock_data`.

Our current analysis focuses on fundamental financial data from annual reports and financial statements.
""",

        'non_finance': """
Sorry, this doesn't appear to be a finance-related question. Our platform specializes in financial analysis, company fundamentals, and investment metrics.

Please ask questions related to:
- Company financial performance
- Financial ratios and metrics
- Balance sheet, income statement, or cash flow analysis
- Shareholding patterns
- Company comparisons
""",

        'company_overview': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my analysis to compare multiple companies while using this single-company template format.
{% endif %}

IMPORTANT • Present all analysis in bullet points. Do not write paragraphs.

You are a financial analyst providing company overview analysis.

User Query: "{{question}}"

**Key Analysis Framework:**

~OVERVIEW_STATS_TABLE~

**Financial Analysis:**

- **Key Performance Highlights**
  - Revenue and profitability trends
  - Market position and competitive advantages
  - Financial stability indicators

- **Operational Efficiency**
  - Asset utilization metrics
  - Working capital management
  - Cost control effectiveness

- **Investment Perspective**
  - Growth prospects and sustainability
  - Risk factors and mitigation
  - Valuation considerations

**Context:** {{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on strategic insights not covered in overview table
- Use specific numbers when available
- Present all analysis as concise bullet points
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'stock_analysis': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my stock analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present stock analysis in bullet points only

You are analyzing stock price movements and market data.

User Query: "{{question}}"

**Stock Performance Analysis:**

~STOCK_CHART_SECTION~

**Market Analysis:**

- **Price Trends**
  - Current price trajectory and momentum
  - Key support and resistance levels
  - Volume analysis and market sentiment

- **Technical Indicators**
  - Moving average analysis (DMA50/DMA200)
  - Price volatility patterns
  - Trading volume trends

- **Performance Context**
  - Relative performance vs market indices
  - Peer comparison within sector
  - Historical performance benchmarks

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key technical terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on technical and price action insights
- Reference specific price levels and trends
- Use bullet points for all analysis
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'dividend_analysis': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my dividend analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present dividend analysis in bullet points only

You are analyzing dividend policies and distributions.

User Query: "{{question}}"

**Dividend Analysis:**

~DIVIDEND_TABLE~

**Dividend Assessment:**

- **Dividend Policy**
  - Current dividend yield and payout ratio
  - Dividend growth history and sustainability
  - Policy consistency and management commitment

- **Financial Capacity**
  - Cash flow adequacy for dividend payments
  - Earnings coverage and stability
  - Balance sheet strength supporting dividends

- **Investor Implications**
  - Income generation potential
  - Total return considerations
  - Dividend reinvestment opportunities

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key dividend terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on dividend sustainability and policy
- Reference specific dividend rates and dates
- Use bullet points for all analysis
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'insider_trading_analysis': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my insider trading analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present insider trading analysis in bullet points only

You are analyzing insider trading patterns and implications.

User Query: "{{question}}"

**Insider Trading Data:**

~INSIDER_TRADING_TABLE~

**Insider Activity Analysis:**

- **Trading Patterns**
  - Recent insider buying vs selling activity
  - Transaction volumes and frequencies
  - Key insider participants (promoters, directors)

- **Market Signals**
  - What insider activity suggests about company prospects
  - Correlation with stock price movements
  - Management confidence indicators

- **Governance Implications**
  - Compliance with regulatory requirements
  - Transparency in insider disclosures
  - Impact on investor confidence

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key trading terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on patterns and implications
- Reference specific transaction details
- Use bullet points for all analysis
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'rpt_analysis': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my RPT analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present RPT analysis in bullet points only

You are analyzing Related Party Transactions.

User Query: "{{question}}"

**Related Party Transactions:**

~RPT_TABLE~

**RPT Analysis:**

- **Transaction Overview**
  - Types and nature of related party transactions
  - Transaction volumes and materiality
  - Key related parties involved

- **Business Rationale**
  - Commercial justification for transactions
  - Arms-length pricing verification
  - Strategic business benefits

- **Governance Assessment**
  - Board approval processes
  - Independent director oversight
  - Disclosure quality and transparency

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key RPT terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on transaction fairness and governance
- Reference specific transaction types and amounts
- Use bullet points for all analysis
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'pledged_data_analysis': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my pledged data analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present pledged data analysis in bullet points only

You are analyzing share pledging patterns and implications.

User Query: "{{question}}"

**Pledged Share Data:**

~PLEDGED_DATA_TABLE~

**Pledging Analysis:**

- **Pledging Overview**
  - Current pledge levels and trends
  - Promoter vs institutional pledging
  - Pledge release patterns

- **Financial Implications**
  - Liquidity and financing needs
  - Debt servicing capabilities
  - Impact on ownership control

- **Risk Assessment**
  - Margin call risks and thresholds
  - Market volatility impact
  - Corporate governance considerations

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key pledging terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on pledging risks and implications
- Reference specific pledge percentages
- Use bullet points for all analysis
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'corporate_governance': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my corporate governance analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present corporate governance analysis in bullet points only

You are analyzing corporate governance structures and practices.

User Query: "{{question}}"

**Corporate Governance Data:**

~CORPORATE_GOVERNANCE_TABLE~

**Governance Analysis:**

- **Board Composition**
  - Board independence and diversity
  - Director qualifications and experience
  - Board meeting frequency and attendance

- **Committee Effectiveness**
  - Audit committee structure and function
  - Nomination and remuneration oversight
  - Risk management committee role

- **Governance Quality**
  - Best practice adherence
  - Regulatory compliance record
  - Shareholder rights protection

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key governance terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on governance quality and effectiveness
- Reference specific board and committee details
- Use bullet points for all analysis
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'multi_company_ratios': """{% set no_raw_tables = true %}
IMPORTANT • Compare companies using bullet points only

You are conducting multi-company ratio analysis and comparison.

User Query: "{{question}}"

**Multi-Company Ratio Comparison:**

~COMPARISON_TABLE~

**Comparative Ratio Analysis:**

- **Profitability Comparison**
  - ROE, ROA, and margin comparisons
  - Earnings quality across companies
  - Profitability trend analysis

- **Efficiency Metrics**
  - Asset turnover comparisons
  - Working capital management efficiency
  - Operational effectiveness ratios

- **Financial Health Assessment**
  - Liquidity ratio comparisons
  - Leverage and solvency analysis
  - Credit quality indicators

- **Investment Rankings**
  - Best-in-class performers by category
  - Risk-adjusted return considerations
  - Valuation metric comparisons

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key ratio names and companies
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on relative performance comparisons
- Identify clear winners in each category
- Use specific ratio values and percentages
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'comparative_analysis': """{% set no_raw_tables = true %}
IMPORTANT • Compare companies using bullet points only

You are conducting comprehensive multi-company comparison.

User Query: "{{question}}"

**Multi-Company Analysis:**

~COMPARISON_TABLE~

**Comparative Assessment:**

- **Financial Performance**
  - Revenue and profitability comparisons
  - Growth trajectory analysis
  - Market share and positioning

- **Operational Efficiency**
  - Cost management effectiveness
  - Asset utilization comparisons
  - Working capital optimization

- **Strategic Positioning**
  - Competitive advantages and moats
  - Market leadership positions
  - Innovation and R&D capabilities

- **Investment Conclusion**
  - Best value propositions identified
  - Risk-reward profiles compared
  - Portfolio allocation recommendations

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold company names and key metrics
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Provide clear comparative insights
- Rank companies by performance categories
- Use specific metrics and percentages
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'ratio_analysis_comprehensive': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my ratio analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present comprehensive ratio analysis in bullet points

You are conducting detailed financial ratio analysis.

User Query: "{{question}}"

**Comprehensive Ratio Analysis:**

~COMPREHENSIVE_RATIOS_TABLE~

**Financial Health Assessment:**

- **Profitability Analysis**
  - Revenue efficiency and margin trends
  - Return on capital metrics (ROE, ROA, ROIC)
  - Earnings quality and sustainability

- **Liquidity & Solvency**
  - Short-term financial flexibility
  - Debt management and leverage ratios
  - Cash flow adequacy ratios

- **Efficiency Metrics**
  - Asset utilization effectiveness
  - Working capital management
  - Inventory and receivables turnover

- **Market Valuation**
  - P/E, P/B, and EV multiples
  - Dividend yield and payout ratios
  - Market premium/discount analysis

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key ratio categories
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Provide integrated ratio interpretation
- Connect ratios to business fundamentals
- Use industry benchmarking context
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'balance_sheet_analysis': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my balance sheet analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present balance sheet analysis in bullet points

You are analyzing balance sheet strength and composition.

User Query: "{{question}}"

**Balance Sheet Analysis:**

~FINANCIAL_DATA_TABLE~

**Asset-Liability Assessment:**

- **Asset Quality**
  - Current vs non-current asset composition
  - Asset turnover and utilization efficiency
  - Working capital management effectiveness

- **Capital Structure**
  - Debt-to-equity ratios and leverage
  - Interest coverage and debt serviceability
  - Equity base strength and growth

- **Liquidity Position**
  - Cash and cash equivalents adequacy
  - Current ratio and quick ratio analysis
  - Short-term financing needs

- **Financial Stability**
  - Balance sheet growth sustainability
  - Off-balance sheet obligations
  - Credit quality indicators

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key balance sheet items
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on balance sheet strength indicators
- Reference specific asset/liability items
- Connect to business strategy implications
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'comprehensive_with_charts': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my analysis to compare multiple companies while incorporating chart insights.
{% endif %}

IMPORTANT • Integrate visual and tabular analysis in bullet points

You are providing comprehensive analysis with visual data support.

User Query: "{{question}}"

**Visual Trend Analysis:**

~CHARTS_SECTION~

**Integrated Financial Analysis:**

~FINANCIAL_DATA_TABLE~

**Comprehensive Assessment:**

- **Trend Insights**
  - Key patterns visible in chart data
  - Year-over-year progression analysis
  - Seasonal or cyclical patterns identified

- **Data Correlation**
  - How visual trends align with financial metrics
  - Cross-validation between charts and tables
  - Performance consistency verification

- **Strategic Implications**
  - What trends suggest about business direction
  - Management effectiveness indicators
  - Future performance predictors

- **Investment Perspective**
  - Combined visual and fundamental analysis
  - Risk factors identified from trends
  - Opportunity areas highlighted

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key insights and metrics
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Reference both visual and tabular data
- Identify correlations and contradictions
- Provide forward-looking insights
- Ensure each point starts with a bullet (e.g., `-`)
""",

        'default_financial': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my financial analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present financial analysis in bullet points

You are a financial analyst providing comprehensive company analysis.

User Query: "{{question}}"

**Financial Analysis:**

Based on the available financial information:

~FINANCIAL_DATA_TABLE~

**Key Financial Assessment:**

- **Performance Overview**
  - Key metrics and performance indicators
  - Important trends and patterns identified
  - Significant financial highlights

- **Operational Insights**
  - What the data reveals about efficiency
  - Strengths and areas of concern
  - Competitive positioning indicators

- **Strategic Perspective**
  - Management effectiveness indicators
  - Capital allocation efficiency
  - Growth sustainability factors

- **Investment Implications**
  - Risk factors and opportunities
  - Valuation considerations
  - Portfolio fit assessment

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Provide clear, structured analysis
- Use specific data points when available
- Focus on actionable insights
- Ensure each point starts with a bullet (e.g., `-`)
""",
        'shareholding_analysis': """{% set no_raw_tables = true %}
{% if context_data.is_comparison %}
NOTE: This appears to be a comparison query. I'll adapt my shareholding analysis to compare multiple companies.
{% endif %}

IMPORTANT • Present shareholding analysis in bullet points only

You are analyzing shareholding patterns and implications.

User Query: "{{question}}"

**Shareholding Pattern Data:**

~SHAREHOLDING_TABLE~

**Shareholding Analysis:**

- **Promoter Holding**
  - Current promoter shareholding and recent changes
  - Promoter group pledging or encumbrances
  - Insider buying/selling trends

- **Institutional & Public Holding**
  - FII/DII shareholding trends
  - Mutual fund and insurance company stakes
  - Public shareholding and retail participation

- **Ownership Structure Implications**
  - Impact on control and governance
  - Changes in major shareholders
  - Implications for stock liquidity and volatility

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key shareholding terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on changes and trends in shareholding
- Reference specific percentages and dates
- Use bullet points for all analysis
- Ensure each point starts with a bullet (e.g., `-`)
""",
    }

    # Prepend system instruction to every template
    templates = {k: system_instruction + v for k, v in templates.items()}

    return templates.get(template_type, templates['default_financial'])


async def get_copilot_response(
        user_query: str,
        refined_context: str = "",
        context_data: dict = None
):
    """Enhanced copilot response with comprehensive template selection"""

    print("DEBUG: Enter get_copilot_response with context_data:", context_data)

    if not refined_context:
        print("DEBUG: No refined context, using fallback")
        refined_context = "No specific financial context was retrieved for this query."

    # Determine appropriate template
    template_type = determine_template_type(user_query, context_data)
    print(f"DEBUG: Selected template type: {template_type}")

    # Get template content
    template_content = get_template_content(template_type)

    # For edge cases, return immediately without calling Gemini
    if template_type in ['news', 'forecasting', 'stock_market', 'non_finance']:
        return {
            "response": template_content.strip(),
            "retrieved_context": refined_context,
            "template_type": template_type
        }

    # If no context for financial query, apologize
    if refined_context == "No specific financial context was retrieved for this query.":
        return {
            "response": "I apologize, but I currently lack the specific training data required to answer your question accurately.",
            "retrieved_context": refined_context,
            "template_type": "no_context_apology"
        }

    # Create Jinja2 template and render
    template = Template(template_content)

    # Prepare template variables
    template_vars = {
        'question': user_query,
        'context': refined_context
    }

    # Add context-specific variables
    if context_data:
        template_vars.update({
            'context_data': context_data,
            'company_count': context_data.get('company_count', 1),
            'query_type': context_data.get('query_type', 'company_overview'),
            'is_comparison': context_data.get('is_comparison', False),
            'endpoint_type': context_data.get('endpoint_type', 'financials'),
            'has_charts': context_data.get('has_charts', False),
            'has_financials': context_data.get('has_financials', False),
            'has_shareholding': context_data.get('has_shareholding', False)
        })

    # Render the template
    formatted_prompt = template.render(**template_vars)
    print(f"DEBUG: Formatted prompt for Gemini (first 500 chars): {formatted_prompt[:500]}...")

    # Call Gemini API
    gemini_api_key = os.getenv("GEMINI_API_KEY_3")
    if not gemini_api_key:
        print("DEBUG: GEMINI_API_KEY missing")
        return {"error": "GEMINI_API_KEY not set in environment."}

    try:
        llm = ChatGoogleGenerativeAI(
            google_api_key=gemini_api_key,
            model="gemini-2.0-flash-thinking-exp-01-21",
            temperature=0.3  # Lower temperature for consistent financial analysis
        )

        # Execute the call
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, llm.invoke, formatted_prompt)
        print("DEBUG: Gemini response received")

        # Post-process response
        response_content = response.content if hasattr(response, "content") else str(response)

        # Ensure proper placeholder formatting
        response_content = ensure_proper_placeholders(response_content)

        # Enforce bullet-point formatting
        response_content = enforce_bullet_format(response_content)

        # Highlight key parameters if available
        if context_data and context_data.get('identified_parameters'):
            params = [p for plist in context_data['identified_parameters'].values() for p in plist]
            response_content = highlight_key_parameters(response_content, params)

        return {
            "response": response_content,
            "retrieved_context": refined_context,
            "template_type": template_type,
            "context_data": context_data
        }

    except Exception as e:
        print(f"DEBUG: Gemini API call failed: {str(e)}")
        return {
            "error": f"Gemini API call failed: {str(e)}",
            "retrieved_context": refined_context,
            "template_type": template_type
        }


def ensure_proper_placeholders(response_content: str) -> str:
    """Ensure response contains proper placeholders for frontend integration"""

    placeholder_patterns = [
        '~OVERVIEW_STATS_TABLE~', '~COMPARISON_TABLE~', '~SHAREHOLDING_TABLE~',
        '~RATIOS_TABLE~', '~COMPREHENSIVE_RATIOS_TABLE~', '~FINANCIAL_PARAMETERS_TABLE~',
        '~CHARTS_SECTION~', '~FINANCIAL_DATA_TABLE~', '~DIVIDEND_TABLE~',
        '~INSIDER_TRADING_TABLE~', '~RPT_TABLE~', '~PLEDGED_DATA_TABLE~',
        '~CORPORATE_GOVERNANCE_TABLE~', '~STOCK_CHART_SECTION~'
    ]

    # Deduplicate placeholders: keep first, drop the rest
    for i, ph in enumerate(placeholder_patterns):
        token = f"__PH_TOKEN_{i}__"
        if ph in response_content:
            response_content = response_content.replace(ph, token, 1)
            # Remove any additional occurrences
            response_content = response_content.replace(ph, '')
            # Restore first occurrence
            response_content = response_content.replace(token, ph)

    # Ensure placeholders are on their own line
    for ph in placeholder_patterns:
        response_content = re.sub(rf"(?<!\n){re.escape(ph)}", f"\n{ph}", response_content)
        response_content = re.sub(rf"{re.escape(ph)}(?!\n)", f"{ph}\n", response_content)

    # Add default placeholder if none exist but content suggests tabular data
    has_placeholders = any(ph in response_content for ph in placeholder_patterns)
    if not has_placeholders and any(word in response_content.lower() for word in
                                    ['financial', 'data', 'table', 'ratio', 'performance']):
        paragraphs = response_content.split('\n\n')
        if len(paragraphs) > 1:
            paragraphs.insert(1, '~FINANCIAL_DATA_TABLE~')
            response_content = '\n\n'.join(paragraphs)

    # Collapse excessive blank lines
    response_content = re.sub(r"\n{3,}", "\n\n", response_content)

    return response_content


if __name__ == "__main__":
    # Example usage
    user_query = "What is the dividend policy of TCS?"
    refined_context = "TCS has consistently paid dividends with a stable payout ratio."
    context_data = {
        'query_type': 'dividend_analysis',
        'company_count': 1,
        'endpoint_type': 'dividend',
        'has_charts': False,
        'has_dividend': True,
        'is_comparison': False,
        'identified_parameters': {
            'dividend': ['dividend_yield', 'payout_ratio']
        }
    }

    response = asyncio.run(get_copilot_response(user_query, refined_context, context_data))
    print(response)