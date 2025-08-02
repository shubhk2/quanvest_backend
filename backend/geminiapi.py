# import base64
from dotenv import load_dotenv
import os
import json
import re
from typing import Dict, List, Any

load_dotenv()  # loads variables from `.env`

from google import genai
from google.genai import types

# Initialize the Gemini API client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def classify_with_gemini(text: str, categories: List[str]) -> Dict[str, Any]:
    """
    Classify text into specified categories using Gemini API

    Args:
        text: The text to classify
        categories: List of category names to classify into

    Returns:
        Dictionary with "labels" and "scores" keys
    """
    # Truncate extremely long texts to avoid token limits
    if len(text) > 10000:
        text = text[:10000] + "...(truncated)"

    # Create a more detailed prompt with category descriptions
    category_descriptions = {
        "MDnA": "Management Discussion and Analysis - financial performance, operations, and future outlook",
        "Risk_Factors": "Discussion of risks and uncertainties facing the company",
        "Company_Segment": "Information about business segments, product lines, or divisions",
        "Company_Infrastructure": "Details about facilities, technology systems, or organizational structure",
        "Shareholder_Performance": "Information about stock performance, dividends, or returns to shareholders",
        "Company_Subsidiaries": "Details about company's subsidiaries, joint ventures, or acquisitions",
        "ESG": "Environmental, Social, and Governance information, including sustainability efforts",
        "Employee_Info": "Information about workforce, compensation, benefits, or labor relations"
    }
    
    formatted_categories = "\n".join([f"- {cat}: {category_descriptions.get(cat, '')}" for cat in categories])

    prompt = f"""
You are an expert financial document analyst. Your task is to classify the following text into the most relevant categories.

Categories and their meanings:
{formatted_categories}

For each identified category in the text, provide a confidence score between 0.0-1.0.
Be generous with classifications - if there's any relevant information for a category, include it.
It's better to classify text into a category with lower confidence than to miss relevant information.

Text to classify:
"{text}"

Respond ONLY with a valid JSON object with two keys:
1. "labels": An array of matching category names
2. "scores": A corresponding array of confidence scores (0.0-1.0)

Example response:
{{"labels": ["Risk_Factors", "MDnA"], "scores": [0.85, 0.72]}}
"""

    try:
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ]

        response = client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp-01-21",
            contents=contents
        )

        # Extract JSON from response
        result_text = response.text

        # Try to find JSON pattern in the response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(0)

        try:
            result = json.loads(result_text)
            # Ensure we have labels and scores
            if "labels" not in result or "scores" not in result:
                print("Gemini response missing required fields")
                return {"labels": [], "scores": []}

            # Validate that only provided categories are returned
            result["labels"] = [label for label in result["labels"] if label in categories]
            # Trim scores list to match labels length
            result["scores"] = result["scores"][:len(result["labels"])]
            
            print(f"Found {len(result['labels'])} categories: {', '.join(result['labels'])}")
            return result

        except json.JSONDecodeError:
            print(f"Failed to parse Gemini response as JSON: {result_text}")
            # Fallback: try to extract labels/scores manually if JSON parsing failed
            try:
                # Simple extraction for cases where the model might format incorrectly
                labels_match = re.search(r'"labels":\s*\[(.*?)\]', result_text)
                scores_match = re.search(r'"scores":\s*\[(.*?)\]', result_text)
                
                if labels_match and scores_match:
                    labels_str = labels_match.group(1)
                    scores_str = scores_match.group(1)
                    
                    # Extract labels
                    labels = [l.strip('" ') for l in labels_str.split(',')]
                    
                    # Extract scores
                    scores = [float(s.strip()) for s in scores_str.split(',')]
                    
                    # Match lengths
                    min_len = min(len(labels), len(scores))
                    return {"labels": labels[:min_len], "scores": scores[:min_len]}
            except Exception:
                pass
                
            return {"labels": [], "scores": []}

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return {"labels": [], "scores": []}


def summarize_with_gemini(text: str, max_length: int = 400) -> str:
    """
    Generate a concise summary of text using Gemini API

    Args:
        text: The text to summarize
        max_length: Target maximum length for summary

    Returns:
        A concise summary of the text
    """
    # Truncate extremely long texts to avoid token limits
    if len(text) > 10000:
        text = text[:10000] + "...(truncated)"

    prompt = f"""
Summarize the following text in a concise manner. 
Your summary should be under {max_length} characters and capture the most important information.

Text to summarize:
"{text}"

Respond ONLY with the summary, no additional text.
"""

    try:
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ]

        response = client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp-01-21",
            contents=contents
        )

        summary = response.text.strip()

        # Ensure the summary isn't too long
        if len(summary) > max_length:
            summary = summary[:max_length - 3] + "..."

        return summary

    except Exception as e:
        print(f"Error generating summary with Gemini: {e}")
        # Fall back to simple truncation
        return text[:400] + ("..." if len(text) > 400 else "")


def classify_and_summarize_with_gemini(text: str, categories: List[str], max_summary_length: int = 1000) -> Dict[str, Any]:
    """
    Classify text and generate detailed summaries in one API call
    
    Args:
        text: The text to classify and summarize
        categories: List of category names to classify into
        max_summary_length: Maximum length for summaries
        
    Returns:
        Dictionary with labels, scores, and summaries
    """
    # Truncate extremely long texts to avoid token limits
    if len(text) > 10000:
        text = text[:10000] + "...(truncated)"
    
    # Create category descriptions with emphasis on detailed information
    category_descriptions = {
        "Letter_To_Shareholders": "Communication from management to shareholders about company performance and strategy",
        "Business_Overview": "General description of the company's business model, operations and markets",
        "MDnA": "Management Discussion and Analysis - detailed financial performance, operations, and future outlook",
        "Corporate_Governance_Report": "Information about board composition, governance practices, and compliance",
        "Risk_Factors": "Detailed discussion of risks and uncertainties facing the company",
        "Corporate_Social_Responsibility": "Information about environmental initiatives, social impact, and sustainable practices",
        "Auditor_Report": "Independent auditor's assessment of financial statements and internal controls",
        "Shareholder_Information": "Details about stock ownership, dividends, shareholder rights and meetings",
        "Company_Segment": "Information about business segments, product lines, or divisions",
        "Company_Infrastructure": "Details about facilities, technology systems, or organizational structure",
        "Shareholder_Performance": "Information about stock performance, dividends, or returns to shareholders",
        "Company_Subsidiaries": "Details about company's subsidiaries, joint ventures, or acquisitions",
        "ESG": "Environmental, Social, and Governance information, including sustainability efforts",
        "Employee_Info": "Information about workforce, compensation, benefits, or labor relations"
    }
    
    formatted_categories = "\n".join([f"- {cat}: {category_descriptions.get(cat, '')}" for cat in categories])

    prompt = f"""
You are an expert financial document analyst. Analyze the following text to:
1. Classify it into relevant categories
2. Provide detailed summaries for each identified category

Categories and their descriptions:
{formatted_categories}

Instructions:
- For each category, provide a confidence score between 0.0-1.0
- Be generous with classifications - if there's any relevant information, include it
- For each identified category, provide a detailed and informative summary
- Be comprehensive in your analysis and consider ALL possible categories that might apply to the text
- Pay attention to both explicit mentions and implicit information related to each category
- Make sure your summaries are complete sentences that don't end abruptly

Text to analyze:
"{text}"

Respond with a valid JSON object with three keys:
1. "labels": Array of matching category names
2. "scores": Corresponding array of confidence scores (0.0-1.0)
3. "summaries": Object with category names as keys and detailed summaries as values

Example response:
{{
  "labels": ["Risk_Factors", "MDnA", "Letter_To_Shareholders"],
  "scores": [0.85, 0.72, 0.65],
  "summaries": {{
    "Risk_Factors": "Detailed risk summary...",
    "MDnA": "Comprehensive analysis of financial performance...",
    "Letter_To_Shareholders": "Analysis of the chairman's message..."
  }}
}}
"""

    try:
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ]

        response = client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp-01-21",
            contents=contents
        )

        # Extract JSON from response
        result_text = response.text
        
        # Try to find JSON pattern in the response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(0)
            
        try:
            result = json.loads(result_text)
            # Ensure we have all required fields
            if not all(key in result for key in ["labels", "scores", "summaries"]):
                print("Gemini response missing required fields")
                return {"labels": [], "scores": [], "summaries": {}}
                
            # Validate that only provided categories are returned
            result["labels"] = [label for label in result["labels"] if label in categories]
            # Trim scores list to match labels length
            result["scores"] = result["scores"][:len(result["labels"])]
            
            # Trim summaries to those in valid categories
            valid_summaries = {}
            for cat in result["labels"]:
                if cat in result["summaries"]:
                    summary = result["summaries"][cat]
                    # Intelligently truncate if too long
                    if len(summary) > max_summary_length:
                        # Try to find sentence boundary to truncate
                        sentences = re.split(r'(?<=[.!?])\s+', summary[:max_summary_length+100])
                        if len(sentences) > 1:
                            # Keep all complete sentences that fit within limit
                            truncated_summary = ""
                            for sentence in sentences:
                                if len(truncated_summary) + len(sentence) + 1 <= max_summary_length:
                                    if truncated_summary:
                                        truncated_summary += " " + sentence
                                    else:
                                        truncated_summary = sentence
                                else:
                                    break
                            summary = truncated_summary
                        else:
                            # If no sentence boundary found, try word boundary
                            words = summary[:max_summary_length].rsplit(' ', 1)
                            summary = words[0] + "..."
                    valid_summaries[cat] = summary
                    
            result["summaries"] = valid_summaries
            
            print(f"Found {len(result['labels'])} categories: {', '.join(result['labels'])}")
            return result
            
        except json.JSONDecodeError:
            print(f"Failed to parse Gemini response as JSON: {result_text}")
            return {"labels": [], "scores": [], "summaries": {}}
            
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return {"labels": [], "scores": [], "summaries": {}}


def generate():
    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""who are you"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="text/plain",
    )

    for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
    ):
        print(chunk.text, end="")


if __name__ == "__main__":
    generate()

