"""High-level orchestration for the GenePhenExtract workflow."""

from __future__ import annotations

import logging
from typing import List, Optional

from .extraction import BaseExtractor, MockExtractor
from .models import ExtractionResult, PipelineInput
from .pubmed import PubMedClient

logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """Coordinates PubMed retrieval and schema-guided extraction."""

    def __init__(
        self,
        *,
        pubmed_client: Optional[PubMedClient] = None,
        extractor: Optional[BaseExtractor] = None,
    ) -> None:
        self.pubmed_client = pubmed_client or PubMedClient()
        self.extractor = extractor or MockExtractor()

    def run(self, payload: PipelineInput) -> List[ExtractionResult]:
        pmids = self._determine_pmids(payload)
        logger.info("Processing %d pmids", len(pmids))
        results: List[ExtractionResult] = []
        for pmid in pmids:
            abstract = self.pubmed_client.fetch_abstract(pmid)
            if not abstract:
                logger.warning("Skipping PMID %s due to missing abstract", pmid)
                continue
            logger.debug("Running extractor for PMID %s", pmid)
            result = self.extractor.extract(abstract, pmid=pmid, schema_path=payload.schema_path)
            results.append(result)
        return results

    def _determine_pmids(self, payload: PipelineInput) -> List[str]:
        if payload.pmids:
            return payload.pmids
        if not payload.query:
            msg = "Either a query or explicit PMIDs must be provided"
            raise ValueError(msg)
        logger.info("Searching PubMed with query '%s'", payload.query)
        pmids = self.pubmed_client.search(payload.query, retmax=payload.max_results)
        return pmids

    def close(self) -> None:
        self.pubmed_client.close()

    def __enter__(self) -> "ExtractionPipeline":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
