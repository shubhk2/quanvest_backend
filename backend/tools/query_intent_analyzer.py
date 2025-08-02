"""
Query Intent Analyzer for Financial RAG Copilot System
Separates user intent from contextual data requirements to enable accurate template selection
"""

import re
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class IntentPriority(Enum):
    CRITICAL = 10  # Explicit user intent (ratio analysis, charts, comparisons)
    HIGH = 8  # Specific parameter requests, company overviews
    MEDIUM = 6  # Financial analysis, comprehensive views
    LOW = 4  # Shareholding (only when explicitly requested)
    CONTEXT = 2  # Supporting data for context


@dataclass
class IntentMatch:
    intent_type: str
    priority: int
    confidence: float
    matched_keywords: List[str]
    explicit_indicators: List[str]
    primary_data_needs: List[str]
    context_data_needs: List[str]
    recommended_template: str


class QueryIntentAnalyzer:
    INTENT_DEFINITIONS = {
        "RATIO_ANALYSIS": {
            "priority": IntentPriority.CRITICAL.value,
            "explicit_indicators": [
                "profitability ratios", "financial ratios", "ratio analysis", "ratios for",
                "roe trends", "roa analysis", "margin analysis", "return on equity",
                "return on assets", "debt to equity", "current ratio", "quick ratio"
            ],
            "keywords": [
                "ratio", "ratios", "roe", "roa", "roi", "margin", "margins",
                "profitability", "return", "returns", "efficiency", "leverage",
                "liquidity", "turnover", "coverage", "pe ratio", "pb ratio"
            ],
            "parameter_indicators": [
                "net_profit_margin", "gross_profit_margin", "operating_margin",
                "return_on_equity", "return_on_assets", "current_ratio",
                "debt_to_equity", "asset_turnover", "inventory_turnover"
            ],
            "templates": ["ratio_analysis_specific", "ratio_analysis_comprehensive"],
            "primary_data": ["financial_ratios"],
            "context_data": ["profit_and_loss"],
            "exclusion_keywords": []
        },

        "CHART_VISUALIZATION": {
            "priority": IntentPriority.CRITICAL.value,
            "explicit_indicators": [
                "show me charts", "growth trends", "trend analysis", "chart showing",
                "graph of", "visual trends", "performance trends", "growth chart",
                "trend over time", "historical trends", "chart analysis"
            ],
            "keywords": [
                "chart", "charts", "graph", "graphs", "trend", "trends",
                "growth", "visual", "show me", "display", "plot", "timeline"
            ],
            "parameter_indicators": [],
            "templates": ["chart_focused_analysis", "trend_analysis_with_charts"],
            "primary_data": ["charts"],
            "context_data": ["financial_ratios", "profit_and_loss"],
            "exclusion_keywords": ["shareholding chart", "ownership chart"]
        },

        "COMPANY_COMPARISON": {
            "priority": IntentPriority.CRITICAL.value,
            "explicit_indicators": [
                "compare companies", "vs analysis", "comparison between",
                "compare tcs vs infosys", "tcs versus wipro", "between companies",
                "which company", "better performer", "comparison analysis"
            ],
            "keywords": [
                "compare", "comparison", "vs", "versus", "against", "between",
                "better", "worse", "higher", "lower", "outperform", "underperform"
            ],
            "parameter_indicators": [],
            "templates": ["comparative_analysis", "multi_company_analysis"],
            "primary_data": ["financial_ratios", "profit_and_loss"],
            "context_data": ["balance_sheet"],
            "exclusion_keywords": []
        },

        "PARAMETER_SPECIFIC": {
            "priority": IntentPriority.HIGH.value,
            "explicit_indicators": [
                "specific ebitda", "operating margin data", "revenue figures",
                "give me", "show me", "what is the", "specific data for",
                "exact figures", "particular metrics", "detailed breakdown"
            ],
            "keywords": [
                "specific", "exact", "particular", "detailed", "give me",
                "show me", "what is", "how much", "figures", "data for"
            ],
            "parameter_indicators": [
                "ebitda", "operating_income", "net_income", "total_revenues",
                "cost_of_goods_sold", "operating_expenses", "depreciation"
            ],
            "templates": ["parameter_specific_analysis"],
            "primary_data": ["identified_parameters"],
            "context_data": [],
            "exclusion_keywords": ["all parameters", "comprehensive"]
        },

        "COMPANY_OVERVIEW": {
            "priority": IntentPriority.HIGH.value,
            "explicit_indicators": [
                "company overview", "company profile", "about company",
                "business overview", "company information", "overview of",
                "profile of", "introduction to", "summary of company"
            ],
            "keywords": [
                "overview", "profile", "about", "company", "business",
                "introduction", "summary", "information", "background"
            ],
            "parameter_indicators": [],
            "templates": ["company_overview"],
            "primary_data": ["company_overview"],
            "context_data": ["financial_ratios"],
            "exclusion_keywords": ["financial overview", "performance overview"]
        },

        "CASH_FLOW_ANALYSIS": {
            "priority": IntentPriority.HIGH.value,
            "explicit_indicators": [
                "cash flow analysis", "cash position", "liquidity analysis",
                "operating cash flow", "free cash flow", "cash generation",
                "cash flow from operations", "cash flow statement"
            ],
            "keywords": [
                "cash flow", "cashflow", "cash", "liquidity", "operating cash",
                "free cash", "cash position", "cash generation"
            ],
            "parameter_indicators": [
                "cash_from_operations", "free_cash_flow", "operating_cash_flow",
                "cash_and_equivalents", "capital_expenditure"
            ],
            "templates": ["parameter_specific_analysis", "tabular_analysis"],
            "primary_data": ["cashflow"],
            "context_data": ["balance_sheet"],
            "exclusion_keywords": []
        },

        "FINANCIAL_OVERVIEW": {
            "priority": IntentPriority.MEDIUM.value,
            "explicit_indicators": [
                "financial analysis", "comprehensive view", "overall performance",
                "financial performance", "complete analysis", "full analysis",
                "comprehensive financial", "overall financial"
            ],
            "keywords": [
                "comprehensive", "financial", "analysis", "performance",
                "results", "overall", "complete", "full", "entire"
            ],
            "parameter_indicators": [],
            "templates": ["comprehensive_with_charts", "tabular_analysis"],
            "primary_data": ["profit_and_loss", "balance_sheet", "financial_ratios"],
            "context_data": ["cashflow"],
            "exclusion_keywords": ["specific", "particular"]
        },

        "SHAREHOLDING_ANALYSIS": {
            "priority": IntentPriority.LOW.value,  # Intentionally low priority
            "explicit_indicators": [
                "shareholding pattern", "ownership structure", "shareholder analysis",
                "shareholding information", "ownership analysis", "share distribution",
                "shareholding details", "ownership pattern", "shareholder breakdown"
            ],
            "keywords": [
                "shareholding", "ownership", "shareholders", "shareholder",
                "shares", "share distribution", "ownership pattern"
            ],
            "parameter_indicators": [
                "shares_outstanding", "earnings_per_share", "dividend_per_share",
                "book_value_per_share"
            ],
            "templates": ["shareholding_analysis"],
            "primary_data": ["shareholding"],
            "context_data": ["financial_ratios"],
            "exclusion_keywords": []
        }
    }

    @classmethod
    def analyze_query_intent(cls, query: str, classification_data: Dict = None) -> IntentMatch:
        """
        Analyze query to determine primary user intent with confidence scoring
        """
        query_lower = query.lower().strip()

        # Step 1: Check for explicit intent indicators (highest confidence)
        explicit_match = cls._check_explicit_indicators(query_lower)
        if explicit_match and explicit_match.confidence >= 0.9:
            logger.info(f"High-confidence explicit intent detected: {explicit_match.intent_type}")
            return explicit_match

        # Step 2: Keyword density analysis with context
        keyword_matches = cls._analyze_keyword_density(query_lower, classification_data)

        # Step 3: Parameter correlation analysis
        parameter_matches = cls._analyze_parameter_correlation(query_lower, classification_data)

        # Step 4: Combine scores and resolve conflicts
        final_intent = cls._resolve_intent_conflicts(
            explicit_match, keyword_matches, parameter_matches, query_lower
        )

        # Step 5: Validate intent makes sense for the query
        validated_intent = cls._validate_intent_match(final_intent, query_lower, classification_data)

        logger.info(f"Final intent: {validated_intent.intent_type} (confidence: {validated_intent.confidence:.2f})")
        return validated_intent

    @classmethod
    def _check_explicit_indicators(cls, query_lower: str) -> Optional[IntentMatch]:
        """Check for explicit intent indicators with high confidence"""
        best_match = None
        highest_confidence = 0.0

        for intent_type, config in cls.INTENT_DEFINITIONS.items():
            for indicator in config["explicit_indicators"]:
                if indicator.lower() in query_lower:
                    # Calculate confidence based on indicator specificity
                    confidence = 0.95 - (len(indicator.split()) * 0.05)  # Longer phrases = higher confidence
                    confidence = max(confidence, 0.85)  # Minimum confidence for explicit indicators

                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        best_match = IntentMatch(
                            intent_type=intent_type,
                            priority=config["priority"],
                            confidence=confidence,
                            matched_keywords=[indicator],
                            explicit_indicators=[indicator],
                            primary_data_needs=config["primary_data"],
                            context_data_needs=config["context_data"],
                            recommended_template=config["templates"][0]
                        )

        return best_match

    @classmethod
    def _analyze_keyword_density(cls, query_lower: str, classification_data: Dict = None) -> Dict[str, IntentMatch]:
        """Analyze keyword density for each intent type"""
        matches = {}
        query_words = set(query_lower.split())

        for intent_type, config in cls.INTENT_DEFINITIONS.items():
            # Skip if exclusion keywords are present
            if any(excl in query_lower for excl in config["exclusion_keywords"]):
                continue

            matched_keywords = []
            for keyword in config["keywords"]:
                if keyword in query_lower:
                    matched_keywords.append(keyword)

            if matched_keywords:
                # Calculate confidence based on keyword density and specificity
                density = len(matched_keywords) / len(config["keywords"])
                keyword_specificity = sum(1 for kw in matched_keywords if kw not in ["data", "analysis", "show"])
                confidence = min(0.8, density * 0.6 + keyword_specificity * 0.1)

                matches[intent_type] = IntentMatch(
                    intent_type=intent_type,
                    priority=config["priority"],
                    confidence=confidence,
                    matched_keywords=matched_keywords,
                    explicit_indicators=[],
                    primary_data_needs=config["primary_data"],
                    context_data_needs=config["context_data"],
                    recommended_template=config["templates"][0]
                )

        return matches

    @classmethod
    def _analyze_parameter_correlation(cls, query_lower: str, classification_data: Dict = None) -> Dict[
        str, IntentMatch]:
        """Analyze correlation between requested parameters and intent types"""
        matches = {}

        if not classification_data:
            return matches

        identified_params = classification_data.get('identified_parameters', {})

        for intent_type, config in cls.INTENT_DEFINITIONS.items():
            param_matches = []

            # Check parameter indicators
            for param_indicator in config["parameter_indicators"]:
                for table, params in identified_params.items():
                    if param_indicator in params or any(param_indicator in p for p in params):
                        param_matches.append(param_indicator)

            # Check parameter alignment with intent
            if intent_type == "RATIO_ANALYSIS" and identified_params.get('financial_ratios'):
                param_matches.extend(identified_params['financial_ratios'][:3])
            elif intent_type == "CASH_FLOW_ANALYSIS" and identified_params.get('cashflow'):
                param_matches.extend(identified_params['cashflow'][:3])

            if param_matches:
                confidence = min(0.85, len(param_matches) * 0.2 + 0.4)
                matches[intent_type] = IntentMatch(
                    intent_type=intent_type,
                    priority=config["priority"],
                    confidence=confidence,
                    matched_keywords=[],
                    explicit_indicators=[],
                    primary_data_needs=config["primary_data"],
                    context_data_needs=config["context_data"],
                    recommended_template=config["templates"][0]
                )

        return matches

    @classmethod
    def _resolve_intent_conflicts(cls, explicit_match: Optional[IntentMatch],
                                  keyword_matches: Dict[str, IntentMatch],
                                  parameter_matches: Dict[str, IntentMatch],
                                  query_lower: str) -> IntentMatch:
        """Resolve conflicts between multiple intent matches using priority and confidence"""

        # Explicit match always wins if confidence is high
        if explicit_match and explicit_match.confidence >= 0.9:
            return explicit_match

        # Combine all matches
        all_matches = {}

        if explicit_match:
            all_matches[explicit_match.intent_type] = explicit_match

        for intent_type, match in keyword_matches.items():
            if intent_type in all_matches:
                # Combine confidence scores
                existing = all_matches[intent_type]
                combined_confidence = (existing.confidence + match.confidence) / 2
                existing.confidence = min(0.95, combined_confidence + 0.1)
                existing.matched_keywords.extend(match.matched_keywords)
            else:
                all_matches[intent_type] = match

        for intent_type, match in parameter_matches.items():
            if intent_type in all_matches:
                existing = all_matches[intent_type]
                existing.confidence = min(0.95, existing.confidence + 0.15)
            else:
                all_matches[intent_type] = match

        if not all_matches:
            # Default to financial overview
            return cls._create_default_intent()

        # Select best match based on priority and confidence
        best_match = max(
            all_matches.values(),
            key=lambda m: (m.priority, m.confidence)
        )

        return best_match

    @classmethod
    def _validate_intent_match(cls, intent_match: IntentMatch, query_lower: str,
                               classification_data: Dict = None) -> IntentMatch:
        """Validate that the intent match makes sense for the query"""

        # Special validation for shareholding intent
        if intent_match.intent_type == "SHAREHOLDING_ANALYSIS":
            # Only allow if explicitly requested or no other strong intent
            explicit_shareholding = any(
                indicator in query_lower
                for indicator in cls.INTENT_DEFINITIONS["SHAREHOLDING_ANALYSIS"]["explicit_indicators"]
            )

            if not explicit_shareholding and intent_match.confidence < 0.7:
                # Override with financial overview instead
                logger.info("Overriding weak shareholding intent with financial overview")
                return cls._create_default_intent()

        # Validate company comparison intent
        if intent_match.intent_type == "COMPANY_COMPARISON":
            if classification_data and classification_data.get('company_count', 0) < 2:
                # Not actually a comparison query
                logger.info("Single company detected, overriding comparison intent")
                return cls._create_default_intent()

        # Validate chart intent
        if intent_match.intent_type == "CHART_VISUALIZATION":
            if classification_data and not classification_data.get('display_components', {}).get('chart', False):
                # Charts not recommended by classifier
                intent_match.confidence *= 0.7  # Reduce confidence

        return intent_match

    @classmethod
    def _create_default_intent(cls) -> IntentMatch:
        """Create default financial overview intent"""
        config = cls.INTENT_DEFINITIONS["FINANCIAL_OVERVIEW"]
        return IntentMatch(
            intent_type="FINANCIAL_OVERVIEW",
            priority=config["priority"],
            confidence=0.5,
            matched_keywords=[],
            explicit_indicators=[],
            primary_data_needs=config["primary_data"],
            context_data_needs=config["context_data"],
            recommended_template=config["templates"][0]
        )

    @classmethod
    def determine_data_priority_filtering(cls, intent_match: IntentMatch,
                                          classification_data: Dict) -> Dict[str, Dict]:
        """
        Determine what data should be fetched based on intent priority
        Returns: {
            'primary': {'tables': [], 'components': []},
            'context': {'tables': [], 'components': []},
            'skip': {'tables': [], 'components': []}
        }
        """

        display_components = classification_data.get('display_components', {})
        required_tables = classification_data.get('required_sql_tables', [])

        filtering = {
            'primary': {'tables': [], 'components': []},
            'context': {'tables': [], 'components': []},
            'skip': {'tables': [], 'components': []}
        }

        # Primary data based on intent
        if intent_match.intent_type == "RATIO_ANALYSIS":
            filtering['primary']['tables'] = ['financial_ratios']
            filtering['primary']['components'] = ['table', 'chart']
            filtering['context']['tables'] = ['profit_and_loss']
            filtering['skip']['components'] = ['shareholding', 'company_overview']

        elif intent_match.intent_type == "CHART_VISUALIZATION":
            filtering['primary']['components'] = ['chart']
            filtering['context']['tables'] = ['financial_ratios', 'profit_and_loss']
            filtering['skip']['components'] = ['shareholding']

        elif intent_match.intent_type == "COMPANY_COMPARISON":
            filtering['primary']['tables'] = ['financial_ratios', 'profit_and_loss']
            filtering['primary']['components'] = ['table', 'chart']
            filtering['context']['tables'] = ['balance_sheet']
            filtering['skip']['components'] = ['company_overview']

        elif intent_match.intent_type == "PARAMETER_SPECIFIC":
            filtering['primary']['tables'] = [t for t in required_tables if t != 'shareholder']
            filtering['primary']['components'] = ['table']
            filtering['skip']['components'] = ['shareholding', 'company_overview']

        elif intent_match.intent_type == "COMPANY_OVERVIEW":
            filtering['primary']['components'] = ['company_overview', 'table']
            filtering['context']['tables'] = ['financial_ratios']
            filtering['skip']['components'] = ['shareholding']

        elif intent_match.intent_type == "SHAREHOLDING_ANALYSIS":
            filtering['primary']['tables'] = ['shareholder']
            filtering['primary']['components'] = ['table', 'shareholding']
            filtering['context']['tables'] = ['financial_ratios']

        else:  # FINANCIAL_OVERVIEW or default
            filtering['primary']['tables'] = required_tables
            filtering['primary']['components'] = list(display_components.keys())

        logger.info(f"Data priority filtering for {intent_match.intent_type}: {filtering}")
        return filtering


def analyze_query_intent_and_priority(query: str, classification_data: Dict) -> Tuple[IntentMatch, Dict]:
    """
    Main function to analyze query intent and determine data priority

    Returns:
        Tuple of (IntentMatch, priority_filtering_dict)
    """

    # Analyze intent
    intent_match = QueryIntentAnalyzer.analyze_query_intent(query, classification_data)

    # Determine data priority filtering
    priority_filtering = QueryIntentAnalyzer.determine_data_priority_filtering(
        intent_match, classification_data
    )

    return intent_match, priority_filtering
