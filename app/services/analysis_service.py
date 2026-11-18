"""Analysis orchestration service.

Orchestrates website extraction and Google Gemini LLM processing to produce
the complete five-section business intelligence analysis:
1. Competitor vs Brand Analysis
2. Top 5 Target Search Queries across Google, Facebook, Instagram, LinkedIn, and X
3. SEO Improvements and Keyword Strategy
4. Top 5 Services with Explicit Inference Labels
5. Target Audience Identification and Profiles
"""

import logging
from typing import Optional

from app.config import Settings, get_settings
from app.schemas import (
    CompleteBusinessAnalysis,
    ExtractedContent,
    ExtractedWebsiteSummary,
    LinkAnalysisResponse,
)
from app.services.competitor_service import CompetitorService
from app.services.llm_service import LLMService
from app.services.website_extractor import WebsiteExtractor

logger = logging.getLogger(__name__)


class AnalysisService:
    """Orchestrates comprehensive multi-section business link analysis."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_service: Optional[LLMService] = None,
        competitor_service: Optional[CompetitorService] = None,
        website_extractor: Optional[WebsiteExtractor] = None,
    ):
        self.settings = settings or get_settings()
        self.llm_service = llm_service or LLMService(self.settings)
        self.competitor_service = competitor_service or CompetitorService(self.settings)
        self.website_extractor = website_extractor or WebsiteExtractor(self.settings)

    async def analyze_url(self, url: str) -> LinkAnalysisResponse:
        """Complete end-to-end pipeline: fetch, sanitize, invoke Gemini, and structure response.

        Returns:
            LinkAnalysisResponse containing success, website, brand, and analysis.
        """
        # Step 1: Asynchronously fetch and extract sanitized website content
        logger.info("Starting website extraction pipeline for: %s", url)
        raw_html, final_url, raw_bytes = await self.website_extractor.fetch_html(url)
        extracted = self.website_extractor.parse_html(raw_html, final_url, raw_bytes)
        logger.info(
            "Extracted content for '%s' (title: '%s', words: %d)",
            final_url,
            extracted.title,
            extracted.word_count,
        )

        # Step 2: Invoke Google Gemini with structured output schemas
        logger.info("Executing Gemini AI analysis for: %s", final_url)
        llm_output = await self.llm_service.analyze_website(extracted)

        # Step 3: Refine competitor evidence labeling
        refined_competitor_analysis = self.competitor_service.validate_and_refine_competitors(
            llm_output.competitor_analysis,
            extracted,
        )

        # Step 4: Ensure Section 2 has exactly 5 search queries
        if len(llm_output.target_search_queries.queries) != 5:
            logger.warning(
                "Gemini generated %d search queries; adjusting to exactly 5",
                len(llm_output.target_search_queries.queries),
            )
            # Ensure exactly 5 items
            queries = llm_output.target_search_queries.queries[:5]
            llm_output.target_search_queries.queries = queries

        # Step 5: Ensure Section 4 does not exceed 5 services
        if len(llm_output.top_services.services) > 5:
            llm_output.top_services.services = llm_output.top_services.services[:5]
        llm_output.top_services.total_identified = len(llm_output.top_services.services)

        # Step 6: Assemble CompleteBusinessAnalysis
        complete_analysis = CompleteBusinessAnalysis(
            competitor_analysis=refined_competitor_analysis,
            target_search_queries=llm_output.target_search_queries,
            seo_improvements=llm_output.seo_improvements,
            top_services=llm_output.top_services,
            target_audience=llm_output.target_audience,
        )

        # Step 7: Build ExtractedWebsiteSummary
        website_summary = ExtractedWebsiteSummary(
            url=extracted.url,
            title=extracted.title,
            meta_description=extracted.meta_description,
            word_count=extracted.word_count,
            character_count=extracted.character_count,
            raw_html_size_bytes=extracted.raw_html_size_bytes,
            extracted_at=extracted.extracted_at,
        )

        # Step 8: Return complete structured LinkAnalysisResponse
        return LinkAnalysisResponse(
            success=True,
            status="success",
            message="Website content extracted and analyzed successfully.",
            website=website_summary,
            brand=llm_output.brand,
            analysis=complete_analysis,
            # Backwards compatibility fields for Phase 1 tests
            url=extracted.url,
            data=extracted,
        )
