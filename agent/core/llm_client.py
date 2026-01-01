"""
LLM Client - Unified interface for OpenRouter and Groq APIs
"""
import json
import base64
import asyncio
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

from agent.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Chat message"""
    role: str  # system, user, assistant
    content: Union[str, List[Dict[str, Any]]]
    
    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}


@dataclass
class CompletionResponse:
    """LLM completion response"""
    content: str
    model: str
    tokens_used: int
    finish_reason: str


class RateLimitError(Exception):
    """Rate limit exceeded"""
    pass


class LLMClient:
    """Unified client for OpenRouter and Groq APIs"""
    
    def __init__(self):
        self.openrouter_key = settings.OPENROUTER_API_KEY
        self.groq_key = settings.GROQ_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_tokens = settings.MAX_API_CALLS_PER_MINUTE
        self._rate_limit_window = 60  # seconds
        self._call_timestamps: List[float] = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        # Remember the asyncio loop this client was created on so other threads
        # can schedule coroutines back onto it via run_coroutine_threadsafe.
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _parse_model(self, model_str: str) -> tuple[str, str]:
        """Parse model string: 'provider:model_name'"""
        if ":" not in model_str:
            raise ValueError(f"Invalid model format: {model_str}. Expected 'provider:model_name'")
        provider, model = model_str.split(":", 1)
        return provider, model
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        import time
        now = time.time()
        
        # Remove old timestamps outside the window
        self._call_timestamps = [
            ts for ts in self._call_timestamps 
            if now - ts < self._rate_limit_window
        ]
        
        if len(self._call_timestamps) >= self._rate_limit_tokens:
            wait_time = self._rate_limit_window - (now - self._call_timestamps[0])
            logger.warning(f"Rate limit reached. Waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        self._call_timestamps.append(now)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def chat_completion(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> CompletionResponse:
        """Send chat completion request"""
        
        await self._check_rate_limit()
        
        model = model or settings.AGENT_MODEL_PRIMARY
        provider, model_name = self._parse_model(model)
        
        logger.info(f"LLM request: {provider}/{model_name}, {len(messages)} messages")
        
        try:
            if provider == "openrouter":
                return await self._openrouter_completion(
                    messages, model_name, temperature, max_tokens, json_mode
                )
            elif provider == "groq":
                return await self._groq_completion(
                    messages, model_name, temperature, max_tokens, json_mode
                )
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            # Try fallback model
            if model != settings.AGENT_MODEL_FALLBACK:
                logger.info(f"Trying fallback model: {settings.AGENT_MODEL_FALLBACK}")
                return await self.fallback_completion(messages, temperature, max_tokens, json_mode)
            raise
    
    async def _openrouter_completion(
        self,
        messages: List[Message],
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> CompletionResponse:
        """OpenRouter API completion"""
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/desktop-agent",
            "X-Title": "Desktop Agent",
        }
        
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        async with self.session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 429:
                raise RateLimitError("OpenRouter rate limit exceeded")
            
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"OpenRouter API error {resp.status}: {error_text}")
                raise Exception(f"OpenRouter API error: {resp.status}")
            
            data = await resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            
            return CompletionResponse(
                content=choice["message"]["content"],
                model=model,
                tokens_used=usage.get("total_tokens", 0),
                finish_reason=choice.get("finish_reason", "unknown")
            )
    
    async def _groq_completion(
        self,
        messages: List[Message],
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> CompletionResponse:
        """Groq API completion"""
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        async with self.session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 429:
                raise RateLimitError("Groq rate limit exceeded")
            
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"Groq API error {resp.status}: {error_text}")
                raise Exception(f"Groq API error: {resp.status}")
            
            data = await resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            
            return CompletionResponse(
                content=choice["message"]["content"],
                model=model,
                tokens_used=usage.get("total_tokens", 0),
                finish_reason=choice.get("finish_reason", "unknown")
            )
    
    async def vision_completion(
        self,
        prompt: str,
        image_data: bytes,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> CompletionResponse:
        """Vision model completion with image"""
        
        model = model or settings.VISION_MODEL_PRIMARY
        provider, model_name = self._parse_model(model)
        
        # Encode image to base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        messages = [
            Message(
                role="user",
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    }
                ]
            )
        ]
        
        logger.info(f"Vision request: {provider}/{model_name}")
        
        if provider == "openrouter":
            return await self._openrouter_completion(
                messages, model_name, temperature, max_tokens, False
            )
        else:
            raise ValueError(f"Vision not supported for provider: {provider}")
    
    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = "en",
    ) -> str:
        """Transcribe audio using Whisper on Groq"""
        
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
        }
        
        form = aiohttp.FormData()
        form.add_field(
            'file', 
            audio_data, 
            filename='audio.wav', 
            content_type='audio/wav'
        )
        form.add_field('model', settings.WHISPER_MODEL)
        form.add_field('language', language)
        form.add_field('response_format', 'json')
        
        logger.info(f"Transcribing audio ({len(audio_data)} bytes)")
        
        async with self.session.post(url, headers=headers, data=form, timeout=30) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"Groq transcription error {resp.status}: {error_text}")
                raise Exception(f"Groq transcription error: {resp.status}")
            
            data = await resp.json()
            text = data["text"]
            logger.info(f"Transcribed: '{text}'")
            return text
    
    async def fallback_completion(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> CompletionResponse:
        """Use fallback model"""
        return await self.chat_completion(
            messages,
            model=settings.AGENT_MODEL_FALLBACK,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )


# Convenience function for synchronous usage
def create_client() -> LLMClient:
    """Create a new LLM client instance"""
    return LLMClient()