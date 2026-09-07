# app/services/llm_service.py
import os
import json
from typing import Optional, List, Dict, Any
import httpx
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """Service for integrating with LLM APIs"""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        self.claude_api_key = os.getenv("CLAUDE_API_KEY")
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229")
        self.use_openai = bool(self.openai_api_key)
        self.use_claude = bool(self.claude_api_key)

    async def generate_response(
        self,
        message: str,
        context: Dict[str, Any],
        history: List[Dict] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Generate response using LLM"""
        if self.use_openai:
            return await self._call_openai(message, context, history, language)
        elif self.use_claude:
            return await self._call_claude(message, context, history, language)
        else:
            # Fallback to rule-based response
            return self._fallback_response(message, context)

    async def _call_openai(
        self, message: str, context: Dict, history: List[Dict], language: str
    ) -> Dict:
        """Call OpenAI API"""
        system_prompt = self._build_system_prompt(context, language)

        messages = [{"role": "system", "content": system_prompt}]

        # Add history if available
        if history:
            for msg in history[-10:]:  # Last 10 messages for context
                messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )

        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.openai_model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    return self._parse_llm_response(content)
                else:
                    logger.error(f"OpenAI API error: {response.text}")
                    return self._fallback_response(message, context)

            except Exception as e:
                logger.error(f"OpenAI call failed: {e}")
                return self._fallback_response(message, context)

    async def _call_claude(
        self, message: str, context: Dict, history: List[Dict], language: str
    ) -> Dict:
        """Call Claude API"""
        system_prompt = self._build_system_prompt(context, language)

        messages = []
        if history:
            for msg in history[-10:]:
                messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )

        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.claude_api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.claude_model,
                        "system": system_prompt,
                        "messages": messages,
                        "max_tokens": 1000,
                        "temperature": 0.7,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["content"][0]["text"]
                    return self._parse_llm_response(content)
                else:
                    logger.error(f"Claude API error: {response.text}")
                    return self._fallback_response(message, context)

            except Exception as e:
                logger.error(f"Claude call failed: {e}")
                return self._fallback_response(message, context)

    def _build_system_prompt(self, context: Dict, language: str) -> str:
        """Build system prompt for LLM"""
        language_map = {"en": "English", "sw": "Swahili", "fr": "French"}
        lang_name = language_map.get(language, "English")

        return f"""
        You are MaishaWatch AI Assistant, a medical equipment management expert.
        
        Current Context:
        - Role: {context.get('role', 'Unknown')}
        - Scope: {context.get('scope_type', 'Unknown')}
        - Equipment Count: {context.get('equipment_count', 0)}
        - Facility Count: {context.get('facility_count', 0)}
        - Language: {lang_name}
        
        Respond in {lang_name}.
        
        You help users with:
        1. Equipment status and details
        2. Failure predictions and RUL
        3. Alert management
        4. Maintenance recommendations
        5. Reports and analytics
        6. Operational guidance
        
        Format your response as JSON with:
        - "response": The main response text
        - "action": The action to take (equipment_status, prediction, alert, maintenance, report, etc.)
        - "data": Any structured data to display
        - "suggestions": List of follow-up suggestions
        
        Be concise, professional, and helpful.
        """

    def _parse_llm_response(self, content: str) -> Dict:
        """Parse LLM response JSON"""
        try:
            # Try to parse as JSON
            result = json.loads(content)
            # Ensure required fields
            if "response" not in result:
                result["response"] = content
            if "action" not in result:
                result["action"] = "general"
            if "suggestions" not in result:
                result["suggestions"] = []
            return result
        except json.JSONDecodeError:
            # Fallback: wrap in expected format
            return {
                "response": content,
                "action": "general",
                "data": None,
                "suggestions": [],
            }

    def _fallback_response(self, message: str, context: Dict) -> Dict:
        """Fallback rule-based response when LLM is unavailable"""
        # Use the existing ChatService for fallback
        from app.services.chat_service import ChatService

        # This will be handled by the main chat service
        return {
            "response": "I'm currently using my base knowledge. For more advanced responses, please configure an LLM API key.",
            "action": "fallback",
            "data": {"using_llm": False},
            "suggestions": ["Help", "Equipment status", "Alerts"],
        }
