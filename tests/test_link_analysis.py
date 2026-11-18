"""Comprehensive test suite for Phase 1 & Phase 2: Website Link Analysis API.

Tests URL validation, SSRF protections, HTML extraction, boilerplate sanitization,
Google Gemini LLM integration, structured 5-section AI business analysis,
retry logic, error recovery, and response contract validation.
"""

import asyncio
from datetime import datetime, timezone
import ipaddress
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from google.genai.errors import APIError
import httpx

from app.config import Settings
from app.main import app
from app.schemas import (
    AudienceSegment,
    BrandSummary,
    CompetitorAnalysis,
    CompetitorItem,
    CompleteBusinessAnalysis,
    ContentRecommendation,
    ExtractedContent,
    FAQItem,
    KeywordStrategy,
    LLMStructuredAnalysis,
    SearchQueriesSection,
    SEOImprovements,
    ServiceOffering,
    ServicesSection,
    TargetAudienceSection,
    TargetSearchQuery,
)
from app.services.analysis_service import AnalysisService
from app.services.competitor_service import CompetitorService
from app.services.llm_service import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiRateLimitError,
    GeminiResponseParseError,
    GeminiTimeoutError,
    LLMService,
)
from app.services.website_extractor import (
    ConnectionTimeoutError,
    HTTPStatusExtractionError,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
    UpstreamConnectionError,
    WebsiteExtractor,
)
from app.utils.validators import (
    SSRFSecurityError,
    URLValidationError,
    is_ip_allowed,
    resolve_and_validate_host,
    validate_url,
)

client = TestClient(app)

# Sample rich HTML fixture representing a modern business website
SAMPLE_COMPANY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>NovaFlow - Next-Generation Cloud Intelligence & AI Ops</title>
    <meta name="description" content="NovaFlow automates enterprise cloud workflows, optimizes cloud spend, and deploys autonomous AI agents.">
    <style>body { font-family: sans-serif; } .banner { background: #333; }</style>
    <script>console.log("Analytics tracker initialized");</script>
</head>
<body>
    <header>
        <div class="logo">NovaFlow Inc.</div>
        <nav>
            <a href="/">Home</a>
            <a href="/services">Services</a>
            <a href="/pricing">Pricing</a>
            <a href="https://blog.novaflow.io">Blog</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>

    <main>
        <h1>Autonomous Cloud Management for Modern Enterprises</h1>
        <p>NovaFlow delivers an intelligent automation engine that streamlines hybrid-cloud operations and slashes operational costs by up to 45%.</p>

        <section id="services" class="services-overview">
            <h2>Our Core Services</h2>
            <div class="service-card">
                <h3>Cloud Spend Optimization</h3>
                <p>Continuous algorithmic resource reallocation to eliminate idle compute and reduce AWS/GCP bills.</p>
            </div>
            <div class="service-card">
                <h3>Autonomous Incident Remediation</h3>
                <p>Self-healing infrastructure workflows that detect, triage, and resolve production outages in seconds.</p>
            </div>
            <div class="service-card">
                <h3>Multi-Cloud Kubernetes Governance</h3>
                <p>Unified compliance, policy enforcement, and observability across all container clusters.</p>
            </div>
        </section>

        <section class="about-section">
            <h2>Why Leading Engineering Teams Choose NovaFlow</h2>
            <p>Built by former hyperscaler engineers, our platform secures and manages over 50,000 workloads worldwide with 99.99% availability.</p>
            <p>Our patent-pending AI orchestration models anticipate capacity bottlenecks hours before they degrade end-user experience.</p>
        </section>
    </main>

    <div class="cookie-banner">
        <p>We use cookies to improve your user experience. Accept all cookies.</p>
    </div>

    <footer>
        <p>© 2026 NovaFlow Technologies Inc. All rights reserved.</p>
        <a href="/privacy">Privacy Policy</a>
        <a href="/terms">Terms of Service</a>
    </footer>
</body>
</html>
"""

# Complete, verified mock structured analysis payload for testing
MOCK_STRUCTURED_ANALYSIS = LLMStructuredAnalysis(
    brand=BrandSummary(
        brand_name="NovaFlow",
        business_overview="Autonomous cloud management and AI Ops platform that streamlines multi-cloud workflows.",
        category="Cloud Computing & DevOps Automation",
        products_and_services=[
            "Cloud Spend Optimization",
            "Autonomous Incident Remediation",
            "Multi-Cloud Kubernetes Governance",
        ],
    ),
    competitor_analysis=CompetitorAnalysis(
        brand_name="NovaFlow",
        business_overview="Autonomous cloud management and AI Ops platform that streamlines multi-cloud workflows.",
        category="Cloud Computing & DevOps Automation",
        products_and_services=[
            "Cloud Spend Optimization",
            "Autonomous Incident Remediation",
            "Multi-Cloud Kubernetes Governance",
        ],
        competitors=[
            CompetitorItem(
                name="Datadog",
                category_or_type="Direct Competitor",
                strengths=["Extensive integration ecosystem", "Broad enterprise market share"],
                weaknesses=["Unpredictable usage-based billing", "High configuration complexity"],
                is_inferred=True,
                evidence_source="ai_inferred_industry_standard",
            ),
            CompetitorItem(
                name="Dynatrace",
                category_or_type="Direct Competitor",
                strengths=["Deep automated root-cause analysis", "Strong APM heritage"],
                weaknesses=["Heavy resource overhead", "Steep administrative learning curve"],
                is_inferred=True,
                evidence_source="ai_inferred_industry_standard",
            ),
            CompetitorItem(
                name="Cast AI",
                category_or_type="Direct Competitor",
                strengths=["Specialized automated Kubernetes cost optimization"],
                weaknesses=["Limited multi-cloud non-container governance"],
                is_inferred=True,
                evidence_source="ai_inferred_industry_standard",
            ),
        ],
        competitive_advantages=[
            "Autonomous self-healing infrastructure workflows",
            "Unified cost reduction and operational incident triage in one console",
        ],
        positioning_opportunities=[
            "Target mid-market engineering teams seeking hands-off infrastructure optimization",
            "Position as a cost-effective alternative to monolithic legacy APM suites",
        ],
        verification_note="Competitors are AI-inferred based on industry benchmarks.",
    ),
    target_search_queries=SearchQueriesSection(
        queries=[
            TargetSearchQuery(
                query="best autonomous kubernetes cost optimization platform",
                platforms=["Google", "LinkedIn"],
                search_intent="Commercial",
                business_relevance="High intent for platform engineers looking to reduce cloud bills.",
                target_audience="Platform Engineering Directors and DevOps Leads",
            ),
            TargetSearchQuery(
                query="how to automate incident remediation in aws",
                platforms=["Google", "X"],
                search_intent="Informational",
                business_relevance="Attracts SREs researching automated self-healing systems.",
                target_audience="Site Reliability Engineers",
            ),
            TargetSearchQuery(
                query="datadog alternatives for automated cloud management",
                platforms=["Google", "LinkedIn", "X"],
                search_intent="Commercial",
                business_relevance="Directly intercepts buyers evaluating replacements for incumbents.",
                target_audience="VPs of Engineering and CTOs",
            ),
            TargetSearchQuery(
                query="multi-cloud kubernetes governance policy enforcement",
                platforms=["Google", "LinkedIn"],
                search_intent="Informational",
                business_relevance="Engages enterprise security and platform architects.",
                target_audience="Enterprise Cloud Architects",
            ),
            TargetSearchQuery(
                query="novaflow pricing and live demo",
                platforms=["Google", "LinkedIn", "X"],
                search_intent="Navigational",
                business_relevance="Bottom-of-funnel decision makers ready to purchase.",
                target_audience="Procurement and Engineering Leadership",
            ),
        ],
        supported_platforms=["Google", "Facebook", "Instagram", "LinkedIn", "X"],
        volume_disclaimer="Search volumes are intentionally not fabricated. Queries are modeled based on audience intent.",
    ),
    seo_improvements=SEOImprovements(
        keywords=KeywordStrategy(
            primary_keywords=["autonomous cloud management", "ai ops platform", "kubernetes cost optimization"],
            secondary_keywords=["multi-cloud governance", "automated incident remediation", "cloud spend reduction"],
            long_tail_keywords=[
                "how to automate kubernetes cluster rightsizing",
                "ai ops tools for hybrid cloud enterprises",
                "real-time cloud cost anomaly detection",
            ],
        ),
        recommended_seo_title="NovaFlow | Autonomous Cloud Intelligence & AI Ops",
        recommended_meta_description="Slash cloud spend by 45% and eliminate downtime with NovaFlow's autonomous AI Ops and Kubernetes management platform. Request a demo today.",
        content_recommendations=[
            ContentRecommendation(
                title="The Complete Guide to Automated Kubernetes Rightsizing in 2026",
                content_type="guide",
                target_keyword="kubernetes cost optimization",
                summary_or_outline="Technical breakdown of automated cluster autoscaling, waste elimination, and finops.",
            ),
            ContentRecommendation(
                title="How Autonomous Incident Remediation Cuts MTTR from Hours to Seconds",
                content_type="blog_post",
                target_keyword="automated incident remediation",
                summary_or_outline="Real-world case studies of self-healing infrastructure in production environments.",
            ),
        ],
        recommended_faqs=[
            FAQItem(
                question="How does NovaFlow connect to our existing cloud infrastructure?",
                recommended_answer="NovaFlow integrates via secure, read/write IAM roles or Kubernetes operators with zero agent footprint.",
            ),
            FAQItem(
                question="Can NovaFlow make automated changes without human approval?",
                recommended_answer="Yes, teams can configure full autonomous execution or require one-click approval workflows.",
            ),
        ],
        rationale="Recommendations align target search terms directly with NovaFlow's core value pillars extracted from the website.",
    ),
    top_services=ServicesSection(
        services=[
            ServiceOffering(
                service_name="Cloud Spend Optimization",
                description="Continuous algorithmic resource reallocation to eliminate idle compute and reduce cloud bills.",
                target_industry="Technology & Financial Services",
                target_customer="VP of Engineering & FinOps Managers",
                main_benefit="Up to 45% reduction in AWS, GCP, and Azure cloud expenditure.",
                is_inferred=False,
                evidence_source="extracted_from_page",
            ),
            ServiceOffering(
                service_name="Autonomous Incident Remediation",
                description="Self-healing infrastructure workflows that detect, triage, and resolve production outages.",
                target_industry="SaaS & Digital Banking",
                target_customer="Site Reliability Engineers & DevOps Teams",
                main_benefit="Drastic reduction in MTTR and pager fatigue.",
                is_inferred=False,
                evidence_source="extracted_from_page",
            ),
            ServiceOffering(
                service_name="Multi-Cloud Kubernetes Governance",
                description="Unified compliance, policy enforcement, and observability across container clusters.",
                target_industry="Enterprise Software",
                target_customer="Cloud Architects & Security Leaders",
                main_benefit="Consistent policy enforcement across distributed clusters.",
                is_inferred=False,
                evidence_source="extracted_from_page",
            ),
        ],
        total_identified=3,
        extraction_note="Services are derived strictly from page content; inferred capabilities are explicitly labeled.",
    ),
    target_audience=TargetAudienceSection(
        primary_audience=AudienceSegment(
            segment_name="Cloud Engineering & Platform Leaders",
            tier="Primary",
            customer_profile="CTOs, VPs of Infrastructure, and Platform Directors managing complex multi-cloud deployments.",
            core_needs_and_pain_points=[
                "Spiraling cloud infrastructure costs",
                "Frequent microservice downtime and alert fatigue",
                "Lack of unified visibility across hybrid cloud environments",
            ],
        ),
        secondary_audiences=[
            AudienceSegment(
                segment_name="FinOps & IT Procurement Executives",
                tier="Secondary",
                customer_profile="Finance and Operations Directors responsible for IT cost governance and software efficiency.",
                core_needs_and_pain_points=[
                    "Unpredictable month-to-month cloud bills",
                    "Difficulty attributing cloud spend to specific product units",
                ],
            )
        ],
        target_industries=[
            "Enterprise B2B SaaS",
            "Financial Technology (FinTech)",
            "E-Commerce & Digital Retail",
            "Healthcare Technology",
        ],
        target_business_types=["B2B Enterprise", "Scale-Up / Growth Stage", "Mid-Market Tech"],
        geographic_focus="Global",
        marketing_recommendations=[
            "Publish technical benchmarking whitepapers comparing autonomous remediation against traditional APMs on LinkedIn.",
            "Run intent-driven Google Search campaigns targeting high-cost keywords like 'Kubernetes finops tool'.",
            "Sponsor practitioner talks at DevOps Days and KubeCon.",
        ],
    ),
)


# ---------------------------------------------------------------------------
# 1. System Health & Root Endpoints
# ---------------------------------------------------------------------------

def test_health_check_endpoint():
    """Verify health check returns 200 OK, valid status, and phase 2 indicator."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["phase"] == 2
    assert "model" in data


def test_root_endpoint():
    """Verify API root metadata returns 200 OK and endpoint catalog."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert "Phase 2" in data["phase"]


# ---------------------------------------------------------------------------
# 2. Complete Phase 2 POST /link-analysis with Mocked Fetch & LLM
# ---------------------------------------------------------------------------

def test_link_analysis_success_mocked():
    """Verify POST /link-analysis executes end-to-end extraction and 5-section AI analysis."""
    mock_url = "https://novaflow.io"

    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(return_value=(SAMPLE_COMPANY_HTML, mock_url, len(SAMPLE_COMPANY_HTML.encode("utf-8")))),
    ), patch.object(
        LLMService,
        "analyze_website",
        new=AsyncMock(return_value=MOCK_STRUCTURED_ANALYSIS),
    ):
        response = client.post("/link-analysis", json={"url": mock_url})
        assert response.status_code == 200
        result = response.json()

        # Contract requirements: success, website, brand, analysis
        assert result["success"] is True
        assert result["status"] == "success"

        # 1. Website block
        website = result["website"]
        assert website["url"] == mock_url
        assert website["title"] == "NovaFlow - Next-Generation Cloud Intelligence & AI Ops"
        assert "NovaFlow automates enterprise cloud workflows" in website["meta_description"]
        assert website["word_count"] > 20
        assert website["raw_html_size_bytes"] > 100

        # 2. Brand block
        brand = result["brand"]
        assert brand["brand_name"] == "NovaFlow"
        assert "Autonomous cloud management" in brand["business_overview"]
        assert "Cloud Computing" in brand["category"]
        assert len(brand["products_and_services"]) >= 3

        # 3. Analysis block (The Five Required Sections)
        analysis = result["analysis"]

        # Section 1: Competitor Analysis
        comp = analysis["competitor_analysis"]
        assert comp["brand_name"] == "NovaFlow"
        assert len(comp["competitors"]) >= 3
        for competitor in comp["competitors"]:
            assert "name" in competitor
            assert len(competitor["strengths"]) > 0
            assert len(competitor["weaknesses"]) > 0
            assert "is_inferred" in competitor
            assert "evidence_source" in competitor
        assert len(comp["competitive_advantages"]) >= 1
        assert len(comp["positioning_opportunities"]) >= 1
        assert "verification_note" in comp

        # Section 2: Target Search Queries
        queries = analysis["target_search_queries"]
        assert len(queries["queries"]) == 5  # exactly 5 queries required
        for q in queries["queries"]:
            assert "query" in q
            assert len(q["platforms"]) >= 1
            assert q["search_intent"] in ("Informational", "Commercial", "Transactional", "Navigational")
            assert "business_relevance" in q
            assert "target_audience" in q
        assert "volume_disclaimer" in queries

        # Section 3: SEO Improvements
        seo = analysis["seo_improvements"]
        assert len(seo["keywords"]["primary_keywords"]) >= 1
        assert len(seo["keywords"]["secondary_keywords"]) >= 1
        assert len(seo["keywords"]["long_tail_keywords"]) >= 1
        assert len(seo["recommended_seo_title"]) > 0
        assert len(seo["recommended_meta_description"]) > 0
        assert len(seo["content_recommendations"]) >= 1
        assert len(seo["recommended_faqs"]) >= 1

        # Section 4: Top 5 Services
        services = analysis["top_services"]
        assert 1 <= len(services["services"]) <= 5
        for s in services["services"]:
            assert "service_name" in s
            assert "description" in s
            assert "target_industry" in s
            assert "target_customer" in s
            assert "main_benefit" in s
            assert "is_inferred" in s
            assert "evidence_source" in s
        assert services["total_identified"] == len(services["services"])

        # Section 5: Target Audience
        audience = analysis["target_audience"]
        assert audience["primary_audience"]["tier"] == "Primary"
        assert len(audience["secondary_audiences"]) >= 1
        assert len(audience["target_industries"]) >= 1
        assert len(audience["target_business_types"]) >= 1
        assert len(audience["marketing_recommendations"]) >= 1


# ---------------------------------------------------------------------------
# 3. Gemini Error Handling & Resiliency Tests
# ---------------------------------------------------------------------------

def test_gemini_missing_api_key_error():
    """Verify 503 error when GEMINI_API_KEY is not configured or blank."""
    mock_url = "https://example.com"

    # Simulate missing API key
    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(return_value=(SAMPLE_COMPANY_HTML, mock_url, len(SAMPLE_COMPANY_HTML))),
    ), patch.object(
        LLMService,
        "analyze_website",
        new=AsyncMock(side_effect=GeminiConfigurationError()),
    ):
        response = client.post("/link-analysis", json={"url": mock_url})
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "GEMINI_API_KEY_MISSING"
        # Ensure no fake AI analysis is returned
        assert "analysis" not in data


def test_gemini_rate_limit_handling():
    """Verify 429 Too Many Requests when Gemini API quota is exhausted."""
    mock_url = "https://example.com"

    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(return_value=(SAMPLE_COMPANY_HTML, mock_url, len(SAMPLE_COMPANY_HTML))),
    ), patch.object(
        LLMService,
        "analyze_website",
        new=AsyncMock(side_effect=GeminiRateLimitError()),
    ):
        response = client.post("/link-analysis", json={"url": mock_url})
        assert response.status_code == 429
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "GEMINI_RATE_LIMIT_EXCEEDED"


def test_gemini_timeout_handling():
    """Verify 504 Gateway Timeout when Gemini API request times out."""
    mock_url = "https://example.com"

    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(return_value=(SAMPLE_COMPANY_HTML, mock_url, len(SAMPLE_COMPANY_HTML))),
    ), patch.object(
        LLMService,
        "analyze_website",
        new=AsyncMock(side_effect=GeminiTimeoutError()),
    ):
        response = client.post("/link-analysis", json={"url": mock_url})
        assert response.status_code == 504
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "GEMINI_TIMEOUT"


def test_gemini_malformed_json_response():
    """Verify 502 Bad Gateway when Gemini output fails JSON schema validation."""
    mock_url = "https://example.com"

    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(return_value=(SAMPLE_COMPANY_HTML, mock_url, len(SAMPLE_COMPANY_HTML))),
    ), patch.object(
        LLMService,
        "analyze_website",
        new=AsyncMock(side_effect=GeminiResponseParseError("Invalid schema JSON")),
    ):
        response = client.post("/link-analysis", json={"url": mock_url})
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "GEMINI_RESPONSE_PARSE_ERROR"


def test_gemini_api_server_error():
    """Verify 502 Bad Gateway when upstream Gemini returns 500 error."""
    mock_url = "https://example.com"

    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(return_value=(SAMPLE_COMPANY_HTML, mock_url, len(SAMPLE_COMPANY_HTML))),
    ), patch.object(
        LLMService,
        "analyze_website",
        new=AsyncMock(side_effect=GeminiAPIError("Internal Google server error", status_code=502)),
    ):
        response = client.post("/link-analysis", json={"url": mock_url})
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "GEMINI_API_ERROR"


# ---------------------------------------------------------------------------
# 4. URL Syntax and Input Validation
# ---------------------------------------------------------------------------

def test_missing_request_body():
    """Verify 422 on empty request payload."""
    response = client.post("/link-analysis", json={})
    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_empty_url_string():
    """Verify 422 on empty URL string."""
    response = client.post("/link-analysis", json={"url": "   "})
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_non_string_url():
    """Verify 422 when URL is not a string."""
    response = client.post("/link-analysis", json={"url": 12345})
    assert response.status_code == 422


def test_disallowed_schemes():
    """Verify rejection of non-HTTP/HTTPS schemes (ftp, file, javascript, data)."""
    disallowed_urls = [
        "ftp://ftp.example.com/files",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,<h1>Hello</h1>",
        "gopher://gopher.floodgap.com",
    ]
    for url in disallowed_urls:
        response = client.post("/link-analysis", json={"url": url})
        assert response.status_code in (400, 422), f"Failed to reject disallowed scheme: {url}"


def test_url_with_embedded_credentials():
    """Verify rejection of URLs with user credentials (e.g., http://user:pass@host)."""
    response = client.post("/link-analysis", json={"url": "http://admin:secret@example.com"})
    assert response.status_code in (400, 422)


def test_url_missing_hostname():
    """Verify rejection of URLs with missing host."""
    response = client.post("/link-analysis", json={"url": "https://"})
    assert response.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 5. SSRF Protections (Localhost, Private IPs, Metadata, and DNS Resolution)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "prohibited_url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:4000",
        "http://127.0.0.2",
        "http://10.0.0.1/admin",
        "http://10.255.255.1",
        "http://172.16.0.1",
        "http://172.31.255.255",
        "http://192.168.0.1",
        "http://192.168.1.254",
        "http://169.254.169.254/latest/meta-data",  # AWS/GCP cloud metadata
        "http://[::1]:8080",                        # IPv6 loopback
        "http://[::ffff:127.0.0.1]",                # IPv4-mapped IPv6 loopback
        "http://0.0.0.0:80",
        "http://metadata.google.internal",
        "http://intranet",                          # Single-label private hostname
        "http://router.local",                      # .local mDNS
        "http://nas.lan",                           # .lan domain
    ],
)
def test_ssrf_prohibited_targets_rejected(prohibited_url):
    """Verify that localhost, loopback, private IPs, and metadata URLs are blocked with 400 Bad Request."""
    response = client.post("/link-analysis", json={"url": prohibited_url})
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] in ("SSRF_SECURITY_BLOCKED", "INVALID_URL")


def test_ssrf_dns_resolution_to_private_ip():
    """Verify that hostnames whose DNS resolves to private IPs are blocked."""
    with patch(
        "app.utils.validators.resolve_and_validate_host",
        new=AsyncMock(side_effect=SSRFSecurityError("Prohibited address 127.0.0.1")),
    ):
        response = client.post("/link-analysis", json={"url": "https://malicious-rebinding-domain.com"})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "SSRF_SECURITY_BLOCKED"


def test_is_ip_allowed_utility():
    """Unit test for is_ip_allowed with public, private, and reserved IPs."""
    # Prohibited IPs
    assert not is_ip_allowed(ipaddress.ip_address("127.0.0.1"))
    assert not is_ip_allowed(ipaddress.ip_address("10.0.0.1"))
    assert not is_ip_allowed(ipaddress.ip_address("192.168.1.1"))
    assert not is_ip_allowed(ipaddress.ip_address("172.20.0.1"))
    assert not is_ip_allowed(ipaddress.ip_address("169.254.169.254"))
    assert not is_ip_allowed(ipaddress.ip_address("0.0.0.0"))
    assert not is_ip_allowed(ipaddress.ip_address("100.64.0.1"))  # CGNAT
    assert not is_ip_allowed(ipaddress.ip_address("::1"))
    assert not is_ip_allowed(ipaddress.ip_address("fe80::1"))
    assert not is_ip_allowed(ipaddress.ip_address("fc00::1"))

    # Public IPs
    assert is_ip_allowed(ipaddress.ip_address("8.8.8.8"))
    assert is_ip_allowed(ipaddress.ip_address("1.1.1.1"))
    assert is_ip_allowed(ipaddress.ip_address("93.184.216.34"))
    assert is_ip_allowed(ipaddress.ip_address("2606:4700:4700::1111"))


# ---------------------------------------------------------------------------
# 6. Upstream Errors and Resiliency
# ---------------------------------------------------------------------------

def test_upstream_timeout_error():
    """Verify 504 Gateway Timeout when upstream server times out."""
    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(side_effect=ConnectionTimeoutError()),
    ):
        response = client.post("/link-analysis", json={"url": "https://slow-website.com"})
        assert response.status_code == 504
        assert response.json()["error_code"] == "GATEWAY_TIMEOUT"


def test_upstream_connection_failure():
    """Verify 502 Bad Gateway when connection to upstream fails."""
    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(side_effect=UpstreamConnectionError("DNS failure or connection refused")),
    ):
        response = client.post("/link-analysis", json={"url": "https://unreachable-website.com"})
        assert response.status_code == 502
        assert response.json()["error_code"] == "UPSTREAM_CONNECT_ERROR"


def test_upstream_http_status_error():
    """Verify appropriate error code when upstream returns 404/500."""
    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(side_effect=HTTPStatusExtractionError(404, "Not Found")),
    ):
        response = client.post("/link-analysis", json={"url": "https://example.com/not-found"})
        assert response.status_code == 400
        assert response.json()["error_code"] == "UPSTREAM_HTTP_404"


def test_unsupported_content_type():
    """Verify 422 Unprocessable Content when response is non-HTML (e.g. PDF)."""
    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(side_effect=UnsupportedContentTypeError("application/pdf")),
    ):
        response = client.post("/link-analysis", json={"url": "https://example.com/document.pdf"})
        assert response.status_code == 422
        assert response.json()["error_code"] == "UNSUPPORTED_CONTENT_TYPE"


def test_payload_too_large():
    """Verify 413 Payload Too Large when webpage exceeds 5 MB."""
    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(side_effect=ResponseTooLargeError(5 * 1024 * 1024)),
    ):
        response = client.post("/link-analysis", json={"url": "https://huge-webpage.com"})
        assert response.status_code == 413
        assert response.json()["error_code"] == "PAYLOAD_TOO_LARGE"


# ---------------------------------------------------------------------------
# 7. HTML Sanitization Unit Tests
# ---------------------------------------------------------------------------

def test_html_sanitizer_removes_scripts_and_styles():
    """Verify that scripts, styles, iframes, and noisy containers are stripped."""
    dirty_html = """
    <html>
    <head>
        <title>Tech Startup</title>
        <style>.ad { display: none; }</style>
        <script>alert('bad');</script>
    </head>
    <body>
        <nav><a href="/home">Home</a></nav>
        <h1>Welcome</h1>
        <p>This is legitimate body text about our software product.</p>
        <div class="cookie-banner"><p>Cookie consent notice</p></div>
        <footer><p>Copyright 2026</p></footer>
    </body>
    </html>
    """
    extractor = WebsiteExtractor()
    extracted = extractor.parse_html(dirty_html, "https://startup.io", len(dirty_html))

    assert extracted.title == "Tech Startup"
    assert len(extracted.paragraphs) == 1
    assert "legitimate body text" in extracted.paragraphs[0]
    assert "cookie" not in extracted.clean_text_summary.lower()
    assert "alert" not in extracted.clean_text_summary


def test_content_length_limiter():
    """Verify that excessively large pages are cleanly truncated for LLM optimization."""
    small_settings = Settings(MAX_EXTRACTED_CONTENT_LENGTH=300)
    extractor = WebsiteExtractor(settings=small_settings)

    long_html = (
        "<html><head><title>Long Page</title></head><body>"
        "<h1>Header</h1>"
        + "".join([f"<p>Paragraph {i}: This is long descriptive enterprise content.</p>\n" for i in range(20)])
        + "</body></html>"
    )

    extracted = extractor.parse_html(long_html, "https://longpage.com", len(long_html))

    assert len(extracted.clean_text_summary) <= 300 + 100
    assert "[Content truncated" in extracted.clean_text_summary


# ---------------------------------------------------------------------------
# 8. Service Unit Tests (Competitor Refinement & Enforcements)
# ---------------------------------------------------------------------------

def test_competitor_service_refinement():
    """Verify CompetitorService labels verified vs inferred competitors accurately."""
    content = ExtractedContent(
        url="https://novaflow.io",
        title="NovaFlow vs Datadog Cloud Management",
        clean_text_summary="We outperform Datadog in automated remediation. Our solution is autonomous.",
        raw_html_size_bytes=1000,
        word_count=50,
        character_count=300,
    )

    comp_analysis = CompetitorAnalysis(
        brand_name="NovaFlow",
        business_overview="Cloud management",
        category="DevOps",
        products_and_services=["Remediation"],
        competitors=[
            CompetitorItem(
                name="Datadog",  # mentioned on page
                category_or_type="Direct",
                strengths=["Scale"],
                weaknesses=["Cost"],
                is_inferred=True,
                evidence_source="ai_inferred_industry_standard",
            ),
            CompetitorItem(
                name="Dynatrace",  # not mentioned on page
                category_or_type="Direct",
                strengths=["APM"],
                weaknesses=["Complexity"],
                is_inferred=True,
                evidence_source="ai_inferred_industry_standard",
            ),
            CompetitorItem(
                name="New Relic",  # not mentioned on page
                category_or_type="Direct",
                strengths=["Visibility"],
                weaknesses=["UI"],
                is_inferred=True,
                evidence_source="ai_inferred_industry_standard",
            ),
        ],
        competitive_advantages=["Autonomous speed"],
        positioning_opportunities=["FinOps"],
    )

    service = CompetitorService()
    refined = service.validate_and_refine_competitors(comp_analysis, content)

    # Datadog was mentioned in title/summary -> verified
    datadog = next(c for c in refined.competitors if c.name == "Datadog")
    assert datadog.is_inferred is False
    assert datadog.evidence_source == "verified_from_website"

    # Dynatrace was NOT mentioned in title/summary -> inferred
    dynatrace = next(c for c in refined.competitors if c.name == "Dynatrace")
    assert dynatrace.is_inferred is True
    assert dynatrace.evidence_source == "ai_inferred_industry_standard"


@pytest.mark.asyncio
async def test_llm_service_retry_and_succeed():
    """Verify LLMService retries on transient errors and succeeds on subsequent attempt."""
    settings = Settings(
        GEMINI_API_KEY="test_key_123",
        GEMINI_MODEL="gemini-2.5-flash",
        GEMINI_MAX_RETRIES=3,
        GEMINI_TIMEOUT_SECONDS=10.0,
    )
    service = LLMService(settings=settings)

    content = ExtractedContent(
        url="https://novaflow.io",
        title="NovaFlow",
        clean_text_summary="Cloud automation platform.",
        raw_html_size_bytes=1000,
        word_count=20,
        character_count=150,
    )

    mock_response = MagicMock()
    mock_response.text = MOCK_STRUCTURED_ANALYSIS.model_dump_json()

    # Fail on attempt 1 with Timeout, succeed on attempt 2
    mock_generate = AsyncMock(side_effect=[asyncio.TimeoutError("Transient timeout"), mock_response])

    with patch.object(service, "_get_client") as mock_get_client, patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = mock_generate
        mock_get_client.return_value = mock_client

        result = await service.analyze_website(content)
        assert result.brand.brand_name == "NovaFlow"
        assert mock_generate.call_count == 2
        assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_analysis_service_enforces_query_and_service_caps():
    """Verify AnalysisService guarantees exactly 5 queries and <= 5 services."""
    settings = Settings(GEMINI_API_KEY="test_key_123")
    analysis_service = AnalysisService(settings=settings)

    # Clone mock analysis with 6 queries and 6 services
    overflow_analysis = MOCK_STRUCTURED_ANALYSIS.model_copy(deep=True)
    extra_query = overflow_analysis.target_search_queries.queries[0].model_copy()
    overflow_analysis.target_search_queries.queries.append(extra_query)
    assert len(overflow_analysis.target_search_queries.queries) == 6

    extra_service = overflow_analysis.top_services.services[0].model_copy()
    overflow_analysis.top_services.services.extend([extra_service, extra_service, extra_service])
    assert len(overflow_analysis.top_services.services) == 6

    with patch.object(
        WebsiteExtractor,
        "fetch_html",
        new=AsyncMock(return_value=(SAMPLE_COMPANY_HTML, "https://novaflow.io", len(SAMPLE_COMPANY_HTML))),
    ), patch.object(
        LLMService,
        "analyze_website",
        new=AsyncMock(return_value=overflow_analysis),
    ):
        result = await analysis_service.analyze_url("https://novaflow.io")
        assert len(result.analysis.target_search_queries.queries) == 5
        assert len(result.analysis.top_services.services) <= 5
        assert result.analysis.top_services.total_identified <= 5


# ---------------------------------------------------------------------------
# 10. Frontend Web Dashboard & Content Negotiation Tests
# ---------------------------------------------------------------------------

def test_frontend_dashboard_endpoint():
    """Verify GET /dashboard returns 200 OK with HTML content."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    html = response.text
    assert "Link Analysis" in html
    assert "Turn Any Website Into" in html
    assert "Competitor vs Brand Analysis" in html
    assert "Target Search Queries" in html
    assert "SEO Improvements" in html
    assert "Top 5 Identified Services" in html
    assert "Target Audience" in html


def test_root_content_negotiation_html():
    """Verify GET / with Accept: text/html serves the frontend HTML dashboard."""
    response = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Link Analysis" in response.text
    assert "Actionable Intelligence" in response.text


def test_root_content_negotiation_json():
    """Verify GET / with Accept: application/json returns the API metadata dict."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    data = response.json()
    assert "endpoints" in data
    assert "dashboard" in data["endpoints"]
    assert "Phase 2" in data["phase"]

