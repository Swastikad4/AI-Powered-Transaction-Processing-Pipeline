import json
import time
from typing import List, Dict, Any, Optional
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class GeminiService:
    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._model = None
        self._initialize()

    def _initialize(self) -> None:
        if not self.settings.GEMINI_API_KEY:
            logger.warning("Gemini API key missing")
            return

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.settings.GEMINI_API_KEY)
            # Use gemini-1.5-flash as requested
            self._model = genai.GenerativeModel("gemini-1.5-flash")
        except Exception as e:
            logger.error(f"Gemini init failed: {e}")

    def categorize_batch(self, transactions: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Takes a list of dicts with 'id', 'merchant', 'notes', 'amount'.
        Returns a dict mapping 'id' to 'category'.
        """
        if not self._model or not transactions:
            return {str(t['id']): "Other" for t in transactions}

        prompt = f"""
Categorize the following list of transactions.
You MUST choose one of the following exact categories: Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other.

Transactions:
{json.dumps(transactions, indent=2)}

Respond with a raw JSON object where keys are the transaction IDs and values are the assigned categories. Do not include markdown code blocks.
Example: {{"1": "Food", "2": "Shopping"}}
"""
        result = self._call_gemini_with_retries(prompt)
        if result and isinstance(result, dict):
            return result
        
        # Fallback if failed
        return {str(t['id']): "Other" for t in transactions}

    def generate_summary(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate narrative summary based on stats.
        stats contains: total_spend_inr, total_spend_usd, top_merchants, anomaly_count
        """
        if not self._model:
            return {
                "total_spend_inr": stats.get("total_spend_inr", 0),
                "total_spend_usd": stats.get("total_spend_usd", 0),
                "top_merchants": stats.get("top_merchants", []),
                "anomaly_count": stats.get("anomaly_count", 0),
                "narrative": "AI unavailable.",
                "risk_level": "low"
            }

        prompt = f"""
Given the following transaction statistics for a batch, generate a 2-3 sentence spending narrative and a risk_level (low, medium, or high).

Stats:
{json.dumps(stats, indent=2)}

Respond with a raw JSON object containing the exact input stats plus 'narrative' and 'risk_level'. Do not include markdown code blocks.
Expected format:
{{
  "total_spend_inr": <number>,
  "total_spend_usd": <number>,
  "top_merchants": [<list of strings>],
  "anomaly_count": <number>,
  "narrative": "<2-3 sentence narrative>",
  "risk_level": "<low, medium, or high>"
}}
"""
        result = self._call_gemini_with_retries(prompt)
        if result and isinstance(result, dict):
            return result
        
        # Fallback
        stats["narrative"] = "Failed to generate narrative."
        stats["risk_level"] = "low"
        return stats

    def _call_gemini_with_retries(self, prompt: str) -> Optional[Dict[str, Any]]:
        for attempt in range(1, 4):  # Up to 3 retries
            try:
                response = self._model.generate_content(prompt)
                text = response.text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
                    text = text.strip()
                return json.loads(text)
            except Exception as e:
                logger.warning(f"Gemini API error (attempt {attempt}): {e}")
                if attempt < 3:
                    time.sleep(2 ** attempt) # Exponential backoff: 2s, 4s
        return None

_gemini_service = None

def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
