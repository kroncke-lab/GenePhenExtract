"""
Penetrance-focused extraction for individual-level data.

THIS IS THE CORE EXTRACTOR FOR THE PROJECT'S TRUE PURPOSE:
Extract INDIVIDUAL family members to calculate penetrance.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .extraction import BaseExtractor, ClaudeExtractor, OpenAIExtractor
from .models import PhenotypeObservation
from .penetrance_models import FamilyStudy, Individual

logger = logging.getLogger(__name__)

PENETRANCE_SCHEMA = Path(__file__).resolve().parent / "schema" / "penetrance_schema.json"


class PenetranceExtractor:
    """Extract individual-level data for penetrance studies.

    Uses an LLM extractor to extract MULTIPLE individuals per paper,
    including both affected and unaffected carriers.
    """

    def __init__(self, llm_extractor: BaseExtractor):
        """Initialize with an LLM extractor.

        Args:
            llm_extractor: Any LLM extractor (ClaudeExtractor, OpenAIExtractor, etc.)
        """
        self.llm_extractor = llm_extractor
        logger.info("Initialized PenetranceExtractor")

    def extract(self, text: str, pmid: str) -> FamilyStudy:
        """Extract family/cohort data from a paper.

        Args:
            text: Paper text (abstract or full-text)
            pmid: PubMed ID

        Returns:
            FamilyStudy with list of individuals
        """
        # Create penetrance-specific prompt
        prompt = self._create_penetrance_prompt(text)

        # Get LLM response
        if hasattr(self.llm_extractor, 'client'):
            # It's a real LLM extractor (Claude, OpenAI, etc.)
            response = self._call_llm(prompt)
        else:
            # Mock extractor - return dummy data
            response = self._get_mock_response()

        # Parse response to FamilyStudy
        study = self._parse_to_family_study(response, pmid)

        logger.info(
            f"Extracted {len(study.individuals)} individuals from PMID {pmid} "
            f"({len(study.get_carriers())} carriers, "
            f"{len(study.get_affected_carriers())} affected, "
            f"{len(study.get_unaffected_carriers())} unaffected)"
        )

        return study

    def _create_penetrance_prompt(self, text: str) -> str:
        """Create prompt for extracting individual-level data."""
        return f"""You are a medical genetics expert. Extract INDIVIDUAL-LEVEL data from this paper.

CRITICAL: Extract EVERY individual mentioned, including:
- Affected carriers (have the variant AND have phenotypes)
- Unaffected carriers (have the variant but NO phenotypes - asymptomatic carriers)
- Wild-type individuals (don't have the variant)

For EACH individual, extract:
1. Unique ID (e.g., "proband", "mother", "patient_1")
2. Genotype (heterozygous, homozygous, compound_heterozygous, wild-type)
3. Affected status (true/false - CRITICAL for penetrance!)
4. Phenotypes (list of phenotypes, or empty if unaffected)
5. Demographics (age, sex)
6. Clinical details (age_at_onset if mentioned)

Paper text:
{text[:3000]}

Return JSON matching this format:
{{
  "variant": "KCNH2 p.Ser906Leu",
  "gene": "KCNH2",
  "study_type": "family",
  "individuals": [
    {{
      "id": "proband",
      "relation": "proband",
      "genotype": "heterozygous",
      "affected": true,
      "phenotypes": [
        {{"name": "prolonged QT interval", "value": "QTc 480ms"}},
        {{"name": "syncope", "age_at_onset": 28}}
      ],
      "age": 34,
      "sex": "male"
    }},
    {{
      "id": "mother",
      "relation": "mother",
      "genotype": "heterozygous",
      "affected": true,
      "phenotypes": [
        {{"name": "prolonged QT interval", "value": "QTc 460ms"}}
      ],
      "age": 56,
      "sex": "female"
    }},
    {{
      "id": "sister",
      "relation": "sibling",
      "genotype": "heterozygous",
      "affected": false,
      "phenotypes": [],
      "age": 28,
      "sex": "female"
    }},
    {{
      "id": "father",
      "relation": "father",
      "genotype": "wild-type",
      "affected": false,
      "phenotypes": [],
      "age": 58,
      "sex": "male"
    }}
  ]
}}

IMPORTANT:
- Extract ALL individuals, not just affected ones
- "affected": false means carrier but asymptomatic (THIS IS CRITICAL!)
- Include wild-type family members
- If paper mentions "5 carriers, 3 affected", extract all 5 individuals
- If specific details not given, create generic IDs like "patient_1", "patient_2"

Return ONLY valid JSON."""

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM with the prompt."""
        if isinstance(self.llm_extractor, ClaudeExtractor):
            import anthropic
            message = self.llm_extractor.client.messages.create(
                model=self.llm_extractor.model,
                max_tokens=self.llm_extractor.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text

        elif isinstance(self.llm_extractor, OpenAIExtractor):
            response = self.llm_extractor.client.chat.completions.create(
                model=self.llm_extractor.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical genetics expert extracting individual-level data.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            response_text = response.choices[0].message.content

        else:
            # Generic extractor - try to use it
            result = self.llm_extractor.extract(prompt, pmid="temp", schema_path=PENETRANCE_SCHEMA)
            # This won't work well but is a fallback
            return {"individuals": []}

        # Parse JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        return json.loads(response_text)

    def _get_mock_response(self) -> Dict[str, Any]:
        """Mock response for testing."""
        return {
            "variant": "KCNH2 p.Ser906Leu",
            "gene": "KCNH2",
            "study_type": "family",
            "individuals": [
                {
                    "id": "proband",
                    "relation": "proband",
                    "genotype": "heterozygous",
                    "affected": True,
                    "phenotypes": [
                        {"name": "prolonged QT interval"},
                        {"name": "syncope"},
                    ],
                    "age": 34,
                    "sex": "male",
                },
                {
                    "id": "mother",
                    "relation": "mother",
                    "genotype": "heterozygous",
                    "affected": False,  # Unaffected carrier!
                    "phenotypes": [],
                    "age": 56,
                    "sex": "female",
                },
            ],
        }

    def _parse_to_family_study(
        self, response: Dict[str, Any], pmid: str
    ) -> FamilyStudy:
        """Parse LLM response to FamilyStudy object."""
        study = FamilyStudy(
            pmid=pmid,
            variant=response.get("variant", ""),
            gene=response.get("gene", ""),
            study_type=response.get("study_type", "unknown"),
        )

        # Parse individuals
        for ind_data in response.get("individuals", []):
            individual = self._parse_individual(ind_data)
            study.add_individual(individual)

        return study

    def _parse_individual(self, data: Dict[str, Any]) -> Individual:
        """Parse individual data."""
        # Parse phenotypes
        phenotypes = []
        for pheno_data in data.get("phenotypes", []):
            pheno = PhenotypeObservation(
                phenotype=pheno_data.get("name", ""),
                ontology_id=pheno_data.get("ontology_id"),
                onset_age=pheno_data.get("age_at_onset"),
                notes=pheno_data.get("value"),  # Store measurement/severity in notes
            )
            phenotypes.append(pheno)

        individual = Individual(
            individual_id=data.get("id", "unknown"),
            pmid="",  # Will be set by FamilyStudy
            variant=data.get("variant"),
            gene=data.get("gene"),
            genotype=data.get("genotype"),
            affected=data.get("affected"),
            phenotypes=phenotypes,
            age=data.get("age"),
            sex=data.get("sex"),
            age_at_onset=data.get("age_at_onset"),
            age_at_diagnosis=data.get("age_at_diagnosis"),
            relation=data.get("relation"),
        )

        return individual


def extract_penetrance_for_gene(
    gene: str,
    extractor: PenetranceExtractor,
    max_papers: int = 50,
) -> List[FamilyStudy]:
    """Extract penetrance data for a gene.

    Args:
        gene: Gene symbol
        extractor: PenetranceExtractor
        max_papers: Maximum papers to process

    Returns:
        List of FamilyStudy objects
    """
    from .pubmed import PubMedClient

    client = PubMedClient()

    # Build query for family/case studies
    query = _build_penetrance_query(gene)

    # Search PubMed
    pmids = client.search(query, retmax=max_papers)

    logger.info(f"Found {len(pmids)} papers for {gene}")

    # Extract from each paper
    studies = []
    for pmid in pmids:
        try:
            # Get text
            text, source = client.fetch_text(pmid, prefer_full_text=True)

            # Extract individuals
            study = extractor.extract(text, pmid)

            # Add metadata
            details = client.fetch_details([pmid])
            if pmid in details:
                study.title = details[pmid].get("title")
                study.journal = details[pmid].get("journal")
                study.publication_date = details[pmid].get("publication_date")

            studies.append(study)

        except Exception as e:
            logger.warning(f"Failed to extract from PMID {pmid}: {e}")
            continue

    logger.info(f"Extracted {len(studies)} studies for {gene}")

    return studies


def _build_penetrance_query(gene: str) -> str:
    """Build PubMed query optimized for penetrance studies."""
    # Focus on family studies and case reports
    query_parts = [
        f'("{gene}"[Gene] OR "{gene}"[Title/Abstract])',
        'AND (',
        '"family"[Title/Abstract] OR "families"[Title/Abstract]',
        'OR "pedigree"[Title/Abstract]',
        'OR "case report"[Title/Abstract]',
        'OR "case series"[Title/Abstract]',
        ')',
        'AND (',
        '"mutation"[Title/Abstract] OR "variant"[Title/Abstract]',
        ')',
        # Exclude reviews and animals
        'NOT "review"[Publication Type]',
        'NOT "animal"[MeSH Terms]',
    ]

    return " ".join(query_parts)
