"""Interfaces for running LLM-based schema-guided extraction."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:  # pragma: no cover - optional dependency
    import google.generativeai as genai
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import anthropic
except ImportError:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import openai
except ImportError:  # pragma: no cover - optional dependency
    openai = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None  # type: ignore

from .models import ExtractionResult, PhenotypeObservation

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA = Path(__file__).resolve().parent / "schema" / "default_schema.json"


class ExtractorError(RuntimeError):
    """Raised when schema-guided extraction cannot be completed."""


class BaseExtractor:
    """Protocol that all extractor implementations must satisfy."""

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        raise NotImplementedError


def _canonicalize_model_name(model: str) -> str:
    """Return a Gemini model identifier acceptable to the google-generativeai library."""

    if not model:
        raise ValueError("Gemini model name must be a non-empty string")

    # For google-generativeai, we want just the model name without prefixes
    # Strip any existing prefixes to normalize
    if model.startswith("models/"):
        return model.replace("models/", "")
    if model.startswith("tunedModels/"):
        return model.replace("tunedModels/", "")
    
    # Return the bare model name
    return model


# Allow deployments to override the Gemini model at import time via an
# environment variable. This accommodates accounts that do not yet have access
# to the newest Gemini releases. The extractor will canonicalize the identifier
# for API usage, so the environment variable may contain either the bare Gemini
# name (e.g., ``gemini-1.5-flash``) or the fully qualified value (e.g.,
# ``models/gemini-1.5-flash``).
DEFAULT_GEMINI_MODEL = os.getenv("GENEPHENEXTRACT_GEMINI_MODEL", "gemini-pro") or "gemini-pro"
DEFAULT_GEMINI_MODEL = "gemini-1.5-pro-latest"
GEMINI_MODEL_ENV_VAR = "GENEPHENEXTRACT_GEMINI_MODEL"
GEMINI_MODEL_PREFERENCE: Sequence[str] = (
    "gemini-1.5-pro-latest",
    "gemini-1.5-pro",
    "gemini-1.0-pro-latest",
    "gemini-1.0-pro",
    "gemini-pro",
    "gemini-1.0-pro-001",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
)


def _resolve_model_name(model: Optional[str]) -> str:
    """Return the Gemini model name to use for extraction."""

    if model:
        return model

    env_model = os.getenv(GEMINI_MODEL_ENV_VAR)
    if env_model:
        return env_model

    return DEFAULT_GEMINI_MODEL


def _normalise_model_name(model_name: str) -> str:
    """Return the canonical Gemini model identifier without API prefixes."""

    return model_name.split("/")[-1]


def _list_available_models() -> List[str]:
    """Return Gemini model identifiers that support generateContent.

    Returns an empty list if the SDK is unavailable or the API call fails.
    """

    if genai is None:  # pragma: no cover - optional dependency
        return []

    try:  # pragma: no cover - network/API dependent
        models = genai.list_models()
    except Exception:  # pragma: no cover - network/API dependent
        logger.debug("Unable to list Gemini models", exc_info=True)
        return []

    available: List[str] = []
    for model in models:
        supported = getattr(model, "supported_generation_methods", [])
        if "generateContent" in supported:
            available.append(_normalise_model_name(getattr(model, "name", "")))

    return sorted(set(filter(None, available)))


def _select_preferred_model(available_models: Sequence[str]) -> Optional[str]:
    """Return the best available model according to preference ordering."""

    available_set = set(available_models)
    for preferred in GEMINI_MODEL_PREFERENCE:
        if preferred in available_set:
            return preferred

    return available_models[0] if available_models else None


class GeminiExtractor(BaseExtractor):
    """Implementation that uses Google's Gemini API directly for extraction."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        if genai is None:  # pragma: no cover - optional dependency
            msg = "google-generativeai is not installed. Install it with `pip install google-generativeai`."
            raise ImportError(msg)

        if not api_key:
            msg = "API key is required for GeminiExtractor"
            raise ValueError(msg)

        genai.configure(api_key=api_key)
        self.model_name = _resolve_model_name(model)
        env_model = os.getenv(GEMINI_MODEL_ENV_VAR)
        model_source = "argument" if model else ("environment" if env_model else "default")

        available_models = _list_available_models()
        if available_models and self.model_name not in available_models:
            if model_source in {"argument", "environment"}:
                msg = (
                    f"Gemini model '{self.model_name}' is not available for your API key. "
                    f"Available models: {', '.join(available_models)}"
                )
                raise ExtractorError(msg)

            fallback = _select_preferred_model(available_models)
            if fallback is None:
                msg = (
                    "No Gemini models supporting generateContent are available to your API key. "
                    "Verify the key has access to at least one generative model."
                )
                raise ExtractorError(msg)

            logger.warning(
                "Default Gemini model '%s' unavailable; falling back to '%s'", self.model_name, fallback
            )
            self.model_name = fallback

        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception as exc:  # pragma: no cover - network/API dependent
            msg = (
                f"Failed to initialise Gemini model '{self.model_name}'. "
                f"Set {GEMINI_MODEL_ENV_VAR} or pass model='<model-name>' to GeminiExtractor."
            )
            raise ExtractorError(msg) from exc

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        schema = _load_schema(schema_path)
        logger.debug("Running Gemini extraction with schema %s", schema_path or DEFAULT_SCHEMA)
        
        # Create the prompt for Gemini
        prompt = self._create_extraction_prompt(text, schema)
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text
            
            # Parse the JSON response
            # Remove markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result_data = json.loads(result_text)
            logger.debug("Successfully extracted data from text")
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from Gemini response: %s", e)
            logger.debug("Response text: %s", result_text)
            raise ExtractorError(f"Failed to parse extraction result: {e}") from e
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            hints = []
            if self.requested_model:
                hints.append(
                    "The model '%s' may not be available to your account." % self.requested_model
                )
                hints.append(
                    "Set the GENEPHENEXTRACT_GEMINI_MODEL environment variable or pass --model to the CLI with a supported identifier."
                )
                if self.requested_model != self.model_name:
                    hints.append(
                        "Gemini expects fully qualified identifiers such as '%s'."
                        % self.model_name
                    )

            message = f"Gemini extraction failed: {e}"
            if hints:
                message = f"{message}. {' '.join(hints)}"
            raise ExtractorError(message) from e
        
        return _result_from_payload(result_data, pmid=pmid)

    def _create_extraction_prompt(self, text: str, schema: Dict[str, Any]) -> str:
        """Create a prompt for Gemini to extract structured data."""
        prompt = f"""You are a medical text extraction expert. Extract structured information from the following scientific text about genetic variants and phenotypes.

Extract the following information according to this JSON schema:
{json.dumps(schema, indent=2)}

Text to analyze:
{text}

Requirements:
1. Extract the genetic variant (gene and mutation) mentioned in the text
2. Extract all phenotypes (clinical symptoms or conditions) mentioned
3. If mentioned, extract carrier status (heterozygous, homozygous, compound heterozygous)
4. If mentioned, extract patient age, sex, treatment, and outcome
5. For phenotypes, provide the phenotype name. Ontology IDs are optional.

Return ONLY a valid JSON object matching the schema. Do not include any explanation or markdown formatting.

Example output format:
{{
  "variant": "KCNH2 c.2717C>T p.(Ser906Leu)",
  "carrier_status": "heterozygous",
  "phenotypes": [
    {{"name": "prolonged QT interval"}},
    {{"name": "syncope"}}
  ],
  "age": 45,
  "sex": "female",
  "treatment": "beta-blocker",
  "outcome": "stable"
}}

Now extract from the provided text:"""
        
        return prompt


def _load_schema(schema_path: Optional[Path]) -> Dict[str, Any]:
    if schema_path is None:
        schema_path = DEFAULT_SCHEMA
    resolved = Path(schema_path).expanduser().resolve()
    if not resolved.exists():
        msg = f"Schema file not found: {resolved}"
        raise ExtractorError(msg)
    logger.debug("Loading schema from %s", resolved)
    return json.loads(resolved.read_text())


def _result_from_payload(payload: Dict[str, Any], *, pmid: str) -> ExtractionResult:
    fields = {
        "pmid": pmid,
        "variant": payload.get("variant", ""),
        "carrier_status": payload.get("carrier_status"),
        "age": payload.get("age"),
        "sex": payload.get("sex"),
        "treatment": payload.get("treatment"),
        "outcome": payload.get("outcome"),
        "title": payload.get("title"),
        "journal": payload.get("journal"),
        "publication_date": payload.get("publication_date"),
        "abstract": payload.get("abstract"),
    }

    phenotypes: Iterable[Dict[str, Any]] = payload.get("phenotypes", [])
    fields["phenotypes"] = [
        PhenotypeObservation(
            phenotype=phenotype.get("name", ""),
            ontology_id=phenotype.get("ontology_id"),
            onset_age=phenotype.get("onset_age"),
            notes=phenotype.get("notes"),
        )
        for phenotype in phenotypes
    ]
    return ExtractionResult(**fields)


class MockExtractor(BaseExtractor):
    """Simple extractor used for tests and local development."""

    def __init__(self, canned_response: Optional[Dict[str, Any]] = None) -> None:
        self.canned_response = canned_response or {
            "variant": "KCNH2 p.Tyr54Asn",
            "carrier_status": "heterozygous",
            "phenotypes": [
                {
                    "name": "prolonged QT interval",
                    "ontology_id": "HP:0001657",
                }
            ],
            "age": 34,
            "sex": "female",
            "treatment": "beta-blocker",
        }

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        del text, schema_path
        return _result_from_payload(self.canned_response, pmid=pmid)


class ClaudeExtractor(BaseExtractor):
    """Extractor using Anthropic's Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
    ) -> None:
        if anthropic is None:
            msg = "anthropic package not installed. Install it with `pip install anthropic`."
            raise ImportError(msg)

        if not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            msg = "API key required. Provide via api_key parameter or ANTHROPIC_API_KEY environment variable."
            raise ValueError(msg)

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        logger.info("Initialized ClaudeExtractor with model %s", model)

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        schema = _load_schema(schema_path)
        prompt = self._create_extraction_prompt(text, schema)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # Parse JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result_data = json.loads(response_text)
            logger.debug("Successfully extracted data using Claude")
            return _result_from_payload(result_data, pmid=pmid)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from Claude response: %s", e)
            raise ExtractorError(f"Failed to parse extraction result: {e}") from e
        except Exception as e:
            logger.error("Claude API error: %s", e)
            raise ExtractorError(f"Claude extraction failed: {e}") from e

    def _create_extraction_prompt(self, text: str, schema: Dict[str, Any]) -> str:
        return f"""You are a medical text extraction expert. Extract structured information from the following scientific text about genetic variants and phenotypes.

Extract the following information according to this JSON schema:
{json.dumps(schema, indent=2)}

Text to analyze:
{text}

Requirements:
1. Extract the genetic variant (gene and mutation) mentioned in the text
2. Extract all phenotypes (clinical symptoms or conditions) mentioned
3. If mentioned, extract carrier status (heterozygous, homozygous, compound heterozygous)
4. If mentioned, extract patient age, sex, treatment, and outcome
5. For phenotypes, provide the phenotype name. Ontology IDs are optional.

Return ONLY a valid JSON object matching the schema. Do not include any explanation or markdown formatting.

Example output format:
{{
  "variant": "KCNH2 c.2717C>T p.(Ser906Leu)",
  "carrier_status": "heterozygous",
  "phenotypes": [
    {{"name": "prolonged QT interval"}},
    {{"name": "syncope"}}
  ],
  "age": 45,
  "sex": "female",
  "treatment": "beta-blocker",
  "outcome": "stable"
}}"""


class OpenAIExtractor(BaseExtractor):
    """Extractor using OpenAI's API (GPT-4, GPT-3.5, etc.)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ) -> None:
        if openai is None:
            msg = "openai package not installed. Install it with `pip install openai`."
            raise ImportError(msg)

        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            msg = "API key required. Provide via api_key parameter or OPENAI_API_KEY environment variable."
            raise ValueError(msg)

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        logger.info("Initialized OpenAIExtractor with model %s", model)

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        schema = _load_schema(schema_path)
        prompt = self._create_extraction_prompt(text, schema)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical text extraction expert. Extract structured genotype-phenotype information from scientific texts.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content

            result_data = json.loads(response_text)
            logger.debug("Successfully extracted data using OpenAI")
            return _result_from_payload(result_data, pmid=pmid)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from OpenAI response: %s", e)
            raise ExtractorError(f"Failed to parse extraction result: {e}") from e
        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            raise ExtractorError(f"OpenAI extraction failed: {e}") from e

    def _create_extraction_prompt(self, text: str, schema: Dict[str, Any]) -> str:
        return f"""Extract structured information from this scientific text about genetic variants and phenotypes.

Schema:
{json.dumps(schema, indent=2)}

Text:
{text}

Extract:
1. Genetic variant (gene and mutation)
2. All phenotypes (clinical symptoms/conditions)
3. Carrier status if mentioned (heterozygous, homozygous, compound heterozygous)
4. Patient demographics if mentioned (age, sex)
5. Treatment and outcome if mentioned

Return ONLY valid JSON matching the schema."""


class GroqExtractor(BaseExtractor):
    """Extractor using Groq's ultra-fast inference API.

    Groq provides extremely fast inference with generous free tier limits.
    Uses OpenAI-compatible API with models like Llama 3.3 70B, Mixtral, etc.

    Free tier: 30 requests/minute
    Paid tier: $0.59/1M tokens for llama-3.3-70b-versatile
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.0,
    ) -> None:
        if Groq is None:
            msg = "groq package not installed. Install it with `pip install groq`."
            raise ImportError(msg)

        if not api_key:
            api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            msg = "API key required. Provide via api_key parameter or GROQ_API_KEY environment variable."
            raise ValueError(msg)

        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature
        logger.info("Initialized GroqExtractor with model %s", model)

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        schema = _load_schema(schema_path)
        prompt = self._create_extraction_prompt(text, schema)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical text extraction expert. Extract structured genotype-phenotype information from scientific texts.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content

            result_data = json.loads(response_text)
            logger.debug("Successfully extracted data using Groq")
            return _result_from_payload(result_data, pmid=pmid)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from Groq response: %s", e)
            raise ExtractorError(f"Failed to parse extraction result: {e}") from e
        except Exception as e:
            logger.error("Groq API error: %s", e)
            raise ExtractorError(f"Groq extraction failed: {e}") from e

    def _create_extraction_prompt(self, text: str, schema: Dict[str, Any]) -> str:
        return f"""Extract structured information from this scientific text about genetic variants and phenotypes.

Schema:
{json.dumps(schema, indent=2)}

Text:
{text}

Extract:
1. Genetic variant (gene and mutation)
2. All phenotypes (clinical symptoms/conditions)
3. Carrier status if mentioned (heterozygous, homozygous, compound heterozygous)
4. Patient demographics if mentioned (age, sex)
5. Treatment and outcome if mentioned

Return ONLY valid JSON matching the schema."""


class RelevanceFilter:
    """Fast, cheap LLM filter to determine if an article is relevant before expensive extraction."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "openai",
        model: Optional[str] = None,
    ) -> None:
        """Initialize relevance filter.

        Args:
            api_key: API key for the provider
            provider: One of "openai", "anthropic", "gemini", or "groq"
            model: Model to use. Defaults to cheapest option for each provider.
        """
        self.provider = provider.lower()

        if self.provider == "openai":
            if openai is None:
                raise ImportError("openai package not installed")
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key required")
            self.client = openai.OpenAI(api_key=api_key)
            self.model = model or "gpt-4o-mini"  # Cheapest OpenAI model

        elif self.provider == "anthropic":
            if anthropic is None:
                raise ImportError("anthropic package not installed")
            if not api_key:
                api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("Anthropic API key required")
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model or "claude-3-haiku-20240307"  # Cheapest Claude model

        elif self.provider == "gemini":
            if genai is None:
                raise ImportError("google-generativeai package not installed")
            if not api_key:
                api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("Google API key required")
            genai.configure(api_key=api_key)
            self.model = model or "gemini-1.5-flash"  # Fast, cheap Gemini model
            self.client = genai.GenerativeModel(self.model)

        elif self.provider == "groq":
            if Groq is None:
                raise ImportError("groq package not installed")
            if not api_key:
                api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("Groq API key required")
            self.client = Groq(api_key=api_key)
            self.model = model or "llama-3.3-70b-versatile"  # Fast, free Groq model

        else:
            raise ValueError(f"Unsupported provider: {provider}")

        logger.info("Initialized RelevanceFilter with %s/%s", provider, self.model)

    def is_relevant(self, text: str, query_context: Optional[str] = None) -> tuple[bool, float, str]:
        """Check if text is relevant for extraction.

        Args:
            text: Article text (abstract or full-text)
            query_context: Optional context about what we're looking for

        Returns:
            Tuple of (is_relevant, confidence_score, reason)
        """
        prompt = self._create_filter_prompt(text, query_context)

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a medical literature filter. Determine if articles contain genetic variant and phenotype information.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                result = json.loads(response.choices[0].message.content)

            elif self.provider == "anthropic":
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = message.content[0].text
                # Extract JSON from response
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                result = json.loads(content)

            elif self.provider == "gemini":
                response = self.client.generate_content(prompt)
                content = response.text
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                result = json.loads(content)

            elif self.provider == "groq":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a medical literature filter. Determine if articles contain genetic variant and phenotype information.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                result = json.loads(response.choices[0].message.content)

            is_relevant = result.get("relevant", False)
            confidence = result.get("confidence", 0.5)
            reason = result.get("reason", "")

            logger.debug("Relevance check: relevant=%s, confidence=%.2f", is_relevant, confidence)
            return is_relevant, confidence, reason

        except Exception as e:
            logger.warning("Relevance filter error: %s. Assuming relevant.", e)
            # On error, assume relevant to avoid false negatives
            return True, 0.5, f"Filter error: {e}"

    def _create_filter_prompt(self, text: str, query_context: Optional[str] = None) -> str:
        context_info = f"\n\nWe are specifically looking for: {query_context}" if query_context else ""

        return f"""Determine if this scientific article contains information about:
1. Specific genetic variants (gene names and mutations)
2. Associated phenotypes or clinical outcomes
3. Patient data or case reports

{context_info}

Article text:
{text[:2000]}...

Return JSON with:
{{
  "relevant": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}}

Be strict: only mark as relevant if the article clearly discusses specific genetic variants with phenotype data."""


class MultiStageExtractor(BaseExtractor):
    """Two-stage extraction: cheap filter first, then expensive extraction if relevant."""

    def __init__(
        self,
        filter: RelevanceFilter,
        extractor: BaseExtractor,
        min_confidence: float = 0.7,
    ) -> None:
        """Initialize multi-stage extractor.

        Args:
            filter: RelevanceFilter for first-pass filtering
            extractor: Primary extractor to use for relevant articles
            min_confidence: Minimum confidence score to proceed with extraction (0.0-1.0)
        """
        self.filter = filter
        self.extractor = extractor
        self.min_confidence = min_confidence
        self.stats = {"filtered": 0, "extracted": 0, "skipped": 0}
        logger.info("Initialized MultiStageExtractor with min_confidence=%.2f", min_confidence)

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        # First stage: cheap relevance check
        is_relevant, confidence, reason = self.filter.is_relevant(text)

        if not is_relevant or confidence < self.min_confidence:
            self.stats["skipped"] += 1
            logger.info(
                "Skipping PMID %s (relevance=%.2f, threshold=%.2f): %s",
                pmid,
                confidence,
                self.min_confidence,
                reason,
            )
            # Return empty result for irrelevant articles
            return ExtractionResult(
                pmid=pmid,
                variant="",
                phenotypes=[],
                notes=f"Filtered out: {reason} (confidence: {confidence:.2f})",
            )

        # Second stage: expensive extraction
        self.stats["extracted"] += 1
        logger.info("Processing PMID %s with full extraction (relevance=%.2f)", pmid, confidence)
        return self.extractor.extract(text, pmid=pmid, schema_path=schema_path)

    def get_stats(self) -> Dict[str, int]:
        """Get statistics on filtering vs extraction."""
        return self.stats.copy()
