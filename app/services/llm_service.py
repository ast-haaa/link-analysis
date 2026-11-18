"""Google Gemini LLM integration service using the official Google GenAI Python SDK.

Handles prompt generation, structured JSON generation with response schemas,
bounded exponential backoff retries, and comprehensive error handling.
"""

import asyncio
import json
import logging
import random
from typing import Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import Settings, get_settings
from app.schemas import ExtractedContent, LLMStructuredAnalysis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom LLM Exceptions
# ---------------------------------------------------------------------------

class LLMServiceError(Exception):
    """Base exception for LLM analysis errors."""

    def __init__(self, message: str, status_code: int = 502, error_code: str = "LLM_ANALYSIS_FAILED"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class GeminiConfigurationError(LLMServiceError):
    """Raised when GEMINI_API_KEY is missing or invalid in configuration."""

    def __init__(
        self,
        message: str = "Gemini API key is not configured. Please set GEMINI_API_KEY in your .env file.",
    ):
        super().__init__(message, status_code=503, error_code="GEMINI_API_KEY_MISSING")


class GeminiRateLimitError(LLMServiceError):
    """Raised when Gemini API rate limit / quota is exhausted."""

    def __init__(self, message: str = "Gemini API rate limit exceeded. Please try again after a brief pause."):
        super().__init__(message, status_code=429, error_code="GEMINI_RATE_LIMIT_EXCEEDED")


class GeminiTimeoutError(LLMServiceError):
    """Raised when Gemini API request times out."""

    def __init__(self, message: str = "AI analysis request timed out waiting for Gemini response."):
        super().__init__(message, status_code=504, error_code="GEMINI_TIMEOUT")


class GeminiResponseParseError(LLMServiceError):
    """Raised when Gemini output cannot be parsed into the structured analysis schema."""

    def __init__(self, message: str = "Failed to parse structured business analysis from Gemini response."):
        super().__init__(message, status_code=502, error_code="GEMINI_RESPONSE_PARSE_ERROR")


class GeminiAPIError(LLMServiceError):
    """Raised for unexpected upstream Gemini API errors."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message, status_code=status_code, error_code="GEMINI_API_ERROR")


# ---------------------------------------------------------------------------
# LLM Service Implementation
# ---------------------------------------------------------------------------

class LLMService:
    """Service encapsulating interactions with Google Gemini API."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.GEMINI_API_KEY
        self.model_name = self.settings.GEMINI_MODEL
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        """Initialize or return the cached Google GenAI Client."""
        if not self.api_key or self.api_key.strip() in ("", "your_gemini_api_key_here"):
            logger.error("GEMINI_API_KEY is not configured in environment or .env file.")
            raise GeminiConfigurationError()

        if self._client is None:
            self._client = genai.Client(
                api_key=self.api_key.strip(),
                http_options={"api_version": "v1beta"},
            )
        return self._client

    def _build_system_instruction(self) -> str:
        """Construct strict system prompt defining analytical constraints and non-fabrication rules."""
        return (
            "You are an elite enterprise business intelligence analyst and digital strategist. "
            "Your task is to analyze raw website content extracted from a specific business domain "
            "and generate five structured, high-value business intelligence sections.\n\n"
            "STRICT ANALYTICAL INTEGRITY RULES:\n"
            "1. SECTION 1 (Competitor Analysis): Extract the brand name, business overview, category, "
            "and products/services. Identify at least 3 direct or indirect market competitors based on "
            "the extracted offerings. Detail their strengths and weaknesses. Articulate the brand's "
            "competitive advantages and positioning opportunities. Clearly flag whether competitors are "
            "AI-inferred from the business category vs explicitly cited on the website. Never claim "
            "verification without evidence.\n"
            "2. SECTION 2 (Target Search Queries): Generate EXACTLY 5 high-intent search queries. "
            "Cover search and social discovery platforms: Google, Facebook, Instagram, LinkedIn, and X. "
            "Include query, platforms, search intent (Informational, Commercial, Transactional, Navigational), "
            "business relevance, and target audience. NEVER FABRICATE SEARCH VOLUMES OR CPC NUMBERS.\n"
            "3. SECTION 3 (SEO Improvements): Base recommendations directly on the extracted content. "
            "Provide primary, secondary, and long-tail keywords. Provide a recommended SEO title (<60 chars) "
            "and meta description (140-160 chars). Recommend blog/content ideas and FAQ schema entries.\n"
            "4. SECTION 4 (Top 5 Services): Identify up to 5 actual services or products from the website. "
            "For each, include service name, description, target industry, target customer, and main benefit. "
            "Explicitly set is_inferred=True for services inferred from context and False for directly stated services. "
            "DO NOT INVENT SERVICES TO FILL 5 ENTRIES IF FEWER EXIST ON THE SITE.\n"
            "5. SECTION 5 (Target Audience): Identify primary and secondary audiences, relevant industries, "
            "business types (B2B, B2C, Enterprise, SMB), customer profiles, core needs/pain points, "
            "geographic focus (only if indicated by site content; otherwise specify Global/Not Specified), "
            "and tactical marketing recommendations.\n\n"
            "Produce structured, objective, professional output strictly conforming to the requested JSON schema."
        )

    def _build_analysis_prompt(self, content: ExtractedContent) -> str:
        """Format sanitized website content into an efficient token-conscious LLM prompt."""
        # Use sanitized clean_text_summary to avoid sending raw HTML noise
        return (
            f"Analyze the following verified website extraction data for domain: {content.url}\n\n"
            f"--- EXTRACTED WEBSITE DATA ---\n"
            f"{content.clean_text_summary}\n\n"
            f"--- RAW METRICS ---\n"
            f"- Title: {content.title}\n"
            f"- Meta Description: {content.meta_description or 'None provided'}\n"
            f"- Extracted Services Detected: {', '.join(content.services) if content.services else 'None explicitly flagged'}\n"
            f"- Total Extracted Word Count: {content.word_count}\n\n"
            f"Generate the comprehensive 5-section business intelligence analysis adhering strictly to all integrity rules."
        )

    async def analyze_website(self, content: ExtractedContent) -> LLMStructuredAnalysis:
        """Call Google Gemini with structured JSON output and bounded exponential backoff retries.

        Returns:
            Validated LLMStructuredAnalysis model containing the 5 analysis sections.

        Raises:
            GeminiConfigurationError: If API key is not configured.
            GeminiRateLimitError: If rate limit / quota is exceeded after retries.
            GeminiTimeoutError: If Gemini API times out.
            GeminiResponseParseError: If model output fails schema validation.
            GeminiAPIError: If an unhandled upstream API error occurs.
        """
        client = self._get_client()
        system_instruction = self._build_system_instruction()
        prompt = self._build_analysis_prompt(content)

        # Ensure active flash model is used if legacy model name was set in environment
        active_model = self.model_name
        if active_model in ("gemini-1.5-flash", "gemini-2.0-flash"):
            logger.info("Upgrading legacy model '%s' to active 'gemini-2.5-flash'", active_model)
            active_model = "gemini-2.5-flash"

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=LLMStructuredAnalysis,
            temperature=self.settings.GEMINI_TEMPERATURE,
        )

        max_retries = max(1, self.settings.GEMINI_MAX_RETRIES)
        base_delay = 1.5
        max_delay = 10.0

        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            logger.info(
                "Invoking Gemini model '%s' for URL '%s' (attempt %d/%d)",
                active_model,
                content.url,
                attempt,
                max_retries,
            )

            try:
                # Wrap API call with timeout guard
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=active_model,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=self.settings.GEMINI_TIMEOUT_SECONDS,
                )

                if not response or not response.text:
                    raise GeminiResponseParseError("Gemini returned an empty response.")

                raw_text = response.text.strip()
                logger.debug("Received Gemini raw response (length: %d chars)", len(raw_text))

                # Parse and validate response with Pydantic
                try:
                    parsed_analysis = LLMStructuredAnalysis.model_validate_json(raw_text)
                    return parsed_analysis
                except Exception as parse_err:
                    logger.warning("Pydantic JSON parsing failed on attempt %d: %s", attempt, parse_err)
                    # Attempt JSON cleanup if markdown code blocks were present
                    cleaned_json = raw_text
                    if "```json" in cleaned_json:
                        cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
                    elif "```" in cleaned_json:
                        cleaned_json = cleaned_json.split("```")[1].split("```")[0].strip()

                    try:
                        parsed_analysis = LLMStructuredAnalysis.model_validate_json(cleaned_json)
                        return parsed_analysis
                    except Exception:
                        raise GeminiResponseParseError(
                            f"Model generated invalid JSON that does not match analysis schema: {parse_err}"
                        ) from parse_err

            except asyncio.TimeoutError as te:
                last_exception = te
                logger.warning("Gemini API call timed out on attempt %d: %s", attempt, te)
                if attempt == max_retries:
                    raise GeminiTimeoutError() from te

            except APIError as api_err:
                last_exception = api_err
                error_code = getattr(api_err, "code", None)
                error_msg = str(api_err)
                logger.warning("Gemini API error (code=%s) on attempt %d: %s", error_code, attempt, error_msg)

                # Rate Limit / Resource Exhausted
                if error_code == 429 or "RESOURCE_EXHAUSTED" in error_msg:
                    if attempt == max_retries:
                        raise GeminiRateLimitError(
                            "Gemini API rate limit or quota exceeded. Please verify quota or retry later."
                        ) from api_err

                # Non-retryable authentication / configuration errors
                elif error_code in (400, 401, 403) or "API_KEY_INVALID" in error_msg:
                    raise GeminiAPIError(
                        f"Gemini API authentication failed (check your GEMINI_API_KEY): {error_msg}",
                        status_code=502,
                    ) from api_err

                # Transient server errors (500, 503, 504)
                elif attempt == max_retries:
                    raise GeminiAPIError(
                        f"Gemini API returned error {error_code}: {error_msg}",
                        status_code=502,
                    ) from api_err

            except LLMServiceError:
                raise

            except Exception as e:
                last_exception = e
                logger.error("Unexpected error during Gemini execution on attempt %d: %s", attempt, e, exc_info=True)
                if attempt == max_retries:
                    raise GeminiAPIError(f"Unexpected error communicating with Gemini: {e}") from e

            # Bounded exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5), max_delay)
            logger.info("Retrying Gemini request in %.2f seconds...", delay)
            await asyncio.sleep(delay)

        # Fallback if loop ends without success
        if isinstance(last_exception, asyncio.TimeoutError):
            raise GeminiTimeoutError()
        raise GeminiAPIError(f"Gemini analysis failed after {max_retries} attempts: {last_exception}")
