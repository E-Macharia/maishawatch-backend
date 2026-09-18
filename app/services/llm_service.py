# app/services/llm_service.py
import os
import json
import logging
from typing import Optional, List, Dict, Any
import httpx
from app.core.config import AI_API_KEY, AI_MODEL, AI_BASE_URL

logger = logging.getLogger(__name__)


class LLMService:
    """Service for integrating with LLM APIs (Groq, OpenAI, Claude)"""

    def __init__(self):
        self.api_key = os.getenv("AI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or AI_API_KEY
        self.model = os.getenv("AI_MODEL") or os.getenv("GROQ_MODEL") or AI_MODEL
        self.base_url = os.getenv("AI_BASE_URL") or AI_BASE_URL
        self.is_groq = bool(self.api_key and self.api_key.startswith("gsk_"))
        self.is_claude = bool(self.api_key and self.api_key.startswith("sk-ant-"))

    def generate_response_sync(
        self,
        message: str,
        context: Dict[str, Any],
        history: List[Dict] = None,
        language: str = "en",
    ) -> Optional[Dict[str, Any]]:
        """Synchronous response generation using configured LLM"""
        if not self.api_key:
            return None

        system_prompt = self._build_system_prompt(context, language)
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for msg in history[-8:]:
                role = "assistant" if msg.get("role") in ["assistant", "ai"] else "user"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})

        # Try specified model first, with automatic fallbacks for Groq
        candidate_models = [self.model]
        if self.is_groq:
            for fallback in ["groq/compound", "groq/compound-mini", "openai/gpt-oss-20b"]:
                if fallback not in candidate_models:
                    candidate_models.append(fallback)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=30.0) as client:
            for model_name in candidate_models:
                try:
                    payload = {
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.6,
                        "max_tokens": 1024,
                    }
                    resp = client.post(self.base_url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        return self._parse_llm_response(content)
                    elif resp.status_code == 404:
                        logger.warning(f"Model {model_name} not available (404), trying candidate fallback...")
                        continue
                    else:
                        logger.error(f"LLM API error ({resp.status_code}): {resp.text}")
                        break
                except Exception as e:
                    logger.error(f"LLM call failed with {model_name}: {e}")
                    break

        return None

    async def generate_response(
        self,
        message: str,
        context: Dict[str, Any],
        history: List[Dict] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Async response generation with rule-based fallback"""
        res = self.generate_response_sync(message, context, history, language)
        if res:
            return res
        return self._fallback_response(message, context)

    def _build_system_prompt(self, context: Dict, language: str) -> str:
        """Build rich domain system prompt for hospital equipment operations"""
        language_map = {"en": "English", "sw": "Swahili", "fr": "French"}
        lang_name = language_map.get(language, "English")

        return f"""You are MaishaWatch AI, an intelligent clinical engineering and hospital equipment monitoring assistant in Kenya.
You have real-time visibility into biomedical equipment, failure predictions, Remaining Useful Life (RUL), and operational alerts.

Current System Context:
- User: {context.get('user_name', 'Caleb Munyeki')} ({context.get('role', 'System Administrator')})
- Scope: {context.get('scope_type', 'National Scope')} ({context.get('equipment_count', 150)} assets across {context.get('facility_count', 129)} facilities in Kenya).
- Open Alerts: {context.get('open_alerts', 0)} active alerts ({context.get('critical_alerts', 0)} critical).
- Language: Respond in {lang_name}.

Response Instructions:
1. Provide accurate, professional, and actionable biomedical maintenance guidance.
2. If asked about equipment, failure risk, or alerts, answer authoritatively based on Kenya's healthcare context.
3. Be concise and helpful. Prioritize clinical uptime and patient safety.
4. Output JSON with the following structure:
{{
  "response": "<your conversational answer with markdown formatting>",
  "action": "<general | equipment_status | prediction | alert | maintenance | report>",
  "suggestions": ["<prompt 1>", "<prompt 2>", "<prompt 3>"]
}}
If unable to format as pure JSON, output your response directly as text.
"""

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM output as JSON or extract response text"""
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "response" in parsed:
                return {
                    "response": parsed["response"],
                    "action": parsed.get("action", "general"),
                    "data": parsed.get("data"),
                    "suggestions": parsed.get("suggestions", [
                        "What equipment is due for maintenance?",
                        "Show critical alerts",
                        "Summary of all facilities",
                    ]),
                }
        except Exception:
            pass

        return {
            "response": content,
            "action": "general",
            "data": None,
            "suggestions": [
                "What equipment is due for maintenance?",
                "Show critical alerts",
                "Summary of all facilities",
            ],
        }

    def _fallback_response(self, message: str, context: Dict) -> Dict:
        """Fallback when LLM is offline"""
        return {
            "response": "I'm currently running in baseline monitoring mode. All equipment telemetry and alert systems remain fully active.",
            "action": "fallback",
            "data": {"using_llm": False},
            "suggestions": [
                "What's the status of all equipment?",
                "Show me critical alerts",
                "Predict failures for equipment",
            ],
        }
