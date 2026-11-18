"""FastAPI Application Entry Point.

AI-Powered Website Link Analysis API - Phase 2: Google Gemini Integration & Business Intelligence.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from app.config import get_settings
from app.schemas import (
    ErrorResponse,
    LinkAnalysisRequest,
    LinkAnalysisResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.llm_service import LLMServiceError
from app.services.website_extractor import (
    WebsiteExtractionError,
)
from app.utils.validators import SSRFSecurityError, URLValidationError

# Configure standard logging
settings = get_settings()
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ai_link_analysis")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown routines."""
    logger.info(
        "Starting %s v%s on %s:%d [Env: %s, Gemini Model: %s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.HOST,
        settings.PORT,
        settings.ENVIRONMENT,
        settings.GEMINI_MODEL,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-quality REST API for website content extraction, HTML sanitization, "
        "and AI-powered business intelligence analysis powered by Google Gemini."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(SSRFSecurityError)
async def ssrf_security_exception_handler(request: Request, exc: SSRFSecurityError):
    """Handle SSRF blocked requests with 400 Bad Request."""
    logger.warning("SSRF security block on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            status="error",
            error_code="SSRF_SECURITY_BLOCKED",
            message=str(exc),
            details={"blocked_url": str(request.url)},
        ).model_dump(),
    )


@app.exception_handler(URLValidationError)
async def url_validation_exception_handler(request: Request, exc: URLValidationError):
    """Handle URL syntax or scheme validation failures with 400 Bad Request."""
    logger.info("URL validation failure on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            status="error",
            error_code="INVALID_URL",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(WebsiteExtractionError)
async def website_extraction_exception_handler(request: Request, exc: WebsiteExtractionError):
    """Handle website network and HTML extraction failures."""
    logger.warning("Website extraction failure [%s]: %s", exc.error_code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            status="error",
            error_code=exc.error_code,
            message=exc.message,
        ).model_dump(),
    )


@app.exception_handler(LLMServiceError)
async def llm_service_exception_handler(request: Request, exc: LLMServiceError):
    """Handle Gemini LLM configuration, rate limits, timeouts, and API errors."""
    logger.warning("Gemini LLM error [%s]: %s", exc.error_code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            status="error",
            error_code=exc.error_code,
            message=exc.message,
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic request body validation failures with 422 Unprocessable Content."""
    errors = exc.errors()
    error_details = []
    first_msg = "Invalid request payload."
    for err in errors:
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "")
        error_details.append({"loc": loc, "msg": msg, "type": err.get("type", "")})
        if first_msg == "Invalid request payload.":
            first_msg = msg

    logger.info("Request validation failure on %s: %s", request.url.path, first_msg)
    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content=ErrorResponse(
            status="error",
            error_code="VALIDATION_ERROR",
            message=f"Request validation failed: {first_msg}",
            details=error_details,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled internal exceptions."""
    logger.error("Unhandled internal server error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            status="error",
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred while processing the request.",
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Frontend Static Asset Resolver
# ---------------------------------------------------------------------------

STATIC_INDEX_PATH = Path(__file__).parent / "static" / "index.html"


def get_frontend_html() -> str:
    """Read and return the single-page application HTML frontend."""
    if STATIC_INDEX_PATH.is_file():
        return STATIC_INDEX_PATH.read_text(encoding="utf-8")
    return (
        "<!DOCTYPE html><html><head><title>Link Analysis</title></head>"
        "<body><h1>Link Analysis Dashboard</h1>"
        "<p>Frontend template not found. Please verify app/static/index.html.</p></body></html>"
    )


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get(
    "/dashboard",
    tags=["UI"],
    summary="Link Analysis Interactive Dashboard",
    response_class=HTMLResponse,
)
async def dashboard():
    """Serve the interactive web interface."""
    return HTMLResponse(content=get_frontend_html(), status_code=status.HTTP_200_OK)


@app.get(
    "/",
    tags=["Root"],
    summary="API Root Information and Web Interface",
)
async def root(request: Request):
    """Return API metadata or interactive dashboard based on Accept header."""
    accept = request.headers.get("accept", "")
    # If a browser requests HTML, serve the interactive web interface
    if "text/html" in accept and not accept.strip() == "*/*":
        return HTMLResponse(content=get_frontend_html(), status_code=status.HTTP_200_OK)

    # Return standard API root JSON metadata for automated callers/tests
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": "Phase 2: Google Gemini Integration and Complete AI-Powered Website Analysis",
        "status": "operational",
        "model": settings.GEMINI_MODEL,
        "documentation": "/docs",
        "dashboard": "/dashboard",
        "endpoints": {
            "dashboard": "GET /dashboard",
            "health": "GET /health",
            "link_analysis": "POST /link-analysis",
        },
    }


@app.get(
    "/health",
    tags=["System"],
    summary="Health Check",
    response_model=dict,
)
async def health_check():
    """Health check endpoint for deployment monitoring (Render, K8s, Uptime)."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "phase": 2,
        "model": settings.GEMINI_MODEL,
        "api_key_configured": bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here"),
    }


@app.post(
    "/link-analysis",
    tags=["Analysis"],
    summary="Extract and Analyze Website Link with AI",
    response_model=LinkAnalysisResponse,
    responses={
        200: {"model": LinkAnalysisResponse, "description": "Website successfully extracted and analyzed."},
        400: {"model": ErrorResponse, "description": "Invalid URL or SSRF security restriction."},
        413: {"model": ErrorResponse, "description": "Target webpage exceeded maximum permitted size."},
        422: {"model": ErrorResponse, "description": "Validation error or unsupported content type."},
        429: {"model": ErrorResponse, "description": "Gemini API rate limit or quota exceeded."},
        502: {"model": ErrorResponse, "description": "Upstream connection error or Gemini parsing failure."},
        503: {"model": ErrorResponse, "description": "Gemini API key is unconfigured or service unavailable."},
        504: {"model": ErrorResponse, "description": "Upstream request or Gemini call timed out."},
    },
)
async def analyze_link(payload: LinkAnalysisRequest):
    """Accept a website URL, extract its actual content, sanitize HTML clutter,

    and generate five structured business intelligence sections using Google Gemini.
    """
    logger.info("Received link-analysis request for URL: %s", payload.url)
    analysis_service = AnalysisService(settings=settings)
    return await analysis_service.analyze_url(payload.url)


# ---------------------------------------------------------------------------
# CLI / Local Server Launcher
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
