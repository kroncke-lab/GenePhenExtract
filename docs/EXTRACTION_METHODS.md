# Extraction Methods: Cohort vs Individual Data

GenePhenExtract supports two extraction methods to handle different ways papers report genotype-phenotype data:

1. **Cohort-level extraction** - For papers reporting aggregate counts
2. **Individual-level extraction** - For papers with detailed patient information

Both methods can be used together to build comprehensive databases.

## When to Use Each Method

### Use Cohort-Level Extraction When:

Papers report **aggregate statistics** without detailed individual information:

> "We studied 50 patients with heterozygous KCNH2 variants. 35 (70%) had long QT syndrome, 12 (24%) experienced syncope, and 15 (30%) were asymptomatic."

**Key indicators:**
- Total counts reported (e.g., "50 patients")
- Percentages or fractions (e.g., "35/50" or "70%")
- No individual patient details
- Large cohorts (typically n > 10)

**What you get:**
```python
CohortData(
    gene="KCNH2",
    genotype="heterozygous",
    total_carriers=50,
    phenotype_counts=[
        PhenotypeCount(phenotype="long QT syndrome", affected_count=35),
        PhenotypeCount(phenotype="syncope", affected_count=12),
    ]
)
```

**Benefits:**
- ✅ Simple counts: affected vs unaffected (total - affected)
- ✅ Easy to aggregate across papers
- ✅ Works with large cohorts
- ✅ No need to track individual demographics

### Use Individual-Level Extraction When:

Papers describe **specific patients** with individual characteristics:

> "The proband (male, age 23) carried a heterozygous KCNH2 p.Tyr54Asn variant and presented with long QT syndrome at age 18. His mother (age 45) was an asymptomatic heterozygous carrier. His father (age 47) did not carry the variant."

**Key indicators:**
- Individual patients described (e.g., "proband", "patient 1", "II-3")
- Family pedigrees
- Individual characteristics (age, sex, age at onset)
- Small studies (typically n < 10)
- Case reports

**What you get:**
```python
FamilyStudy(
    gene="KCNH2",
    variant="p.Tyr54Asn",
    individuals=[
        Individual(
            id="proband",
            genotype="heterozygous",
            affected=True,
            age=23,
            sex="male",
            age_at_onset=18,
            phenotypes=["long QT syndrome"]
        ),
        Individual(
            id="mother",
            genotype="heterozygous",
            affected=False,  # Asymptomatic carrier!
            age=45,
            sex="female",
            phenotypes=[]
        ),
        Individual(
            id="father",
            genotype="wild-type",
            affected=False,
            age=47,
            sex="male",
            phenotypes=[]
        )
    ]
)
```

**Benefits:**
- ✅ Detailed demographics (age, sex, age at onset)
- ✅ Individual-level analysis
- ✅ Can track unaffected carriers explicitly
- ✅ Useful for penetrance calculations with individual characteristics
- ✅ Captures family relationships

## Quick Start Guide

### Option 1: Unified Extractor (Recommended)

The `UnifiedExtractor` **automatically** determines which method to use based on the paper:

```python
from genephenextract import UnifiedExtractor, ClaudeExtractor

extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())

# Automatically extracts cohort OR individual data
result = extractor.extract(text, pmid="12345678", gene="KCNH2")

# Check which type was extracted
if isinstance(result, CohortData):
    print(f"Cohort: {result.total_carriers} carriers")
    for pc in result.phenotype_counts:
        print(f"  {pc.phenotype}: {pc.affected_count} affected")

elif isinstance(result, FamilyStudy):
    print(f"Family: {len(result.individuals)} individuals")
    for ind in result.individuals:
        print(f"  {ind.individual_id}: {ind.genotype}, affected={ind.affected}")
```

### Option 2: Extract All Data for a Gene

Extract from multiple papers automatically:

```python
from genephenextract import extract_gene_data, UnifiedExtractor, ClaudeExtractor

extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())

# Returns BOTH databases
cohort_db, individual_db = extract_gene_data(
    gene="KCNH2",
    extractor=extractor,
    max_papers=50,
    date_range=(2020, 2024)
)

# Analyze cohort data
summary = cohort_db.get_summary(genotype="heterozygous")
print(f"Cohort studies: {summary['total_cohorts']}")
print(f"Total carriers: {summary['total_carriers']}")

# Analyze individual data
print(f"\nFamily studies: {len(individual_db.studies)}")
print(f"Affected carriers: {len(individual_db.get_affected_carriers())}")
print(f"Unaffected carriers: {len(individual_db.get_unaffected_carriers())}")
```

## Data Models

### Cohort Models

```python
@dataclass
class PhenotypeCount:
    """Count of patients with a phenotype in a cohort."""
    phenotype: str
    affected_count: int
    notes: Optional[str] = None

    def get_unaffected_count(self, total_carriers: int) -> int:
        """Calculate unaffected: total_carriers - affected_count"""
        return total_carriers - self.affected_count


@dataclass
class CohortData:
    """Aggregate data from a cohort study."""
    pmid: str
    gene: str
    genotype: str  # heterozygous, homozygous, compound_heterozygous
    total_carriers: int
    phenotype_counts: List[PhenotypeCount]
    variant: Optional[str] = None  # None if multiple variants
    population: Optional[str] = None
    notes: Optional[str] = None

    def calculate_frequency(self, phenotype: str) -> float:
        """Calculate phenotype frequency in this cohort."""
        affected = self.get_affected_count(phenotype)
        return affected / self.total_carriers


class GeneticCohortDatabase:
    """Database aggregating cohort data across multiple studies."""

    def get_aggregate_phenotype_counts(
        self,
        phenotype: str,
        genotype: Optional[str] = None
    ) -> tuple[int, int]:
        """Get (affected_count, total_carriers) across all cohorts."""

    def calculate_aggregate_frequency(
        self,
        phenotype: str,
        genotype: Optional[str] = None
    ) -> float:
        """Calculate frequency across all studies."""
```

### Individual Models

```python
@dataclass
class Individual:
    """A single individual with genotype and phenotype data."""
    individual_id: str  # "proband", "II-3", "patient 1"
    pmid: str
    gene: str
    genotype: str  # heterozygous, homozygous, compound_heterozygous, wild-type
    affected: Optional[bool] = None  # True = has phenotype, False = asymptomatic
    phenotypes: List[str] = field(default_factory=list)
    variant: Optional[str] = None
    age: Optional[float] = None
    sex: Optional[str] = None
    age_at_onset: Optional[float] = None
    age_at_diagnosis: Optional[float] = None
    relation: Optional[str] = None
    notes: Optional[str] = None

    def is_carrier(self) -> bool:
        """Check if individual carries variant."""
        return self.genotype in ["heterozygous", "homozygous", "compound_heterozygous"]

    def is_affected_carrier(self) -> bool:
        """Carrier WITH phenotype."""
        return self.is_carrier() and self.affected is True

    def is_unaffected_carrier(self) -> bool:
        """Carrier WITHOUT phenotype (asymptomatic)."""
        return self.is_carrier() and self.affected is False


@dataclass
class FamilyStudy:
    """A family or cohort study with multiple individuals."""
    pmid: str
    gene: str
    variant: str
    individuals: List[Individual]

    def get_affected_carriers(self) -> List[Individual]:
        """Get all carriers with phenotypes."""

    def get_unaffected_carriers(self) -> List[Individual]:
        """Get all asymptomatic carriers."""


class VariantPenetranceDatabase:
    """Database aggregating individual data across multiple studies."""

    def get_affected_carriers(
        self,
        phenotype: Optional[str] = None
    ) -> List[Individual]:
        """Get all affected carriers (optionally filtered by phenotype)."""

    def get_unaffected_carriers(
        self,
        genotype: Optional[str] = None
    ) -> List[Individual]:
        """Get all unaffected carriers."""
```

## Combining Both Methods

You can analyze cohort and individual data together:

```python
# Extract both types
cohort_db, individual_db = extract_gene_data(gene="KCNH2", ...)

phenotype = "long QT syndrome"
genotype = "heterozygous"

# Get counts from cohort studies
cohort_affected, cohort_total = cohort_db.get_aggregate_phenotype_counts(
    phenotype=phenotype,
    genotype=genotype
)

# Get counts from individual studies
individual_affected = len(individual_db.get_affected_carriers(phenotype))
individual_total = len(individual_db.get_all_carriers())

# Combined analysis
total_affected = cohort_affected + individual_affected
total_carriers = cohort_total + individual_total
frequency = total_affected / total_carriers

print(f"Overall frequency: {frequency:.1%}")
print(f"  From {len(cohort_db.cohorts)} cohort studies: {cohort_affected}/{cohort_total}")
print(f"  From {len(individual_db.studies)} family studies: {individual_affected}/{individual_total}")
```

## Export Options

### Cohort Data

```python
# Export to JSON
cohort_db.export_to_json("cohort_data.json")

# Get summary statistics
summary = cohort_db.get_summary(genotype="heterozygous")
```

### Individual Data

```python
# Export to CSV (one row per individual)
individual_db.export_to_csv("individual_data.csv")

# Export to JSON (preserves all details)
individual_db.export_to_json("individual_data.json")
```

## Best Practices

### 1. Start with Unified Extractor

The `UnifiedExtractor` automatically determines the appropriate method:

```python
extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())
result = extractor.extract(text, pmid, gene)
```

### 2. Use Both Databases Together

Most analyses benefit from combining both types:

```python
cohort_db, individual_db = extract_gene_data(gene="KCNH2", ...)

# Cohort data gives you large-scale counts
# Individual data gives you detailed characteristics
```

### 3. Filter by Genotype

Focus on specific genotypes:

```python
# Cohort data
het_cohorts = cohort_db.filter_by_genotype("heterozygous")

# Individual data
het_carriers = [ind for ind in individual_db.get_all_carriers()
                if ind.genotype == "heterozygous"]
```

### 4. Calculate Frequencies

```python
# From cohort data (simple)
frequency = cohort_db.calculate_aggregate_frequency(
    phenotype="long QT syndrome",
    genotype="heterozygous"
)

# From individual data (with demographics)
het_carriers = [ind for ind in individual_db.get_all_carriers()
                if ind.genotype == "heterozygous"]
affected = [ind for ind in het_carriers if ind.affected]
frequency = len(affected) / len(het_carriers)

# Can also analyze by age, sex, etc.
young_carriers = [ind for ind in het_carriers if ind.age and ind.age < 30]
```

## Examples

See [examples/unified_extraction_example.py](../examples/unified_extraction_example.py) for comprehensive examples including:

1. Cohort-level extraction
2. Individual-level extraction
3. Comprehensive gene extraction
4. Combined analysis
5. Data export

## Schema

The unified extraction uses [schema/unified_extraction_schema.json](../src/genephenextract/schema/unified_extraction_schema.json), which supports both extraction types in a single schema.
