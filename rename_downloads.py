"""Rename and organize downloaded literature files based on metadata.

This script helps manage downloaded PDFs, Word docs, and other files by:
1. Matching downloaded files to their metadata records (PMID, author, year, journal)
2. Renaming files using the standardized format: PMID_FirstAuthorLastName_Year_Journal.ext
3. Organizing files into gene-specific subfolders
4. Logging any files that cannot be matched
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


class FileRenamer:
    """Handle renaming and organizing downloaded literature files."""

    def __init__(self, metadata_path: Path, metadata_format: str = "json"):
        """Initialize the file renamer with metadata.

        Args:
            metadata_path: Path to the metadata file (JSON, CSV, or SQLite)
            metadata_format: Format of the metadata file
        """
        self.metadata_path = metadata_path
        self.metadata_format = metadata_format.lower()
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> List[Dict]:
        """Load metadata from the specified file."""

        if self.metadata_format == "json":
            return self._load_json()
        elif self.metadata_format == "sqlite":
            return self._load_sqlite()
        else:
            raise ValueError(f"Unsupported metadata format: {self.metadata_format}")

    def _load_json(self) -> List[Dict]:
        """Load metadata from JSON file."""

        with self.metadata_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded %d metadata records from JSON", len(data))
        return data

    def _load_sqlite(self) -> List[Dict]:
        """Load metadata from SQLite database."""

        connection = sqlite3.connect(self.metadata_path)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.execute("SELECT * FROM articles")
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            logger.info("Loaded %d metadata records from SQLite", len(data))
            return data
        finally:
            connection.close()

    def _extract_pmid_from_filename(self, filename: str) -> Optional[str]:
        """Try to extract PMID from filename.

        Looks for patterns like:
        - PMID12345678.pdf
        - 12345678.pdf (8-digit number)
        - pubmed_12345678.pdf
        - PMC12345678.pdf (extracts the number)
        """

        # Try explicit PMID pattern
        match = re.search(r"PMID[_\-]?(\d{7,8})", filename, re.IGNORECASE)
        if match:
            return match.group(1)

        # Try standalone 7-8 digit number
        match = re.search(r"\b(\d{7,8})\b", filename)
        if match:
            return match.group(1)

        return None

    def _sanitize_filename_part(self, text: str) -> str:
        """Sanitize a text string for use in filename.

        Removes or replaces characters that are problematic in filenames.
        """

        if not text:
            return "Unknown"

        # Replace problematic characters with underscores
        text = re.sub(r'[<>:"/\\|?*]', "_", text)
        # Replace multiple spaces with single space
        text = re.sub(r"\s+", " ", text)
        # Remove leading/trailing spaces
        text = text.strip()
        # Limit length
        if len(text) > 50:
            text = text[:50]

        return text or "Unknown"

    def _extract_last_name(self, full_name: Optional[str]) -> str:
        """Extract last name from full author name."""

        if not full_name:
            return "UnknownAuthor"

        # Handle "FirstName LastName" format
        parts = full_name.split()
        if len(parts) >= 2:
            return self._sanitize_filename_part(parts[-1])
        elif len(parts) == 1:
            return self._sanitize_filename_part(parts[0])

        return "UnknownAuthor"

    def _build_new_filename(self, metadata: Dict, extension: str) -> str:
        """Build standardized filename from metadata.

        Format: PMID_LastName_Year_Journal.ext
        """

        pmid = metadata.get("pmid", "UnknownPMID")
        author = self._extract_last_name(metadata.get("first_author"))
        year = metadata.get("publication_year", "NoYear")
        journal = self._sanitize_filename_part(metadata.get("journal", "UnknownJournal"))

        # Create filename
        new_name = f"{pmid}_{author}_{year}_{journal}{extension}"

        return new_name

    def process_downloads(
        self,
        download_dir: Path,
        output_dir: Path,
        gene: str,
        *,
        dry_run: bool = False,
        log_file: Optional[Path] = None,
    ) -> Dict[str, List[str]]:
        """Process downloaded files and organize them.

        Args:
            download_dir: Directory containing downloaded files
            output_dir: Base directory for organized files
            gene: Gene symbol for subfolder organization
            dry_run: If True, only log what would be done without moving files
            log_file: Optional path to write detailed processing log

        Returns:
            Dictionary with 'matched', 'renamed', and 'unmatched' file lists
        """

        download_dir = download_dir.expanduser().resolve()
        output_dir = output_dir.expanduser().resolve()

        if not download_dir.exists():
            raise FileNotFoundError(f"Download directory not found: {download_dir}")

        # Create gene-specific output directory
        gene_dir = output_dir / gene
        if not dry_run:
            gene_dir.mkdir(parents=True, exist_ok=True)

        # Prepare results tracking
        results = {"matched": [], "renamed": [], "unmatched": []}

        # Create metadata lookup by PMID
        metadata_by_pmid: Dict[str, Dict] = {}
        for record in self.metadata:
            pmid = record.get("pmid")
            if pmid:
                metadata_by_pmid[pmid] = record

        logger.info("Processing files in %s", download_dir)

        # Process files
        for file_path in download_dir.iterdir():
            if file_path.is_dir():
                continue

            # Skip hidden files and system files
            if file_path.name.startswith("."):
                continue

            # Try to extract PMID from filename
            pmid = self._extract_pmid_from_filename(file_path.name)

            if pmid and pmid in metadata_by_pmid:
                # Found matching metadata
                metadata = metadata_by_pmid[pmid]
                extension = file_path.suffix
                new_filename = self._build_new_filename(metadata, extension)
                new_path = gene_dir / new_filename

                logger.info("Matched: %s -> %s", file_path.name, new_filename)
                results["matched"].append(file_path.name)
                results["renamed"].append(new_filename)

                if not dry_run:
                    # Copy or move file
                    shutil.copy2(file_path, new_path)
                    logger.debug("Copied %s to %s", file_path, new_path)
            else:
                # Could not match file
                logger.warning("Unmatched file (no PMID or metadata found): %s", file_path.name)
                results["unmatched"].append(file_path.name)

        # Write log file if requested
        if log_file and not dry_run:
            self._write_log(results, log_file)

        # Print summary
        logger.info("Processing complete:")
        logger.info("  Matched files: %d", len(results["matched"]))
        logger.info("  Renamed files: %d", len(results["renamed"]))
        logger.info("  Unmatched files: %d", len(results["unmatched"]))

        return results

    def _write_log(self, results: Dict[str, List[str]], log_file: Path) -> None:
        """Write detailed processing log to file."""

        with log_file.open("w", encoding="utf-8") as f:
            f.write("# File Renaming Log\n\n")

            f.write("## Matched and Renamed Files\n\n")
            for i, (orig, new) in enumerate(zip(results["matched"], results["renamed"]), 1):
                f.write(f"{i}. {orig} -> {new}\n")

            f.write(f"\n## Unmatched Files ({len(results['unmatched'])})\n\n")
            for i, filename in enumerate(results["unmatched"], 1):
                f.write(f"{i}. {filename}\n")

        logger.info("Wrote processing log to %s", log_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("gene", help="Gene symbol for organizing files")
    parser.add_argument("download_dir", type=Path, help="Directory containing downloaded files")
    parser.add_argument("metadata_file", type=Path, help="Path to metadata file (JSON or SQLite)")

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("organized_literature"),
        help="Base directory for organized files (default: organized_literature)",
    )

    parser.add_argument(
        "--metadata-format",
        choices=["json", "sqlite"],
        default="json",
        help="Format of metadata file (default: json)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually moving files",
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write detailed processing log to this file",
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

    # Initialize renamer
    renamer = FileRenamer(args.metadata_file, args.metadata_format)

    # Process downloads
    results = renamer.process_downloads(
        download_dir=args.download_dir,
        output_dir=args.output_dir,
        gene=args.gene,
        dry_run=args.dry_run,
        log_file=args.log_file,
    )

    # Exit with non-zero code if there are unmatched files
    if results["unmatched"]:
        logger.warning("Some files could not be matched. Use --log-file to save details.")
        exit(1)


if __name__ == "__main__":
    main()
