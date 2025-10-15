"""Command-line interface for GenePhenExtract."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from .extraction import DEFAULT_GEMINI_MODEL, GeminiExtractor, MockExtractor
from .hpo import PhenotypeOntologyMapper
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
    parser.add_argument(
        "--model",
        default=DEFAULT_GEMINI_MODEL,
        help=(
            "LLM model identifier to use (defaults to %(default)s). "
            "Common options: gemini-pro, gemini-1.5-pro, gemini-1.5-flash. "
            "Can also be set via the GENEPHENEXTRACT_GEMINI_MODEL environment variable."
        ),
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the mock extractor instead of LangExtract (no external API calls)",
    )
    parser.add_argument("--output", type=Path, default=None, help="Path to write JSON results")
    parser.add_argument("--hpo-map", type=Path, default=None, help="Optional path to a custom HPO mapping JSON file")
    parser.add_argument("--no-hpo", action="store_true", help="Disable phenotype ontology mapping")
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

    phenotype_mapper = _build_phenotype_mapper(args)

    with ExtractionPipeline(
        pubmed_client=PubMedClient(), extractor=extractor, phenotype_mapper=phenotype_mapper
    ) as pipeline:
        results = pipeline.run(payload)

    serialized = [result.to_dict() for result in results]
    if args.output:
        args.output.write_text(json.dumps(serialized, indent=2))
        logger.info("Wrote %d records to %s", len(serialized), args.output)
    else:
        print(json.dumps(serialized, indent=2))
    return 0


def _build_extractor(args: argparse.Namespace) -> MockExtractor | GeminiExtractor:
    """Instantiate the appropriate extractor implementation."""
    if args.mock:
        return MockExtractor()
    return GeminiExtractor(api_key=args.api_key, model=args.model)


def _build_phenotype_mapper(args: argparse.Namespace) -> PhenotypeOntologyMapper | None:
    if args.no_hpo:
        return PhenotypeOntologyMapper({})
    if args.hpo_map:
        return PhenotypeOntologyMapper.from_json(args.hpo_map)
    return PhenotypeOntologyMapper.default()


if __name__ == "__main__":
    raise SystemExit(main())
