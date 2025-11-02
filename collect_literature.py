"""Command-line entry point for gene-focused literature collection."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from gene_literature import LiteratureCollector, PubMedClient
from gene_literature.synonym_finder import SynonymFinder, interactive_synonym_selection
from gene_literature.writer import write_metadata

try:
    from gene_literature.relevance_checker import RelevanceChecker
    RELEVANCE_CHECKER_AVAILABLE = True
except ImportError:
    RELEVANCE_CHECKER_AVAILABLE = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Primary gene symbol to query")
    parser.add_argument(
        "--synonym",
        action="append",
        dest="synonyms",
        default=None,
        help="Gene synonym (can be provided multiple times)",
    )
    parser.add_argument(
        "--auto-synonyms",
        action="store_true",
        help="Automatically find gene synonyms using NCBI Gene database and prompt for selection",
    )
    parser.add_argument(
        "--include-other-designations",
        action="store_true",
        help="Include verbose 'other designations' when finding synonyms (use with --auto-synonyms)",
    )
    parser.add_argument("--retmax", type=int, default=100, help="Maximum number of PubMed results")
    parser.add_argument("--email", help="Email address provided to PubMed", default=None)
    parser.add_argument("--api-key", help="NCBI API key", default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("literature_results.json"),
        help="Output path for collected metadata",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "sqlite", "urls"],
        default="json",
        help="Output format (urls format creates a text file with downloadable URLs)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    parser.add_argument(
        "--filter-irrelevant",
        action="store_true",
        help="Use LLM to filter out irrelevant papers (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--anthropic-api-key",
        help="Anthropic API key for relevance checking (or set ANTHROPIC_API_KEY env var)",
        default=None,
    )
    parser.add_argument(
        "--min-relevance-score",
        type=float,
        default=0.7,
        help="Minimum relevance score (0.0-1.0) to keep papers (default: 0.7)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s:%(name)s:%(message)s")
    logger = logging.getLogger(__name__)

    # Initialize synonym list with any manually provided synonyms
    all_synonyms = list(args.synonyms) if args.synonyms else []

    # Auto-discover synonyms if requested
    if args.auto_synonyms:
        logger.info("Auto-discovering synonyms for gene: %s", args.gene)
        if args.anthropic_api_key:
            logger.info("LLM-based synonym relevance checking enabled")
        synonym_finder = SynonymFinder(
            email=args.email,
            api_key=args.api_key,
            anthropic_api_key=args.anthropic_api_key,
        )

        try:
            found_synonyms = synonym_finder.find_gene_synonyms(
                args.gene,
                include_other_designations=args.include_other_designations,
            )

            # Interactive selection
            selected_synonyms = interactive_synonym_selection(args.gene, found_synonyms)

            # Merge with manually provided synonyms (avoid duplicates)
            existing_set = set(s.lower() for s in all_synonyms)
            for syn in selected_synonyms:
                if syn.lower() not in existing_set and syn.lower() != args.gene.lower():
                    all_synonyms.append(syn)
                    existing_set.add(syn.lower())

            logger.info("Total synonyms to use: %d", len(all_synonyms))

        except Exception as e:
            logger.error("Failed to find synonyms: %s", e)
            logger.warning("Continuing with manually provided synonyms only")

    # Initialize PubMed client
    client = PubMedClient(api_key=args.api_key, email=args.email)

    # Initialize relevance checker if filtering is requested
    relevance_checker = None
    if args.filter_irrelevant:
        if not RELEVANCE_CHECKER_AVAILABLE:
            logger.error(
                "Relevance filtering requested but anthropic package not installed. "
                "Install with: pip install 'gene-literature-collector[relevance]'"
            )
            return
        relevance_checker = RelevanceChecker(api_key=args.anthropic_api_key)
        logger.info("Relevance filtering enabled (min_score=%.2f)", args.min_relevance_score)

    # Initialize collector
    collector = LiteratureCollector(client, relevance_checker=relevance_checker)

    logger.info("Collecting literature for gene: %s", args.gene)
    if all_synonyms:
        logger.info("Using %d synonyms: %s", len(all_synonyms), ", ".join(all_synonyms))

    # Collect papers
    records = collector.collect(
        args.gene,
        synonyms=all_synonyms if all_synonyms else None,
        retmax=args.retmax,
        filter_irrelevant=args.filter_irrelevant,
        min_relevance_score=args.min_relevance_score,
    )

    write_metadata(records, args.output, fmt=args.format)
    logger.info("Successfully wrote %d records to %s", len(records), args.output)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
