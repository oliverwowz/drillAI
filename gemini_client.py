"""DrillAI Gemini API Client.

Handles communication with Google's Gemini API for image analysis.
Implements retry logic, rate limiting, and error handling.
"""

import io
import json
import logging
import time
from typing import Any, Dict, Optional

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger("drillai.gemini")


class GeminiClientError(Exception):
    """Base exception for Gemini client errors."""
    pass


class GeminiAuthError(GeminiClientError):
    """Authentication or API key error."""
    pass


class GeminiModelError(GeminiClientError):
    """Model not found or unsupported."""
    pass


class GeminiRateLimitError(GeminiClientError):
    """Rate limit or quota exceeded."""
    pass


class GeminiClient:
    """Client for Google Gemini API with image analysis capabilities.
    
    Handles authentication, request formatting, retry logic,
    and structured response parsing.
    """
    
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0
    DEFAULT_MAX_DELAY = 30.0
    DEFAULT_TIMEOUT = 60
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-genai is not installed. Install with: pip install google-genai"
            )
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow is not installed. Install with: pip install Pillow"
            )
        if not api_key:
            raise GeminiAuthError(
                "API key is required. Set GEMINI_API_KEY in your .env file."
            )
        
        self.model_name = model_name
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self._request_count = 0
        self._last_request_hash: Optional[str] = None
        
        try:
            self.client = genai.Client(api_key=api_key)
            logger.info(f"Gemini client initialized with model: {model_name}")
        except Exception as e:
            raise GeminiAuthError(f"Failed to initialize Gemini client: {e}") from e
    
    def verify_model(self) -> Dict[str, Any]:
        """Verify that the configured model is available.
        
        Returns:
            Dict with model information.
            
        Raises:
            GeminiModelError: If model is not available.
            GeminiAuthError: If authentication fails.
        """
        try:
            model = self.client.models.get(model=f"models/{self.model_name}")
            info = {
                "name": model.name,
                "display_name": getattr(model, 'display_name', self.model_name),
                "supported_methods": getattr(model, 'supported_generation_methods', []),
            }
            logger.info(f"Model verified: {info['display_name']}")
            return info
        except Exception as e:
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                raise GeminiModelError(
                    f"Model '{self.model_name}' not found. "
                    f"Check available models at https://ai.google.dev/models"
                ) from e
            elif "401" in error_str or "403" in error_str or "auth" in error_str or "key" in error_str:
                raise GeminiAuthError(
                    "Authentication failed. Check your GEMINI_API_KEY."
                ) from e
            else:
                raise GeminiClientError(f"Failed to verify model: {e}") from e
    
    def _image_to_part(self, image: Image.Image) -> types.Part:
        """Convert PIL Image to Gemini API Part.
        
        Args:
            image: PIL Image to convert.
            
        Returns:
            Gemini API Part with inline image data.
        """
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        
        return types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/png",
        )
    
    def analyze_image(
        self,
        image: Image.Image,
        system_instruction: str,
        prompt: str,
        image_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an image to Gemini for analysis.
        
        Args:
            image: PIL Image to analyze.
            system_instruction: System instruction for the model.
            prompt: User prompt describing what to analyze.
            image_hash: Optional hash to prevent duplicate requests.
            
        Returns:
            Parsed JSON response from Gemini.
            
        Raises:
            GeminiClientError: On permanent failures.
            GeminiRateLimitError: On rate limiting.
        """
        # Duplicate check
        if image_hash and image_hash == self._last_request_hash:
            logger.debug("Skipping duplicate image request")
            return {"_skipped": True, "reason": "Duplicate image"}
        
        image_part = self._image_to_part(image)
        
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=f"models/{self.model_name}",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[image_part, types.Part.from_text(text=prompt)],
                        )
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1,
                        max_output_tokens=4096,
                    ),
                )
                
                self._request_count += 1
                if image_hash:
                    self._last_request_hash = image_hash
                
                # Extract and parse response
                return self._parse_response(response)
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Don't retry auth errors
                if "401" in error_str or "403" in error_str or "auth" in error_str:
                    raise GeminiAuthError(f"Authentication failed: {e}") from e
                
                # Don't retry model not found
                if "404" in error_str and "model" in error_str:
                    raise GeminiModelError(f"Model not found: {e}") from e
                
                # Rate limiting or temporary high demand (503/429) - retry with backoff
                if "429" in error_str or "503" in error_str or "rate" in error_str or "quota" in error_str or "unavailable" in error_str:
                    if attempt < self.max_retries:
                        delay = min(
                            max(2.0, self.base_delay) * (2 ** attempt),
                            self.max_delay,
                        )
                        logger.warning(
                            f"Server busy or rate limited ({error_str[:60]}). Retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        # Try fallback model if available
                        fallback_model = "gemini-3-flash-preview" if "3.8" in self.model_name else "gemini-3.8-flash"
                        if self.model_name != fallback_model:
                            logger.warning(
                                f"Model {self.model_name} unavailable after {self.max_retries} retries. "
                                f"Switching to fallback model: {fallback_model}"
                            )
                            try:
                                fb_response = self.client.models.generate_content(
                                    model=f"models/{fallback_model}",
                                    contents=[
                                        types.Content(
                                            role="user",
                                            parts=[image_part, types.Part.from_text(text=prompt)],
                                        )
                                    ],
                                    config=types.GenerateContentConfig(
                                        system_instruction=system_instruction,
                                        temperature=0.1,
                                        max_output_tokens=4096,
                                    ),
                                )
                                self._request_count += 1
                                if image_hash:
                                    self._last_request_hash = image_hash
                                return self._parse_response(fb_response)
                            except Exception as fb_err:
                                logger.error(f"Fallback model {fallback_model} also failed: {fb_err}")
                        
                        if "429" in error_str:
                            raise GeminiRateLimitError(
                                f"Rate limit exceeded after {self.max_retries} retries: {e}"
                            ) from e
                        raise GeminiClientError(
                            f"Service unavailable after {self.max_retries} retries: {e}"
                        ) from e
                
                # Transient errors - retry with backoff
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (2 ** attempt),
                        self.max_delay,
                    )
                    logger.warning(
                        f"Request failed: {e}. Retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                else:
                    raise GeminiClientError(
                        f"Request failed after {self.max_retries} retries: {e}"
                    ) from e
        
        raise GeminiClientError(f"Request failed: {last_error}")
    
    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse and validate a Gemini API response.
        
        Args:
            response: Raw response from the Gemini API.
            
        Returns:
            Parsed dict from the response JSON.
            
        Raises:
            GeminiClientError: If response parsing fails.
        """
        try:
            if not response or not response.text:
                raise GeminiClientError("Empty response from Gemini")
            
            text = response.text.strip()
            
            # Strip markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first and last lines (code fences)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            
            # Try to parse JSON
            try:
                result = json.loads(text)
                if isinstance(result, dict):
                    return result
                else:
                    return {"raw_response": result}
            except json.JSONDecodeError:
                # If not valid JSON, return as raw text
                logger.warning("Response is not valid JSON, returning as raw text")
                return {
                    "raw_text": text,
                    "parse_error": True,
                }
                
        except GeminiClientError:
            raise
        except Exception as e:
            raise GeminiClientError(f"Failed to parse response: {e}") from e
    
    @property
    def request_count(self) -> int:
        """Total number of API requests made."""
        return self._request_count
    
    def health_check(self) -> Dict[str, Any]:
        """Perform a basic health check.
        
        Returns:
            Dict with health check results.
        """
        result = {
            "api_key_set": True,
            "model": self.model_name,
            "model_available": False,
            "error": None,
        }
        try:
            model_info = self.verify_model()
            result["model_available"] = True
            result["model_info"] = model_info
        except Exception as e:
            result["error"] = str(e)
        
        return result
