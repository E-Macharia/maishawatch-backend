# app/services/voice_service.py
import os
import base64
from typing import Optional
import httpx
import logging

logger = logging.getLogger(__name__)

class VoiceService:
    """Voice support for chat"""
    
    def __init__(self):
        self.elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
        self.elevenlabs_voice = os.getenv('ELEVENLABS_VOICE', '21m00Tcm4TlvDq8ikWAM')
        self.use_elevenlabs = bool(self.elevenlabs_api_key)
        
        # Speech-to-text
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.use_whisper = bool(self.openai_api_key)
    
    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """Convert text to speech (TTS)"""
        if self.use_elevenlabs:
            return await self._elevenlabs_tts(text)
        else:
            # Fallback - return None
            logger.warning("No TTS API configured")
            return None
    
    async def _elevenlabs_tts(self, text: str) -> bytes:
        """ElevenLabs TTS"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice}",
                    headers={
                        "xi-api-key": self.elevenlabs_api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": text,
                        "model_id": "eleven_monolingual_v1",
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.5
                        }
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return response.content
                else:
                    logger.error(f"ElevenLabs TTS error: {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"TTS error: {e}")
                return None
    
    async def speech_to_text(self, audio_data: bytes) -> Optional[str]:
        """Convert speech to text (STT) using Whisper"""
        if self.use_whisper:
            return await self._whisper_stt(audio_data)
        else:
            logger.warning("No STT API configured")
            return None
    
    async def _whisper_stt(self, audio_data: bytes) -> str:
        """OpenAI Whisper STT"""
        async with httpx.AsyncClient() as client:
            try:
                files = {
                    'file': ('audio.wav', audio_data, 'audio/wav'),
                    'model': (None, 'whisper-1'),
                    'language': (None, 'en')
                }
                
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}"
                    },
                    files=files,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('text', '')
                else:
                    logger.error(f"Whisper STT error: {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"STT error: {e}")
                return None