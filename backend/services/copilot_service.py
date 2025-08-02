import os
import asyncio
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from jinja2 import Template

load_dotenv()


def strip_md_tables(text: str, default_placeholder: str = "~FINANCIAL_DATA_TABLE~") -> str:
    """
    Remove any Markdown table the model still sneaks in and
    replace it with the generic placeholder so the front-end
    can inject the real table.
    """
    md_table_regex = re.compile(r"^(?:\s*\|.*\|\s*$\n?)+", re.MULTILINE)
    if md_table_regex.search(text):
        # wipe every markdown grid we find
        text = md_table_regex.sub("", text)
        # ensure *one* placeholder after first paragraph
        paras = text.split("\n\n")
        if default_placeholder not in text:
            if paras:
                paras.insert(1, default_placeholder)
            text = "\n\n".join(paras)
    return text


def enforce_bullet_format(text: str) -> str:
    """Convert paragraphs to bullet points"""
    # Convert numbered lists to bullets
    text = re.sub(r'^\d+\.\s+', '- ', text, flags=re.MULTILINE)

    # Split paragraphs into bullets if they don't already start with bullets
    if '\n\n' in text and not text.strip().startswith('-'):
        paragraphs = text.split('\n\n')
        bullet_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith('-') and not para.startswith('~') and not para.startswith('**'):
                # Convert paragraph to bullet points
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
        if param and len(param) > 2:  # Avoid highlighting very short terms
            text = re.sub(fr'\b{re.escape(param)}\b', f'**{param}**', text, flags=re.IGNORECASE)
    return text


def determine_template_type(user_query: str, context_data: dict = None) -> str:
    """Enhanced template selection with multi-company support"""
    query_lower = user_query.lower()

    # Edge case detection
    edge_cases = {
        'news': ['news', 'recent news', 'latest news', 'breaking news'],
        'forecasting': ['forecast', 'forecasting', 'predict', 'prediction', 'future', 'valuation', 'modelling',
                        'intrinsic value', 'dcf', 'fair value'],
        'stock_market': ['stock price', 'share price', 'market data', 'stock market', 'trading', 'volume',
                         'technical analysis'],
        'non_finance': ['weather', 'sports', 'entertainment', 'politics', 'technology news', 'india vs pakistan']
    }

    for case_type, keywords in edge_cases.items():
        if any(keyword in query_lower for keyword in keywords):
            return case_type

    if not context_data:
        return 'default_financial'

    # Enhanced data-driven template selection
    has_charts = context_data.get('has_charts', False)
    has_financials = context_data.get('has_financials', False)
    has_shareholding = context_data.get('has_shareholding', False)
    company_count = context_data.get('company_count', 0)
    endpoint_type = context_data.get('endpoint_type', 'financials')
    endpoint_mode = context_data.get('endpoint_mode', 'base')
    query_type = context_data.get('query_type', 'comprehensive')

    # NEW: Multi-company ratio comparison logic
    if company_count > 1 and endpoint_type == 'ratios':
        return 'multi_company_analysis'

    # Enhanced chart handling
    if has_charts and any(kw in query_lower for kw in ['trend', 'growth']):
        return 'trend_analysis_with_charts'

    # Template priority logic
    if company_count > 1:
        return 'comparative_analysis'
    elif 'overview' in query_lower or query_type == 'company_overview':
        return 'company_overview'
    elif has_shareholding:
        return 'shareholding_analysis'
    elif endpoint_type == 'ratios' and endpoint_mode == 'parameters':
        return 'ratio_analysis_specific'
    elif endpoint_type == 'ratios':
        return 'ratio_analysis_comprehensive'
    elif endpoint_mode == 'parameters' and has_financials:
        return 'parameter_specific_analysis'
    elif has_charts and has_financials:
        return 'comprehensive_with_charts'
    elif has_charts:
        return 'chart_focused_analysis'
    elif has_financials:
        return 'tabular_analysis'
    else:
        return 'default_financial'


def get_template_content(template_type: str) -> str:
    """Return enhanced Jinja2 template content with bullet-point enforcement and a system instruction."""

    # System instruction to guide Gemini to not always respond, but to answer only if context is relevant and to follow rules/query type
    system_instruction = (
        "SYSTEM: Only answer the user's real query if the provided context is relevant and sufficient. "
        "If the context is not relevant or does not contain the required information, do NOT fabricate or repeat the context. "
        "Always follow the rules and formatting instructions for the current query type. "
        "If the context is not needed for the query, ignore it and answer as per the rules. "
        "Do not provide a response just because context is present; respond only if it is appropriate and required."
        "\n\n"
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
IMPORTANT • Present all analysis in bullet points. Do not write paragraphs.

You are a financial analyst providing company overview analysis.
User Query: "{{question}}"

**Key Analysis Sections:**
- **Financial Highlights**
- **Performance Assessment**
- **Investment Perspective**

**Required Format:**
- Use '- ' prefix for every bullet point
- Maximum 5 bullet points per section
- No paragraph-style writing

**Context:** A company overview has been displayed above showing key company information and statistics.

~OVERVIEW_STATS_TABLE~

**Your Task:**
- Provide a focused analysis covering:
  - Key Financial Highlights
  - Performance Assessment
  - Investment Perspective

- Use bullet points for all analysis.
- Summarize key insights in concise bullet points.
- Break down complex information into a series of bullet points.
- Ensure each point starts with a bullet ('-').

**Available Financial Data:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Be concise and actionable
- Focus on insights not already covered in the overview above
- Use specific numbers when available
- Avoid repeating basic company information already displayed
- Present all analysis under each heading as concise bullet points.
- Ensure each point starts with a bullet (e.g., `-`).""",

        'multi_company_analysis': """{% set no_raw_tables = true %}
IMPORTANT • Compare companies using bullet points only

You are a financial analyst conducting multi-company comparative analysis.
User Query: "{{question}}"

**Comparative Analysis Framework:**
- **Financial Metrics Comparison**
  - Metric 1: {{company_a}} vs {{company_b}}
  - Metric 2: {{company_a}} vs {{company_b}}
- **Performance Benchmarks**
- **Investment Risk Profiles**

**Data Sources:**
~COMPARISON_TABLE~
~RATIOS_TABLE~

**Available Context:**
{{context}}

**Your Analysis Should Cover:**

**📊 Key Metrics Comparison**
- Compare the most significant financial ratios between companies
- Highlight which company leads in each category
- Identify percentage differences in key metrics

**⚡ Performance Analysis**
- Analyze relative operational efficiency
- Compare growth trajectories and trends
- Assess financial stability indicators

**🎯 Investment Implications**
- Determine which company offers better value proposition
- Evaluate risk-reward profiles for each
- Provide investor-focused recommendations

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus on comparative insights only
- Use specific percentages and ratios
- Present analysis in bullet point format
- Ensure each point starts with a bullet (e.g., `-`)""",

        'trend_analysis_with_charts': """{% set no_raw_tables = true %}
IMPORTANT • Present trend analysis in bullet points only

You are analyzing financial trends with visual data support.
User Query: "{{question}}"

**Trend Analysis with Charts:**

**📈 Visual Trends Analysis**
~CHARTS_SECTION~

**📊 Key Trend Insights**
- Identify primary growth or decline patterns
- Highlight significant trend changes or inflection points
- Compare year-over-year progression metrics

**⏱️ Time-Based Performance**
- Analyze seasonal or cyclical patterns
- Assess consistency of performance trends
- Evaluate momentum indicators

**🔮 Future Implications**
- Determine trend sustainability
- Identify potential risk factors
- Assess competitive positioning trends

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Reference both visual and contextual data
- Focus on trend interpretation
- Present analysis in bullet point format
- Ensure each point starts with a bullet (e.g, `-`)""",

        'comparative_analysis': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are a financial analyst comparing multiple companies.
User Query: "{{question}}"

**Available Data:**
{{context}}

**Analysis Framework:**
Provide a structured comparison using these sections:

**📊 Key Metrics Comparison**
~COMPARISON_TABLE~

**💡 Performance Analysis**
- Highlight the top performer in each key area
- Identify relative strengths and weaknesses
- Note any significant differences in business models

**🎯 Investment Implications**
- Which company offers better value proposition?
- Risk considerations for each
- Suitability for different investor types

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).
- Include specific metrics and percentages
- Be objective and fact-based
- Conclude with a brief comparative summary""",

        'shareholding_analysis': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are analyzing company shareholding patterns and ownership structure.
User Query: "{{question}}"

**Shareholding Data:**
~SHAREHOLDING_TABLE~

**Financial Context:**
{{context}}

**Your Analysis Should Cover:**

**🏢 Ownership Structure**
- Key institutional and individual shareholders
- Promoter vs public holding analysis
- Any significant recent changes in holdings

**📈 Shareholding Insights**
- Quality of institutional investors
- Concentration vs diversification of ownership
- Impact on company governance and decision-making

**💼 Investment Implications**
- What the shareholding pattern suggests about confidence
- Liquidity considerations
- Governance quality indicators

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Reference specific shareholders and percentages
- Explain the significance of major holdings
- Connect shareholding to company performance and strategy
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).""",

        'ratio_analysis_specific': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are a financial analyst focusing on specific financial ratios.
User Query: "{{question}}"

**Requested Ratios Analysis:**
~RATIOS_TABLE~

**Supporting Context:**
{{context}}

**Detailed Ratio Analysis:**

**📊 Ratio Interpretation**
- What each ratio indicates about company performance
- Industry benchmarking context where relevant
- Trends and year-over-year changes

**🔍 Deep Dive Insights**
- Interconnections between the ratios
- What the ratios reveal about management efficiency
- Red flags or positive indicators

**📈 Performance Assessment**
- Overall financial health based on these metrics
- Comparative performance vs industry standards
- Areas for improvement or concern

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus specifically on the requested ratios
- Provide numerical context and percentages
- Explain what each ratio means in plain language
- Connect ratios to business performance
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).""",

        'ratio_analysis_comprehensive': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are conducting a comprehensive financial ratio analysis.
User Query: "{{question}}"

**Complete Ratio Analysis:**
~COMPREHENSIVE_RATIOS_TABLE~

**Supporting Data:**
{{context}}

**Comprehensive Financial Health Assessment:**

**💰 Profitability Analysis**
- Revenue efficiency and margin trends
- Return on assets and equity performance
- Earnings quality assessment

**🏦 Liquidity & Solvency**
- Short-term financial flexibility
- Debt management and leverage
- Cash flow adequacy

**⚡ Efficiency Metrics**
- Asset utilization effectiveness
- Working capital management
- Operational efficiency indicators

**📊 Overall Financial Score**
- Integrated assessment across all ratio categories
- Key strengths and weaknesses
- Strategic financial recommendations

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

Use the comprehensive ratio data to provide actionable insights.
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).""",

        'parameter_specific_analysis': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are analyzing specific financial statement parameters.
User Query: "{{question}}"

**Focused Parameter Analysis:**
~FINANCIAL_PARAMETERS_TABLE~

**Context:**
{{context}}

**Parameter-Specific Insights:**

**📋 Parameter Overview**
- What these specific metrics represent
- Their importance in financial analysis
- Industry context and benchmarks

**🔢 Numerical Analysis**
- Trends across the time periods shown
- Percentage changes and growth rates
- Absolute values and their significance

**💡 Strategic Implications**
- What these parameters reveal about business strategy
- Management decisions reflected in the numbers
- Future outlook based on current trends

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Focus exclusively on the requested parameters
- Provide specific numerical insights
- Explain business implications of the trends
- Keep analysis targeted and actionable
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).""",

        'comprehensive_with_charts': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are providing comprehensive financial analysis with visual data support.
User Query: "{{question}}"

**Multi-Dimensional Analysis:**

**📊 Visual Trends Analysis**
~CHARTS_SECTION~

The charts above illustrate key trends. Based on this visual data and the supporting context:

**📈 Performance Trends**
- Key patterns visible in the chart data
- Year-over-year progression analysis
- Seasonal or cyclical patterns

**💹 Financial Data Deep Dive**
~FINANCIAL_DATA_TABLE~

**🎯 Integrated Insights**
- How the visual trends correlate with financial metrics
- Cross-validation between chart and table data
- Emerging patterns and future implications

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Reference both visual and tabular data
- Identify correlations between different data types
- Provide forward-looking insights based on trends
- Maintain focus on actionable intelligence
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).""",

        'chart_focused_analysis': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are analyzing financial data with primary focus on visual trends.
User Query: "{{question}}"

**Chart-Based Financial Analysis:**

**📊 Visual Data Presentation**
~CHARTS_SECTION~

**📈 Trend Analysis**
Based on the charts above and supporting context:

- **Primary Trends:** Key patterns and movements
- **Performance Indicators:** What the trends suggest about performance
- **Comparative Analysis:** How metrics relate to each other over time
- **Future Implications:** What current trends might indicate

**Supporting Context:**
{{context}}

**Key Insights:**
- Focus on what the visual data reveals
- Identify inflection points and significant changes
- Provide context for trend interpretations
- Connect visual patterns to business fundamentals

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Lead with chart insights
- Reference specific time periods and values
- Explain the significance of trend directions
- Provide actionable conclusions
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).""",

        'tabular_analysis': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are analyzing detailed financial data from company statements.
User Query: "{{question}}"

**Financial Statement Analysis:**

**📋 Data Overview**
~FINANCIAL_DATA_TABLE~

**🔍 Detailed Analysis**
Based on the financial data above:

**Key Financial Highlights:**
- Most significant figures and their implications
- Year-over-year changes and growth patterns
- Notable strengths and concerns in the data

**Performance Assessment:**
- What the numbers reveal about company health
- Efficiency and profitability indicators
- Cash flow and liquidity considerations

**Strategic Insights:**
- Management decisions reflected in the financials
- Competitive positioning based on metrics
- Areas requiring attention or improvement

**Supporting Context:**
{{context}}

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Reference specific figures from the table
- Provide percentage calculations and comparisons
- Focus on material changes and trends
- Deliver actionable financial insights
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`).""",

        'default_financial': """{% set no_raw_tables = true %}
IMPORTANT • Do **not** render any markdown tables. Only reference the placeholder(s) shown below — the real
table / chart will be injected by the front-end.

You are a financial analyst providing comprehensive company analysis.
User Query: "{{question}}"

**Financial Analysis:**
Based on the available financial information and context provided:

{{context}}

**Analysis Framework:**

**📊 Financial Overview**
- Key metrics and performance indicators
- Important trends and patterns identified
- Significant financial highlights

**💡 Key Insights**
- What the data reveals about company performance
- Strengths and areas of concern
- Competitive positioning and efficiency

**🎯 Investment Perspective**
- What this analysis means for stakeholders
- Risk factors and opportunities identified
- Overall assessment and recommendations

**Formatting Rules:**
- Use bullet points exclusively
- Bold key financial terms
- Never use markdown tables
- Reference placeholders: ~PLACEHOLDER_NAME~

**Instructions:**
- Provide clear, structured analysis
- Use specific data points when available
- Focus on actionable insights
- Maintain objective, professional tone
- Use bullet points for clarity
- Ensure each point starts with a bullet (e.g, `-`)."""
    }

    # Prepend the system instruction to every template
    templates = {k: system_instruction + v for k, v in templates.items()}

    return templates.get(template_type, templates['default_financial'])


async def get_copilot_response(
        user_query: str,
        refined_context: str = "",
        context_data: dict = None
):
    """Enhanced copilot response with dynamic template selection and bullet-point enforcement"""
    print("DEBUG: Enter get_copilot_response with context_data:", context_data)

    if not refined_context:
        print("DEBUG: No refined context from Colab, using fallback")
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

    # If no context is found for a valid financial query, apologize
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
            'company_count': context_data.get('company_count', 1),
            'endpoint_type': context_data.get('endpoint_type', 'financials'),
            'has_charts': context_data.get('has_charts', False),
            'has_financials': context_data.get('has_financials', False),
            'has_shareholding': context_data.get('has_shareholding', False)
        })

    # Render the template
    formatted_prompt = template.render(**template_vars)
    print(f"DEBUG: Formatted prompt for Gemini: {formatted_prompt[:500]}...")

    # Call Gemini API
    gemini_api_key = os.getenv("GEMINI_API_KEY_3")
    if not gemini_api_key:
        print("DEBUG: GEMINI_API_KEY missing")
        return {"error": "GEMINI_API_KEY not set in environment."}

    try:
        llm = ChatGoogleGenerativeAI(
            google_api_key=gemini_api_key,
            model="gemini-2.0-flash-thinking-exp-01-21",
            temperature=0.3  # Lower temperature for more consistent financial analysis
        )

        # Create a simple prompt wrapper
        prompt = ChatPromptTemplate.from_messages([
            ("human", formatted_prompt)
        ])
        final_prompt = prompt.format()

        # Execute the call
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, llm.invoke, final_prompt)
        print("DEBUG: Gemini response received")

        # Post-process response to ensure placeholder formatting and bullet points
        response_content = response.content if hasattr(response, "content") else str(response)

        # Ensure proper placeholder formatting
        response_content = ensure_proper_placeholders(response_content)

        # NEW: Enforce bullet-point formatting
        response_content = enforce_bullet_format(response_content)

        # NEW: Highlight key parameters if available
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
    # Standard placeholder patterns that should be preserved
    placeholder_patterns = [
        '~OVERVIEW_STATS_TABLE~',
        '~COMPARISON_TABLE~',
        '~SHAREHOLDING_TABLE~',
        '~RATIOS_TABLE~',
        '~COMPREHENSIVE_RATIOS_TABLE~',
        '~FINANCIAL_PARAMETERS_TABLE~',
        '~CHARTS_SECTION~',
        '~FINANCIAL_DATA_TABLE~'
    ]

    # If response doesn't contain placeholders but should, add appropriate ones
    # This is a safety mechanism
    if not any(placeholder in response_content for placeholder in placeholder_patterns):
        # Add generic table placeholder if financial data is mentioned
        if any(term in response_content.lower() for term in ['table', 'data', 'metrics', 'financial']):
            # Insert placeholder after first paragraph
            paragraphs = response_content.split('\n\n')
            if len(paragraphs) > 1:
                paragraphs.insert(1, '~OVERVIEW_STATS_TABLE~')
                response_content = '\n\n'.join(paragraphs)

    return response_content

if __name__=="__main__":
    # Example usage
    user_query = "What is the financial overview of Company X?"
    refined_context = "TCS has shown consistent growth in revenue over the past 5 years."
    context_data = {
        'company_count': 1,
        'endpoint_type': 'financials',
        'has_charts': True,
        'has_financials': True,
        'has_shareholding': False,
        'identified_parameters': {
            'profitability': ['ROE', 'ROA'],
            'liquidity': ['Current Ratio']
        }
    }

    response = asyncio.run(get_copilot_response(user_query, refined_context, context_data))
    print(response)