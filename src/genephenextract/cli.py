"""Command-line interface for GenePhenExtract."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from .extraction import LangExtractExtractor, MockExtractor
from .models import PipelineInput
from .pipeline import ExtractionPipeline
from .pubmed import PubMedClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract genotype-phenotype evidence from PubMed")
    parser.add_argument("--query", help="PubMed query string", default=None)
    parser.add_argument("--pmids", nargs="*", help="Explicit PMIDs to process", default=None)
    parser.add_argument("--max-results", type=int, default=5, help="Maximum results to fetch for a query")
    parser.add_argument("--schema", type=Path, default=None, help="Path to a LangExtract schema JSON file")
    parser.add_argument("--api-key", help="API key for LangExtract or the backing LLM provider")
    parser.add_argument("--model", default="gemini-1.5-pro", help="LLM model identifier to use")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the mock extractor instead of LangExtract (no external API calls)",
    )
    parser.add_argument("--output", type=Path, default=None, help="Path to write JSON results")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.query and not args.pmids:
        parser.error("Either --query or --pmids must be provided")

    extractor = _build_extractor(args)
    payload = PipelineInput(
        query=args.query,
        pmids=args.pmids or [],
        max_results=args.max_results,
        schema_path=args.schema,
    )

    with ExtractionPipeline(pubmed_client=PubMedClient(), extractor=extractor) as pipeline:
        results = pipeline.run(payload)

    serialized = [result.to_dict() for result in results]
    if args.output:
        args.output.write_text(json.dumps(serialized, indent=2))
        logger.info("Wrote %d records to %s", len(serialized), args.output)
    else:
        print(json.dumps(serialized, indent=2))
    return 0


def _build_extractor(args: argparse.Namespace) -> MockExtractor | LangExtractExtractor:
    """Instantiate the appropriate extractor implementation."""
    if args.mock:
        return MockExtractor()
    return LangExtractExtractor(api_key=args.api_key, model=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
