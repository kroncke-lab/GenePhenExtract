"""LLM-based relevance checker for filtering gene synonyms."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SynonymRelevance:
    """Relevance assessment for a gene synonym."""

    synonym: str
    is_relevant: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str


class SynonymRelevanceChecker:
    """Check if synonyms are actually relevant gene names using LLM assessment."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022",
    ) -> None:
        """Initialize the synonym relevance checker.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Claude model to use (haiku is cost-effective)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            logger.warning(
                "No Anthropic API key provided. Set ANTHROPIC_API_KEY "
                "environment variable or pass api_key parameter."
            )

    def check_synonym_relevance(
        self,
        gene_name: str,
        synonym: str,
        source: str,
    ) -> SynonymRelevance:
        """Check if a synonym is relevant for the gene.

        Args:
            gene_name: The primary gene name
            synonym: The synonym candidate to evaluate
            source: Source of the synonym (e.g., 'official_symbol', 'alias', 'other_designation')

        Returns:
            SynonymRelevance with assessment
        """
        if not self.api_key:
            # Fallback: assume relevant if no API key
            return SynonymRelevance(
                synonym=synonym,
                is_relevant=True,
                confidence=0.5,
                reasoning="No API key provided; cannot assess relevance",
            )

        try:
            import anthropic
        except ImportError:
            logger.error(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )
            return SynonymRelevance(
                synonym=synonym,
                is_relevant=True,
                confidence=0.5,
                reasoning="anthropic package not installed",
            )

        client = anthropic.Anthropic(api_key=self.api_key)

        prompt = f"""You are evaluating whether a gene synonym is actually relevant and useful for literature searches.

Primary gene name: {gene_name}
Synonym candidate: {synonym}
Source: {source}

Your task is to determine if this synonym is:
1. A legitimate alternate name for the gene (not just a misspelling or overly generic term)
2. Likely to appear in scientific literature when referring to this gene
3. Sufficiently specific to avoid excessive false positives

Consider:
- Official gene symbols and common aliases are usually highly relevant
- Very generic terms (like "protein", "factor", "component") are NOT relevant
- Overly verbose descriptions are less useful than concise terms
- Terms that could easily refer to other things are less relevant
- Historical names that are rarely used anymore may have lower relevance

Examples of RELEVANT synonyms:
- BRCA1 → BRCC1 (common historical alias)
- TP53 → P53 (widely used alternative)
- SCN5A → LQT3 (disease-associated designation)

Examples of NOT RELEVANT synonyms:
- BRCA1 → "breast cancer 1, early onset" (too verbose)
- CAT → "catalase" (could match too many unrelated terms)
- GENE → "protein" (too generic)

Respond with ONLY a JSON object with this exact format:
{{
  "is_relevant": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation (max 50 words)"
}}

Be reasonably selective - the goal is to expand searches with useful terms while avoiding noise."""

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            response_text = message.content[0].text.strip()

            # Try to extract JSON
            import json
            import re

            # Look for JSON object in response
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return SynonymRelevance(
                    synonym=synonym,
                    is_relevant=result.get("is_relevant", False),
                    confidence=float(result.get("confidence", 0.5)),
                    reasoning=result.get("reasoning", ""),
                )
            else:
                logger.warning(f"Could not parse LLM response for synonym '{synonym}': {response_text}")
                return SynonymRelevance(
                    synonym=synonym,
                    is_relevant=True,
                    confidence=0.5,
                    reasoning="Could not parse LLM response",
                )

        except Exception as e:
            logger.error(f"Error checking relevance for synonym '{synonym}': {e}")
            return SynonymRelevance(
                synonym=synonym,
                is_relevant=True,
                confidence=0.5,
                reasoning=f"Error: {str(e)}",
            )

    def check_synonyms_batch(
        self,
        gene_name: str,
        synonyms: List[tuple[str, str]],
    ) -> List[SynonymRelevance]:
        """Check relevance for multiple synonyms.

        Args:
            gene_name: The primary gene name
            synonyms: List of (synonym, source) tuples

        Returns:
            List of SynonymRelevance objects
        """
        results = []
        for synonym, source in synonyms:
            score = self.check_synonym_relevance(gene_name, synonym, source)
            results.append(score)

        return results
