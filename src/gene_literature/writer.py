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
    else:
        raise ValueError(f"Unsupported output format: {fmt}")


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
                patient_level_evidence INTEGER
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
                patient_level_evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                )
                for record in records
            ],
        )
        connection.commit()
    finally:
        connection.close()
