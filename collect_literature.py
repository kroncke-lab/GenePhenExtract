"""Command-line entry point for gene-focused literature collection."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from gene_literature import LiteratureCollector, PubMedClient
from gene_literature.writer import write_metadata


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s:%(name)s:%(message)s")
    logger = logging.getLogger(__name__)

    client = PubMedClient(api_key=args.api_key, email=args.email)
    collector = LiteratureCollector(client)

    logger.info("Collecting literature for gene: %s", args.gene)
    records = collector.collect(args.gene, synonyms=args.synonyms, retmax=args.retmax)
    write_metadata(records, args.output, fmt=args.format)
    logger.info("Successfully wrote %d records to %s", len(records), args.output)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
