"""LLM-based relevance checker for filtering irrelevant papers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RelevanceScore:
    """Relevance assessment for a paper."""

    is_relevant: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    pmid: str


class RelevanceChecker:
    """Check if papers are actually about the gene using LLM assessment."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022",
        batch_size: int = 10,
    ) -> None:
        """Initialize the relevance checker.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Claude model to use (haiku is cost-effective)
            batch_size: Number of papers to process in parallel
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.batch_size = batch_size

        if not self.api_key:
            logger.warning(
                "No Anthropic API key provided. Set ANTHROPIC_API_KEY "
                "environment variable or pass api_key parameter."
            )

    def check_relevance(
        self,
        gene_name: str,
        title: str,
        abstract: Optional[str],
        pmid: str,
    ) -> RelevanceScore:
        """Check if a single paper is relevant to the gene.

        Args:
            gene_name: The gene being searched for
            title: Paper title
            abstract: Paper abstract (if available)
            pmid: PubMed ID

        Returns:
            RelevanceScore with assessment
        """
        if not self.api_key:
            # Fallback: assume relevant if no API key
            return RelevanceScore(
                is_relevant=True,
                confidence=0.5,
                reasoning="No API key provided; cannot assess relevance",
                pmid=pmid,
            )

        try:
            import anthropic
        except ImportError:
            logger.error(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )
            return RelevanceScore(
                is_relevant=True,
                confidence=0.5,
                reasoning="anthropic package not installed",
                pmid=pmid,
            )

        client = anthropic.Anthropic(api_key=self.api_key)

        # Build the prompt
        text_to_check = f"Title: {title}\n"
        if abstract:
            text_to_check += f"\nAbstract: {abstract}"

        prompt = f"""You are analyzing whether a scientific paper is actually about the gene "{gene_name}".

Sometimes gene symbols match common abbreviations that have nothing to do with the gene. For example:
- "TTR" could mean the gene Transthyretin OR "time to reimbursement"
- "CAT" could mean the gene Catalase OR "computed axial tomography"

Analyze this paper and determine if it's genuinely about the gene {gene_name}.

{text_to_check}

Respond with ONLY a JSON object with this exact format:
{{
  "is_relevant": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation"
}}

Consider:
1. Is the gene name used in a biological/genetic context?
2. Are there mentions of proteins, mutations, diseases, or genetic mechanisms?
3. Or is it clearly used as an abbreviation for something else?

Be strict - if you're uncertain, mark as not relevant."""

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
                return RelevanceScore(
                    is_relevant=result.get("is_relevant", False),
                    confidence=float(result.get("confidence", 0.5)),
                    reasoning=result.get("reasoning", ""),
                    pmid=pmid,
                )
            else:
                logger.warning(f"Could not parse LLM response for PMID {pmid}: {response_text}")
                return RelevanceScore(
                    is_relevant=True,
                    confidence=0.5,
                    reasoning="Could not parse LLM response",
                    pmid=pmid,
                )

        except Exception as e:
            logger.error(f"Error checking relevance for PMID {pmid}: {e}")
            return RelevanceScore(
                is_relevant=True,
                confidence=0.5,
                reasoning=f"Error: {str(e)}",
                pmid=pmid,
            )

    def check_batch(
        self,
        gene_name: str,
        papers: List[tuple[str, str, Optional[str], str]],
    ) -> List[RelevanceScore]:
        """Check relevance for multiple papers.

        Args:
            gene_name: The gene being searched for
            papers: List of (title, abstract, pmid) tuples

        Returns:
            List of RelevanceScore objects
        """
        results = []
        for title, abstract, pmid in papers:
            score = self.check_relevance(gene_name, title, abstract, pmid)
            results.append(score)

        return results
