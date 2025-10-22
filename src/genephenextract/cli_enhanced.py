"""Enhanced command-line interface for GenePhenExtract with multi-LLM support."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from .extraction import (
    BaseExtractor,
    ClaudeExtractor,
    GeminiExtractor,
    MockExtractor,
    MultiStageExtractor,
    OpenAIExtractor,
    RelevanceFilter,
)
from .hpo import PhenotypeOntologyMapper
from .models import PipelineInput
from .pipeline import ExtractionPipeline
from .pubmed import PubMedClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract genotype-phenotype evidence from PubMed with multi-LLM support"
    )

    # Search parameters
    search_group = parser.add_argument_group("Search options")
    search_group.add_argument("--query", help="PubMed query string")
    search_group.add_argument("--pmids", nargs="*", help="Explicit PMIDs to process")
    search_group.add_argument(
        "--max-results", type=int, default=5, help="Maximum results to fetch for a query"
    )
    search_group.add_argument(
        "--prefer-full-text",
        action="store_true",
        help="Prefer full-text from PMC over abstracts when available",
    )

    # Extractor selection
    extractor_group = parser.add_argument_group("Extractor options")
    extractor_group.add_argument(
        "--extractor",
        choices=["mock", "gemini", "claude", "openai"],
        default="mock",
        help="LLM extractor to use (default: mock)",
    )
    extractor_group.add_argument(
        "--api-key",
        help="API key for the selected extractor (or set via environment variable)",
    )
    extractor_group.add_argument(
        "--model",
        help=(
            "Model identifier to use. Defaults:\n"
            "  gemini: gemini-1.5-pro-latest\n"
            "  claude: claude-3-5-sonnet-20241022\n"
            "  openai: gpt-4o-mini"
        ),
    )

    # Filtering options
    filter_group = parser.add_argument_group("Filtering options (cost optimization)")
    filter_group.add_argument(
        "--filter",
        action="store_true",
        help="Enable two-stage extraction: cheap filter first, expensive extraction if relevant",
    )
    filter_group.add_argument(
        "--filter-provider",
        choices=["openai", "anthropic", "gemini"],
        default="openai",
        help="Provider for relevance filter (default: openai with gpt-4o-mini)",
    )
    filter_group.add_argument(
        "--filter-model",
        help="Model for relevance filter. Defaults to cheapest option for provider.",
    )
    filter_group.add_argument(
        "--filter-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold for relevance filter (0.0-1.0, default: 0.7)",
    )
    filter_group.add_argument(
        "--filter-api-key",
        help="Separate API key for filter (if different from main extractor)",
    )

    # Other options
    other_group = parser.add_argument_group("Other options")
    other_group.add_argument(
        "--schema", type=Path, default=None, help="Path to a custom extraction schema JSON file"
    )
    other_group.add_argument("--output", type=Path, help="Path to write JSON results")
    other_group.add_argument(
        "--hpo-map", type=Path, help="Optional path to a custom HPO mapping JSON file"
    )
    other_group.add_argument(
        "--no-hpo", action="store_true", help="Disable phenotype ontology mapping"
    )
    other_group.add_argument(
        "--show-filter-stats",
        action="store_true",
        help="Show statistics on filtering vs extraction",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.query and not args.pmids:
        parser.error("Either --query or --pmids must be provided")

    # Build extractor
    extractor = _build_extractor(args)

    # Build pipeline input
    payload = PipelineInput(
        query=args.query,
        pmids=args.pmids or [],
        max_results=args.max_results,
        schema_path=args.schema,
    )

    # Build phenotype mapper
    phenotype_mapper = _build_phenotype_mapper(args)

    # Build PubMed client
    pubmed_client = PubMedClient()

    # Run pipeline
    with ExtractionPipeline(
        pubmed_client=pubmed_client, extractor=extractor, phenotype_mapper=phenotype_mapper
    ) as pipeline:
        results = pipeline.run(payload)

    # Show filter stats if requested
    if args.show_filter_stats and isinstance(extractor, MultiStageExtractor):
        stats = extractor.get_stats()
        logger.info("Filter Statistics:")
        logger.info(f"  Articles processed: {stats['extracted'] + stats['skipped']}")
        logger.info(f"  Passed filter (extracted): {stats['extracted']}")
        logger.info(f"  Filtered out (skipped): {stats['skipped']}")
        if stats['extracted'] + stats['skipped'] > 0:
            savings_pct = 100 * stats['skipped'] / (stats['extracted'] + stats['skipped'])
            logger.info(f"  Cost savings: {savings_pct:.1f}%")

    # Output results
    serialized = [result.to_dict() for result in results]
    if args.output:
        args.output.write_text(json.dumps(serialized, indent=2))
        logger.info("Wrote %d records to %s", len(serialized), args.output)
    else:
        print(json.dumps(serialized, indent=2))

    return 0


def _build_extractor(args: argparse.Namespace) -> BaseExtractor:
    """Build the appropriate extractor based on CLI arguments."""

    # Build primary extractor
    if args.extractor == "mock":
        primary_extractor = MockExtractor()
        logger.info("Using MockExtractor (no external API calls)")

    elif args.extractor == "gemini":
        logger.info("Using GeminiExtractor")
        primary_extractor = GeminiExtractor(api_key=args.api_key, model=args.model)

    elif args.extractor == "claude":
        logger.info("Using ClaudeExtractor")
        primary_extractor = ClaudeExtractor(api_key=args.api_key, model=args.model)

    elif args.extractor == "openai":
        logger.info("Using OpenAIExtractor")
        primary_extractor = OpenAIExtractor(api_key=args.api_key, model=args.model)

    else:
        raise ValueError(f"Unknown extractor: {args.extractor}")

    # Wrap with filter if requested
    if args.filter:
        if args.extractor == "mock":
            logger.warning("Filtering with MockExtractor is not useful; skipping filter")
            return primary_extractor

        logger.info("Enabling two-stage extraction with relevance filter")
        filter_api_key = args.filter_api_key or args.api_key
        relevance_filter = RelevanceFilter(
            api_key=filter_api_key,
            provider=args.filter_provider,
            model=args.filter_model,
        )
        return MultiStageExtractor(
            filter=relevance_filter,
            extractor=primary_extractor,
            min_confidence=args.filter_confidence,
        )

    return primary_extractor


def _build_phenotype_mapper(args: argparse.Namespace) -> Optional[PhenotypeOntologyMapper]:
    if args.no_hpo:
        return PhenotypeOntologyMapper({})
    if args.hpo_map:
        return PhenotypeOntologyMapper.from_json(args.hpo_map)
    return PhenotypeOntologyMapper.default()


if __name__ == "__main__":
    raise SystemExit(main())
