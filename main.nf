#!/usr/bin/env nextflow

/*
 * GenePhenExtract Nextflow Pipeline
 *
 * Extract genotype-phenotype associations from PubMed literature using LLMs.
 * Supports both cohort-level (aggregate counts) and individual-level (detailed pedigrees) data.
 */

nextflow.enable.dsl=2

// Print pipeline information
log.info """\
    =========================================
    G E N E P H E N E X T R A C T
    =========================================
    genes           : ${params.genes}
    max papers      : ${params.max_papers_per_gene}
    date range      : ${params.date_range_start}-${params.date_range_end}
    LLM provider    : ${params.llm_provider}
    output dir      : ${params.outdir}
    =========================================
    """
    .stripIndent()

/*
 * Process 1: Search PubMed for each gene
 * Input: Gene name
 * Output: List of PMIDs for that gene
 */
process SEARCH_PUBMED {
    tag "$gene"
    publishDir "${params.outdir}/pubmed_searches", mode: params.publish_mode

    input:
    val gene

    output:
    tuple val(gene), path("${gene}_pmids.txt"), emit: pmids
    path "${gene}_search_stats.json", emit: stats

    script:
    """
    #!/usr/bin/env python3
    import json
    from genephenextract import PubMedClient

    # Search PubMed
    client = PubMedClient()
    query = f"{gene}[Gene] AND (variant OR mutation OR genotype)"

    # Add date range
    query += f" AND ${params.date_range_start}:${params.date_range_end}[PDAT]"

    # Search
    pmids = client.search(query, max_results=${params.max_papers_per_gene})

    # Write PMIDs to file (one per line)
    with open("${gene}_pmids.txt", "w") as f:
        for pmid in pmids:
            f.write(f"{pmid}\\n")

    # Write statistics
    stats = {
        "gene": "${gene}",
        "query": query,
        "total_results": len(pmids),
        "max_requested": ${params.max_papers_per_gene}
    }
    with open("${gene}_search_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Found {len(pmids)} papers for ${gene}")
    """
}

/*
 * Process 2: Fetch paper details for each PMID
 * Input: Gene name and PMID
 * Output: Paper text (abstract or full-text)
 */
process FETCH_PAPERS {
    tag "$gene-$pmid"
    publishDir "${params.outdir}/papers/${gene}", mode: params.publish_mode

    input:
    tuple val(gene), val(pmid)

    output:
    tuple val(gene), val(pmid), path("${pmid}_text.txt"), emit: paper_text
    path "${pmid}_metadata.json", emit: metadata optional true

    script:
    """
    #!/usr/bin/env python3
    import json
    from genephenextract import PubMedClient

    client = PubMedClient()

    # Fetch paper details
    details = client.fetch_details(["${pmid}"])

    if not details:
        print(f"No details found for PMID ${pmid}")
        # Create empty file so process doesn't fail
        with open("${pmid}_text.txt", "w") as f:
            f.write("")
        exit(0)

    paper = details[0]

    # Try to get full text if enabled
    text = ""
    if ${params.use_full_text}:
        try:
            full_text = client.fetch_full_text("${pmid}")
            if full_text:
                text = full_text
        except:
            pass

    # Fall back to abstract if no full text
    if not text:
        text = paper.get("abstract", "")

    # Write text
    with open("${pmid}_text.txt", "w") as f:
        f.write(text)

    # Write metadata
    metadata = {
        "pmid": "${pmid}",
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "journal": paper.get("journal", ""),
        "pub_date": paper.get("pub_date", ""),
        "text_length": len(text),
        "text_type": "full_text" if text != paper.get("abstract", "") else "abstract"
    }
    with open("${pmid}_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Fetched {metadata['text_type']} for PMID ${pmid} ({len(text)} chars)")
    """
}

/*
 * Process 3: Extract genotype-phenotype data using LLM
 * Input: Gene, PMID, and paper text
 * Output: Extracted data (cohort or individual)
 */
process EXTRACT_DATA {
    tag "$gene-$pmid"
    publishDir "${params.outdir}/extractions/${gene}", mode: params.publish_mode

    input:
    tuple val(gene), val(pmid), path(text_file)

    output:
    tuple val(gene), path("${pmid}_extraction.json"), emit: extraction
    path "${pmid}_extraction_log.json", emit: log

    script:
    def llm_config = params.llm_provider == 'claude' ? "ClaudeExtractor()" :
                     params.llm_provider == 'openai' ? "OpenAIExtractor()" :
                     params.llm_provider == 'gemini' ? "GeminiExtractor()" :
                     "MockExtractor()"

    """
    #!/usr/bin/env python3
    import json
    import time
    from genephenextract import (
        UnifiedExtractor,
        ${params.llm_provider == 'claude' ? 'ClaudeExtractor' :
          params.llm_provider == 'openai' ? 'OpenAIExtractor' :
          params.llm_provider == 'gemini' ? 'GeminiExtractor' : 'MockExtractor'},
        CohortData,
        FamilyStudy
    )

    # Read paper text
    with open("${text_file}", "r") as f:
        text = f.read()

    if not text.strip():
        print("Empty text, skipping extraction")
        with open("${pmid}_extraction.json", "w") as f:
            json.dump({"error": "empty_text"}, f)
        with open("${pmid}_extraction_log.json", "w") as f:
            json.dump({"pmid": "${pmid}", "status": "skipped", "reason": "empty_text"}, f)
        exit(0)

    # Create extractor
    start_time = time.time()
    try:
        llm_extractor = ${llm_config}
        extractor = UnifiedExtractor(llm_extractor=llm_extractor)

        # Extract data
        result = extractor.extract(text, pmid="${pmid}", gene="${gene}")

        # Convert to dict
        extraction_data = {
            "pmid": "${pmid}",
            "gene": "${gene}",
            "extraction_type": None,
            "data": None
        }

        if isinstance(result, CohortData):
            extraction_data["extraction_type"] = "cohort"
            extraction_data["data"] = result.to_dict()
        elif isinstance(result, FamilyStudy):
            extraction_data["extraction_type"] = "individual"
            extraction_data["data"] = {
                "pmid": result.pmid,
                "gene": result.gene,
                "variant": result.variant,
                "individuals": [
                    {
                        "id": ind.individual_id,
                        "genotype": ind.genotype,
                        "affected": ind.affected,
                        "phenotypes": [p.phenotype for p in ind.phenotypes],
                        "age": ind.age,
                        "sex": ind.sex,
                        "age_at_onset": ind.age_at_onset,
                        "age_at_diagnosis": ind.age_at_diagnosis,
                        "relation": ind.relation
                    }
                    for ind in result.individuals
                ]
            }
        elif isinstance(result, list):
            # Multiple cohorts
            extraction_data["extraction_type"] = "multiple_cohorts"
            extraction_data["data"] = [r.to_dict() for r in result if isinstance(r, CohortData)]

        # Write extraction
        with open("${pmid}_extraction.json", "w") as f:
            json.dump(extraction_data, f, indent=2)

        # Write log
        log_data = {
            "pmid": "${pmid}",
            "gene": "${gene}",
            "status": "success",
            "extraction_type": extraction_data["extraction_type"],
            "duration_seconds": time.time() - start_time,
            "text_length": len(text)
        }
        with open("${pmid}_extraction_log.json", "w") as f:
            json.dump(log_data, f, indent=2)

        print(f"Successfully extracted {extraction_data['extraction_type']} data from PMID ${pmid}")

    except Exception as e:
        # Log error but don't fail
        error_data = {
            "pmid": "${pmid}",
            "error": str(e),
            "error_type": type(e).__name__
        }
        with open("${pmid}_extraction.json", "w") as f:
            json.dump(error_data, f)

        log_data = {
            "pmid": "${pmid}",
            "gene": "${gene}",
            "status": "error",
            "error": str(e),
            "duration_seconds": time.time() - start_time
        }
        with open("${pmid}_extraction_log.json", "w") as f:
            json.dump(log_data, f, indent=2)

        print(f"Error extracting from PMID ${pmid}: {e}")
    """
}

/*
 * Process 4: Aggregate extractions by gene
 * Input: All extractions for a gene
 * Output: Combined cohort and individual databases
 */
process AGGREGATE_BY_GENE {
    tag "$gene"
    publishDir "${params.outdir}/aggregated", mode: params.publish_mode

    input:
    tuple val(gene), path(extractions)

    output:
    tuple val(gene), path("${gene}_cohort_data.json"), path("${gene}_individual_data.json"), emit: databases
    path "${gene}_summary.json", emit: summary

    script:
    """
    #!/usr/bin/env python3
    import json
    import glob
    from genephenextract import (
        GeneticCohortDatabase,
        VariantPenetranceDatabase,
        CohortData,
        FamilyStudy,
        Individual,
        PhenotypeCount,
        PhenotypeObservation
    )

    # Initialize databases
    cohort_db = GeneticCohortDatabase(gene="${gene}")
    individual_db = VariantPenetranceDatabase()

    # Load all extractions
    extraction_files = glob.glob("*_extraction.json")

    cohort_count = 0
    individual_count = 0
    error_count = 0

    for filepath in extraction_files:
        with open(filepath) as f:
            data = json.load(f)

        if "error" in data:
            error_count += 1
            continue

        extraction_type = data.get("extraction_type")
        extraction_data = data.get("data")

        if not extraction_data:
            continue

        # Process cohort data
        if extraction_type == "cohort":
            cohort = CohortData(
                pmid=extraction_data["pmid"],
                gene=extraction_data["gene"],
                variant=extraction_data.get("variant"),
                genotype=extraction_data["genotype"],
                total_carriers=extraction_data["total_carriers"],
                phenotype_counts=[
                    PhenotypeCount(
                        phenotype=pc["phenotype"],
                        affected_count=pc["affected_count"],
                        notes=pc.get("notes")
                    )
                    for pc in extraction_data.get("phenotype_counts", [])
                ],
                population=extraction_data.get("population"),
                notes=extraction_data.get("notes")
            )
            cohort_db.add_cohort(cohort)
            cohort_count += 1

        # Process individual data
        elif extraction_type == "individual":
            individuals = [
                Individual(
                    individual_id=ind["id"],
                    pmid=extraction_data["pmid"],
                    gene=extraction_data["gene"],
                    variant=ind.get("variant") or extraction_data.get("variant"),
                    genotype=ind["genotype"],
                    affected=ind.get("affected"),
                    phenotypes=[
                        PhenotypeObservation(phenotype=p)
                        for p in ind.get("phenotypes", [])
                    ],
                    age=ind.get("age"),
                    sex=ind.get("sex"),
                    age_at_onset=ind.get("age_at_onset"),
                    age_at_diagnosis=ind.get("age_at_diagnosis"),
                    relation=ind.get("relation")
                )
                for ind in extraction_data.get("individuals", [])
            ]

            study = FamilyStudy(
                pmid=extraction_data["pmid"],
                gene=extraction_data["gene"],
                variant=extraction_data.get("variant", "unknown"),
                individuals=individuals
            )
            individual_db.add_study(study)
            individual_count += 1

        # Process multiple cohorts
        elif extraction_type == "multiple_cohorts":
            for cohort_data in extraction_data:
                cohort = CohortData(
                    pmid=cohort_data["pmid"],
                    gene=cohort_data["gene"],
                    variant=cohort_data.get("variant"),
                    genotype=cohort_data["genotype"],
                    total_carriers=cohort_data["total_carriers"],
                    phenotype_counts=[
                        PhenotypeCount(
                            phenotype=pc["phenotype"],
                            affected_count=pc["affected_count"],
                            notes=pc.get("notes")
                        )
                        for pc in cohort_data.get("phenotype_counts", [])
                    ],
                    population=cohort_data.get("population"),
                    notes=cohort_data.get("notes")
                )
                cohort_db.add_cohort(cohort)
                cohort_count += 1

    # Export databases
    cohort_db.export_to_json("${gene}_cohort_data.json")
    individual_db.export_to_json("${gene}_individual_data.json")

    # Create summary
    summary = {
        "gene": "${gene}",
        "total_extractions": len(extraction_files),
        "cohort_studies": cohort_count,
        "family_studies": individual_count,
        "errors": error_count,
        "cohort_summary": cohort_db.get_summary(genotype="heterozygous") if cohort_db.cohorts else None,
        "individual_summary": {
            "total_individuals": len(individual_db.get_all_individuals()),
            "total_carriers": len(individual_db.get_all_carriers()),
            "affected_carriers": len(individual_db.get_affected_carriers()),
            "unaffected_carriers": len(individual_db.get_unaffected_carriers())
        } if individual_db.studies else None
    }

    with open("${gene}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Aggregated data for ${gene}:")
    print(f"  Cohort studies: {cohort_count}")
    print(f"  Family studies: {individual_count}")
    print(f"  Errors: {error_count}")
    """
}

/*
 * Process 5: Create final combined report
 * Input: All gene summaries
 * Output: Combined report and datasets
 */
process CREATE_FINAL_REPORT {
    publishDir "${params.outdir}/final", mode: params.publish_mode

    input:
    path summaries
    path cohort_dbs
    path individual_dbs

    output:
    path "combined_cohort_data.csv", emit: cohort_csv
    path "combined_individual_data.csv", emit: individual_csv
    path "pipeline_report.html", emit: report
    path "summary_statistics.json", emit: stats

    script:
    """
    #!/usr/bin/env python3
    import json
    import glob
    import pandas as pd
    from pathlib import Path

    # Load all summaries
    summary_files = glob.glob("*_summary.json")
    all_summaries = []

    for filepath in summary_files:
        with open(filepath) as f:
            all_summaries.append(json.load(f))

    # Combine cohort data
    cohort_records = []
    for cohort_file in glob.glob("*_cohort_data.json"):
        with open(cohort_file) as f:
            data = json.load(f)
            for cohort in data.get("cohorts", []):
                for pc in cohort.get("phenotype_counts", []):
                    cohort_records.append({
                        "gene": cohort["gene"],
                        "pmid": cohort["pmid"],
                        "variant": cohort.get("variant"),
                        "genotype": cohort["genotype"],
                        "total_carriers": cohort["total_carriers"],
                        "phenotype": pc["phenotype"],
                        "affected_count": pc["affected_count"],
                        "unaffected_count": pc.get("unaffected_count"),
                        "population": cohort.get("population")
                    })

    if cohort_records:
        cohort_df = pd.DataFrame(cohort_records)
        cohort_df.to_csv("combined_cohort_data.csv", index=False)
    else:
        # Create empty file
        pd.DataFrame().to_csv("combined_cohort_data.csv", index=False)

    # Combine individual data
    individual_records = []
    for ind_file in glob.glob("*_individual_data.json"):
        with open(ind_file) as f:
            data = json.load(f)
            for study in data.get("studies", []):
                for ind in study.get("individuals", []):
                    individual_records.append({
                        "gene": study["gene"],
                        "pmid": study["pmid"],
                        "variant": study.get("variant"),
                        "individual_id": ind["individual_id"],
                        "genotype": ind["genotype"],
                        "affected": ind.get("affected"),
                        "phenotypes": "; ".join(ind.get("phenotypes", [])),
                        "age": ind.get("age"),
                        "sex": ind.get("sex"),
                        "age_at_onset": ind.get("age_at_onset"),
                        "age_at_diagnosis": ind.get("age_at_diagnosis"),
                        "relation": ind.get("relation")
                    })

    if individual_records:
        individual_df = pd.DataFrame(individual_records)
        individual_df.to_csv("combined_individual_data.csv", index=False)
    else:
        pd.DataFrame().to_csv("combined_individual_data.csv", index=False)

    # Create summary statistics
    stats = {
        "total_genes": len(all_summaries),
        "total_cohort_studies": sum(s.get("cohort_studies", 0) for s in all_summaries),
        "total_family_studies": sum(s.get("family_studies", 0) for s in all_summaries),
        "total_errors": sum(s.get("errors", 0) for s in all_summaries),
        "total_cohort_records": len(cohort_records),
        "total_individual_records": len(individual_records),
        "genes": [s["gene"] for s in all_summaries]
    }

    with open("summary_statistics.json", "w") as f:
        json.dump(stats, f, indent=2)

    # Create HTML report
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>GenePhenExtract Pipeline Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            .metric {{ background-color: #f2f2f2; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>GenePhenExtract Pipeline Report</h1>

        <div class="metric">
            <h2>Summary Statistics</h2>
            <p><strong>Total Genes Processed:</strong> {stats["total_genes"]}</p>
            <p><strong>Cohort Studies:</strong> {stats["total_cohort_studies"]}</p>
            <p><strong>Family Studies:</strong> {stats["total_family_studies"]}</p>
            <p><strong>Total Cohort Records:</strong> {stats["total_cohort_records"]}</p>
            <p><strong>Total Individual Records:</strong> {stats["total_individual_records"]}</p>
            <p><strong>Errors:</strong> {stats["total_errors"]}</p>
        </div>

        <h2>Per-Gene Results</h2>
        <table>
            <tr>
                <th>Gene</th>
                <th>Cohort Studies</th>
                <th>Family Studies</th>
                <th>Errors</th>
            </tr>
    '''

    for summary in all_summaries:
        html += f'''
            <tr>
                <td>{summary["gene"]}</td>
                <td>{summary.get("cohort_studies", 0)}</td>
                <td>{summary.get("family_studies", 0)}</td>
                <td>{summary.get("errors", 0)}</td>
            </tr>
        '''

    html += '''
        </table>

        <h2>Output Files</h2>
        <ul>
            <li><strong>combined_cohort_data.csv</strong> - All cohort-level data</li>
            <li><strong>combined_individual_data.csv</strong> - All individual-level data</li>
            <li><strong>summary_statistics.json</strong> - Detailed statistics</li>
        </ul>
    </body>
    </html>
    '''

    with open("pipeline_report.html", "w") as f:
        f.write(html)

    print("Final report created successfully!")
    print(f"Total genes: {stats['total_genes']}")
    print(f"Cohort records: {stats['total_cohort_records']}")
    print(f"Individual records: {stats['total_individual_records']}")
    """
}

/*
 * Main workflow
 */
workflow {
    // Read genes from input file
    genes_ch = Channel
        .fromPath(params.genes)
        .splitText()
        .map { it.trim() }
        .filter { it.length() > 0 }

    // Step 1: Search PubMed for each gene
    SEARCH_PUBMED(genes_ch)

    // Step 2: Split PMIDs and fetch papers
    pmids_ch = SEARCH_PUBMED.out.pmids
        .splitText()
        .map { line ->
            def parts = line.split('\t')
            if (parts.size() >= 2) {
                return tuple(parts[0], parts[1].trim())
            }
        }
        .filter { it != null }

    // Actually we need to parse the pmids file differently
    pmids_ch = SEARCH_PUBMED.out.pmids
        .flatMap { gene, pmid_file ->
            pmid_file.readLines()
                .findAll { it.trim() }
                .collect { pmid -> tuple(gene, pmid.trim()) }
        }

    FETCH_PAPERS(pmids_ch)

    // Step 3: Extract data from each paper
    EXTRACT_DATA(FETCH_PAPERS.out.paper_text)

    // Step 4: Group extractions by gene and aggregate
    extractions_by_gene = EXTRACT_DATA.out.extraction
        .groupTuple()

    AGGREGATE_BY_GENE(extractions_by_gene)

    // Step 5: Create final report
    all_summaries = AGGREGATE_BY_GENE.out.summary.collect()
    all_cohort_dbs = AGGREGATE_BY_GENE.out.databases.map { it[1] }.collect()
    all_individual_dbs = AGGREGATE_BY_GENE.out.databases.map { it[2] }.collect()

    CREATE_FINAL_REPORT(
        all_summaries,
        all_cohort_dbs,
        all_individual_dbs
    )
}

workflow.onComplete {
    log.info """\
        =========================================
        Pipeline execution summary
        =========================================
        Completed at : ${workflow.complete}
        Duration     : ${workflow.duration}
        Success      : ${workflow.success}
        Work Dir     : ${workflow.workDir}
        Exit status  : ${workflow.exitStatus}
        =========================================
        """
        .stripIndent()
}
