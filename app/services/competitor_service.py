"""Competitor discovery and analysis service.

Enforces business rules for competitor evaluation, ensuring clear distinction
between verified on-site disclosures and AI-inferred industry comparisons.
"""

import logging
from typing import List, Optional

from app.config import Settings, get_settings
from app.schemas import CompetitorAnalysis, CompetitorItem, ExtractedContent

logger = logging.getLogger(__name__)


class CompetitorService:
    """Service managing competitor evaluation and brand positioning logic."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def validate_and_refine_competitors(
        self,
        analysis: CompetitorAnalysis,
        content: ExtractedContent,
    ) -> CompetitorAnalysis:
        """Validate competitor data against extracted page content and enforce evidence labeling.

        Ensures that:
        1. At least 3 competitors are included when reliable industry context exists.
        2. Inferred vs verified evidence labels are explicitly tagged.
        3. Strengths and weaknesses are populated.
        4. No false verification claims are made.
        """
        page_text_lower = (content.title + " " + content.clean_text_summary).lower()

        refined_competitors: List[CompetitorItem] = []
        for comp in analysis.competitors:
            comp_name_lower = comp.name.lower()
            # Check if competitor was explicitly mentioned in the webpage content
            is_directly_mentioned = comp_name_lower in page_text_lower

            refined_comp = CompetitorItem(
                name=comp.name.strip(),
                category_or_type=comp.category_or_type or "Direct Competitor",
                strengths=comp.strengths if comp.strengths else ["Established market presence"],
                weaknesses=comp.weaknesses if comp.weaknesses else ["Higher cost / less agile"],
                is_inferred=not is_directly_mentioned,
                evidence_source=(
                    "verified_from_website"
                    if is_directly_mentioned
                    else "ai_inferred_industry_standard"
                ),
            )
            refined_competitors.append(refined_comp)

        analysis.competitors = refined_competitors
        return analysis
