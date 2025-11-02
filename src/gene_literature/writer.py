"""Utility helpers for exporting collected literature metadata."""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from pathlib import Path
from typing import Sequence

from .pubmed_client import ArticleMetadata

logger = logging.getLogger(__name__)


def write_metadata(records: Sequence[ArticleMetadata], destination: Path, fmt: str = "json") -> None:
    """Persist article metadata to the desired destination in the requested format."""

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    logger.info("Writing %d records to %s as %s", len(records), destination, fmt)

    if fmt == "json":
        _write_json(records, destination)
    elif fmt == "csv":
        _write_csv(records, destination)
    elif fmt == "sqlite":
        _write_sqlite(records, destination)
    elif fmt == "urls":
        _write_urls(records, destination)
    else:
        raise ValueError(f"Unsupported output format: {fmt}")


def write_urls(records: Sequence[ArticleMetadata], destination: Path) -> None:
    """Write downloadable URLs to a text file for batch downloading."""

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Writing URLs for %d records to %s", len(records), destination)
    _write_urls(records, destination)


def _write_json(records: Sequence[ArticleMetadata], destination: Path) -> None:
    payload = [record.to_dict() for record in records]
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(records: Sequence[ArticleMetadata], destination: Path) -> None:
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "pmid",
                "title",
                "abstract",
                "first_author",
                "publication_year",
                "journal",
                "xml_available",
                "patient_level_evidence",
                "pmcid",
                "doi",
                "pubmed_url",
                "pmc_url",
                "doi_url",
                "pmc_pdf_url",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())


def _write_sqlite(records: Sequence[ArticleMetadata], destination: Path) -> None:
    connection = sqlite3.connect(destination)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                pmid TEXT PRIMARY KEY,
                title TEXT,
                abstract TEXT,
                first_author TEXT,
                publication_year INTEGER,
                journal TEXT,
                xml_available INTEGER,
                patient_level_evidence INTEGER,
                pmcid TEXT,
                doi TEXT,
                pubmed_url TEXT,
                pmc_url TEXT,
                doi_url TEXT,
                pmc_pdf_url TEXT
            )
            """
        )
        connection.execute("DELETE FROM articles")
        connection.executemany(
            """
            INSERT OR REPLACE INTO articles (
                pmid,
                title,
                abstract,
                first_author,
                publication_year,
                journal,
                xml_available,
                patient_level_evidence,
                pmcid,
                doi,
                pubmed_url,
                pmc_url,
                doi_url,
                pmc_pdf_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.pmid,
                    record.title,
                    record.abstract,
                    record.first_author,
                    record.publication_year,
                    record.journal,
                    1 if record.xml_available else 0,
                    1 if record.patient_level_evidence else 0,
                    record.pmcid,
                    record.doi,
                    record.pubmed_url,
                    record.pmc_url,
                    record.doi_url,
                    record.pmc_pdf_url,
                )
                for record in records
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _write_urls(records: Sequence[ArticleMetadata], destination: Path) -> None:
    """Write downloadable URLs to a text file."""

    with destination.open("w", encoding="utf-8") as handle:
        handle.write("# Downloadable URLs for Literature Collection\n")
        handle.write("# Format: PMID | First Author | Year | Journal | URL Type | URL\n")
        handle.write("# " + "=" * 78 + "\n\n")

        for record in records:
            # Basic metadata for context
            author = record.first_author or "Unknown"
            year = record.publication_year or "N/A"
            journal = record.journal or "Unknown"
            title = record.title or "No title"

            handle.write(f"# PMID: {record.pmid}\n")
            handle.write(f"# Title: {title}\n")
            handle.write(f"# Author: {author} ({year}) - {journal}\n")

            # Always write PubMed URL
            if record.pubmed_url:
                handle.write(f"{record.pubmed_url}  # PubMed page\n")

            # PMC full-text URL
            if record.pmc_url:
                handle.write(f"{record.pmc_url}  # PMC full-text HTML\n")

            # PMC PDF URL
            if record.pmc_pdf_url:
                handle.write(f"{record.pmc_pdf_url}  # PMC PDF\n")

            # DOI URL (may redirect to publisher)
            if record.doi_url:
                handle.write(f"{record.doi_url}  # DOI (publisher link)\n")

            handle.write("\n")
