"""Pydantic schemas for request, response, and structured business analysis validation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class LinkAnalysisRequest(BaseModel):
    """Request payload for website link analysis."""

    url: str = Field(
        ...,
        description="The HTTP or HTTPS website URL to analyze.",
        examples=["https://example.com"],
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("URL must be a string.")

        cleaned = v.strip()
        if not cleaned:
            raise ValueError("URL cannot be empty.")

        try:
            parsed = urlsplit(cleaned)
        except Exception as e:
            raise ValueError(f"Malformed URL: {e}") from e

        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(
                f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are allowed."
            )

        if not parsed.netloc:
            raise ValueError("URL must include a valid host or domain name.")

        # Reject embedded credentials (e.g., http://user:pass@host)
        if parsed.username or parsed.password:
            raise ValueError("URLs with embedded user credentials are not allowed.")

        # Extract hostname (without port if present)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Could not extract a valid hostname from the URL.")

        return cleaned


# ---------------------------------------------------------------------------
# Extraction Models
# ---------------------------------------------------------------------------

class ExtractedHeading(BaseModel):
    """Structured heading item."""

    level: str = Field(..., description="Heading tag level (h1, h2, h3, etc.)")
    text: str = Field(..., description="Cleaned heading text")


class ExtractedLink(BaseModel):
    """Structured hyperlink item."""

    text: str = Field(..., description="Visible link anchor text")
    url: str = Field(..., description="Resolved absolute URL")
    is_internal: bool = Field(..., description="Whether the link points to the same domain")


class ExtractedContent(BaseModel):
    """Extracted and structured website content from DOM."""

    url: str = Field(..., description="Normalized target URL")
    title: str = Field(..., description="Page title")
    meta_description: Optional[str] = Field(
        None, description="Meta description content or fallback snippet"
    )
    headings: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Grouped headings by tag level (e.g., h1, h2, h3)",
    )
    heading_items: List[ExtractedHeading] = Field(
        default_factory=list,
        description="Sequential list of headings in order of appearance",
    )
    paragraphs: List[str] = Field(
        default_factory=list,
        description="Meaningful text paragraphs extracted from main body",
    )
    services: List[str] = Field(
        default_factory=list,
        description="Extracted service offerings, product features, or capabilities",
    )
    links: List[ExtractedLink] = Field(
        default_factory=list,
        description="Relevant navigation and internal/external links",
    )
    clean_text_summary: str = Field(
        ...,
        description="Sanitized, noise-free text summary formatted for LLM processing",
    )
    word_count: int = Field(..., description="Total word count in clean text summary")
    character_count: int = Field(..., description="Total character count in clean text summary")
    raw_html_size_bytes: int = Field(
        ..., description="Byte size of the raw fetched HTML content"
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the extraction was performed",
    )


class ExtractedWebsiteSummary(BaseModel):
    """High-level summary of the extracted website for final JSON response."""

    url: str = Field(..., description="Analyzed website URL")
    title: str = Field(..., description="Website title")
    meta_description: Optional[str] = Field(None, description="Extracted meta description")
    word_count: int = Field(..., description="Extracted textual content word count")
    character_count: int = Field(..., description="Extracted textual content character count")
    raw_html_size_bytes: int = Field(..., description="Raw fetched HTML size in bytes")
    extracted_at: datetime = Field(..., description="Extraction timestamp")


# ---------------------------------------------------------------------------
# Section 1: Competitor Analysis Models
# ---------------------------------------------------------------------------

class CompetitorItem(BaseModel):
    """Individual competitor evaluation."""

    name: str = Field(..., description="Competitor company or platform name")
    category_or_type: str = Field(..., description="Direct or indirect competitor type")
    strengths: List[str] = Field(..., description="Key competitive strengths")
    weaknesses: List[str] = Field(..., description="Key competitive weaknesses or vulnerabilities")
    is_inferred: bool = Field(
        True,
        description="True if identified via industry context rather than direct website mention",
    )
    evidence_source: str = Field(
        ...,
        description="Basis of competitor identification (e.g., 'verified_from_website', 'ai_inferred_industry_standard')",
    )


class CompetitorAnalysis(BaseModel):
    """Section 1: Competitor vs Brand Analysis."""

    brand_name: str = Field(..., description="Identified brand name")
    business_overview: str = Field(..., description="Concise summary of the business and value proposition")
    category: str = Field(..., description="Primary business / industry category")
    products_and_services: List[str] = Field(..., description="Key products, services, or solutions offered")
    competitors: List[CompetitorItem] = Field(
        ...,
        min_length=3,
        description="At least 3 relevant market competitors with strengths and weaknesses",
    )
    competitive_advantages: List[str] = Field(
        ...,
        description="Brand unique competitive strengths and key differentiators",
    )
    positioning_opportunities: List[str] = Field(
        ...,
        description="Market positioning, messaging, or whitespace opportunities",
    )
    verification_note: str = Field(
        "Competitors and market positions are AI-inferred based on industry benchmarks and extracted site offerings; verified data is explicitly distinguished from inferred suggestions.",
        description="Transparency note on evidence vs inference",
    )


# ---------------------------------------------------------------------------
# Section 2: Target Search Queries Models
# ---------------------------------------------------------------------------

class TargetSearchQuery(BaseModel):
    """Individual target search query model."""

    query: str = Field(..., description="The exact search query phrase")
    platforms: List[str] = Field(
        ...,
        description="Relevant discovery platforms among: Google, Facebook, Instagram, LinkedIn, X",
    )
    search_intent: str = Field(
        ...,
        description="Search intent: Informational, Commercial, Transactional, or Navigational",
    )
    business_relevance: str = Field(..., description="Why this query is commercially valuable to the brand")
    target_audience: str = Field(..., description="Audience segment or buyer persona executing this search")


class SearchQueriesSection(BaseModel):
    """Section 2: Exactly 5 Top Target Search Queries."""

    queries: List[TargetSearchQuery] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Exactly 5 targeted high-intent search queries",
    )
    supported_platforms: List[str] = Field(
        default_factory=lambda: ["Google", "Facebook", "Instagram", "LinkedIn", "X"],
        description="Supported search and social discovery platforms",
    )
    volume_disclaimer: str = Field(
        "Search volumes are intentionally not fabricated. Queries are modeled based on audience intent and topical relevance.",
        description="Integrity disclaimer regarding search metrics",
    )


# ---------------------------------------------------------------------------
# Section 3: SEO Improvements Models
# ---------------------------------------------------------------------------

class KeywordStrategy(BaseModel):
    """Categorized keyword strategy."""

    primary_keywords: List[str] = Field(..., description="High-priority core business keywords")
    secondary_keywords: List[str] = Field(..., description="Secondary supporting keywords")
    long_tail_keywords: List[str] = Field(..., description="High-intent long-tail search phrases")


class ContentRecommendation(BaseModel):
    """Specific content or landing page recommendation."""

    title: str = Field(..., description="Recommended content or page headline")
    content_type: str = Field(..., description="Type: blog_post, landing_page, case_study, or guide")
    target_keyword: str = Field(..., description="Primary keyword targeted by this piece")
    summary_or_outline: str = Field(..., description="Brief outline and strategic intent")


class FAQItem(BaseModel):
    """Recommended FAQ entry for on-page SEO schema."""

    question: str = Field(..., description="Frequently asked user question")
    recommended_answer: str = Field(..., description="Concise, authoritative answer snippet")


class SEOImprovements(BaseModel):
    """Section 3: Comprehensive SEO Improvements."""

    keywords: KeywordStrategy = Field(..., description="Target keyword hierarchy")
    recommended_seo_title: str = Field(..., description="Optimized title tag under 60 characters")
    recommended_meta_description: str = Field(
        ..., description="Compelling meta description between 140-160 characters"
    )
    content_recommendations: List[ContentRecommendation] = Field(
        ..., description="Recommended blog posts, landing pages, and topic clusters"
    )
    recommended_faqs: List[FAQItem] = Field(
        ..., description="On-page FAQ schema recommendations"
    )
    rationale: str = Field(
        ..., description="Explanation of recommendations based on extracted page content"
    )


# ---------------------------------------------------------------------------
# Section 4: Top 5 Services Models
# ---------------------------------------------------------------------------

class ServiceOffering(BaseModel):
    """Structured service offering."""

    service_name: str = Field(..., description="Name of the service or product offering")
    description: str = Field(..., description="Detailed description of what the service provides")
    target_industry: str = Field(..., description="Primary vertical or industry served")
    target_customer: str = Field(..., description="Ideal customer profile or buyer persona")
    main_benefit: str = Field(..., description="Core business value or outcome delivered")
    is_inferred: bool = Field(
        ...,
        description="True if inferred by AI; False if explicitly documented on the website",
    )
    evidence_source: str = Field(
        ...,
        description="Source basis: 'extracted_from_page' or 'ai_inferred'",
    )


class ServicesSection(BaseModel):
    """Section 4: Up to 5 Top Services / Offerings."""

    services: List[ServiceOffering] = Field(
        ...,
        max_length=5,
        description="Up to 5 actual services identified from website content",
    )
    total_identified: int = Field(..., description="Count of identified services (up to 5)")
    extraction_note: str = Field(
        "Services are derived strictly from page content; inferred capabilities are explicitly labeled.",
        description="Integrity note",
    )


# ---------------------------------------------------------------------------
# Section 5: Target Audience Models
# ---------------------------------------------------------------------------

class AudienceSegment(BaseModel):
    """Specific target audience persona."""

    segment_name: str = Field(..., description="Audience segment title")
    tier: str = Field(..., description="'Primary' or 'Secondary'")
    customer_profile: str = Field(..., description="Demographic and professional profile")
    core_needs_and_pain_points: List[str] = Field(
        ..., description="Key pain points, jobs-to-be-done, and goals"
    )


class TargetAudienceSection(BaseModel):
    """Section 5: Target Audience Identification."""

    primary_audience: AudienceSegment = Field(..., description="Primary target audience segment")
    secondary_audiences: List[AudienceSegment] = Field(
        ..., description="Secondary and auxiliary audience segments"
    )
    target_industries: List[str] = Field(..., description="Industries most relevant to the business")
    target_business_types: List[str] = Field(
        ..., description="Business models: e.g., B2B Enterprise, Mid-Market, SMB, D2C"
    )
    geographic_focus: Optional[str] = Field(
        None, description="Geographic market focus if supported by website evidence"
    )
    marketing_recommendations: List[str] = Field(
        ..., description="Actionable marketing channel and messaging recommendations"
    )


# ---------------------------------------------------------------------------
# Combined Business Intelligence & Final Response Models
# ---------------------------------------------------------------------------

class BrandSummary(BaseModel):
    """High-level brand profile."""

    brand_name: str = Field(..., description="Brand or organization name")
    business_overview: str = Field(..., description="Executive summary of the business")
    category: str = Field(..., description="Primary industry / market category")
    products_and_services: List[str] = Field(..., description="Primary products and service lines")


class CompleteBusinessAnalysis(BaseModel):
    """Complete 5-section AI business intelligence analysis."""

    competitor_analysis: CompetitorAnalysis = Field(
        ..., description="Section 1: Competitor vs Brand Analysis"
    )
    target_search_queries: SearchQueriesSection = Field(
        ..., description="Section 2: Top 5 Target Search Queries across Google, FB, IG, LinkedIn, X"
    )
    seo_improvements: SEOImprovements = Field(
        ..., description="Section 3: Actionable SEO Improvements and Keyword Strategy"
    )
    top_services: ServicesSection = Field(
        ..., description="Section 4: Top 5 Services from extracted content"
    )
    target_audience: TargetAudienceSection = Field(
        ..., description="Section 5: Target Audience Identification and Profiles"
    )


class LLMStructuredAnalysis(BaseModel):
    """Schema for Gemini structured JSON generation."""

    brand: BrandSummary = Field(..., description="Extracted brand summary")
    competitor_analysis: CompetitorAnalysis = Field(..., description="Section 1: Competitor Analysis")
    target_search_queries: SearchQueriesSection = Field(..., description="Section 2: Search Queries")
    seo_improvements: SEOImprovements = Field(..., description="Section 3: SEO Improvements")
    top_services: ServicesSection = Field(..., description="Section 4: Top 5 Services")
    target_audience: TargetAudienceSection = Field(..., description="Section 5: Target Audience")


class LinkAnalysisResponse(BaseModel):
    """Complete response payload for POST /link-analysis."""

    success: bool = Field(True, description="Indicates whether link analysis succeeded")
    status: str = Field("success", description="Status indicator")
    message: str = Field(
        "Website content extracted and analyzed successfully.",
        description="Status description",
    )
    website: ExtractedWebsiteSummary = Field(
        ..., description="Metadata and metrics of the analyzed website"
    )
    brand: BrandSummary = Field(..., description="Extracted brand overview and categorization")
    analysis: CompleteBusinessAnalysis = Field(
        ..., description="The five structured business intelligence sections"
    )

    # Backwards-compatibility fields for Phase 1 tests & clients
    url: Optional[str] = Field(None, description="Analyzed URL (for backwards compatibility)")
    phase: Optional[str] = Field(
        "Phase 2 - Complete AI-Powered Website Analysis",
        description="Phase status",
    )
    data: Optional[ExtractedContent] = Field(
        None, description="Raw extracted DOM data (for backwards compatibility)"
    )


class ErrorResponse(BaseModel):
    """Standardized error response payload."""

    status: str = Field("error", description="Failure indicator")
    error_code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Any] = Field(
        None, description="Optional extra diagnostic details"
    )
