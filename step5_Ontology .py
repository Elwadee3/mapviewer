import pandas as pd
import logging
import re
from pathlib import Path
from tqdm import tqdm
from typing import Dict, Set
from owlready2 import *


# ============================================================
# STEP 5: OWL-BASED ONTOLOGY SEMANTIC REFINEMENT
# ============================================================
# This version replaces the old dictionary/Jaccard ontology logic.
# It loads the cybersecurity ontology from an actual OWL file:
# data/cybersecurity_ontology.owl
#
# Final Score Formula:
# Final Score = (Hybrid Score * 0.6) + (Ontology Score * 0.4)
# ============================================================


class OWLOntologyRefiner:
    def __init__(self, ontology_path: str):
        self.ontology_path = ontology_path

        if not Path(ontology_path).exists():
            raise FileNotFoundError(f"OWL ontology file not found: {ontology_path}")

        # Load formal OWL ontology
        self.onto = get_ontology(ontology_path).load()

        # Extract OWL relationships into Python structures for scoring
        self.domain_keywords = self._load_domain_keywords()
        self.semantic_bridges = self._load_semantic_bridges()

    def _load_domain_keywords(self) -> Dict[str, Set[str]]:
        """
        Reads cybersecurity domain-keyword relationships from the OWL ontology.

        Expected OWL object property:
        - hasKeyword

        Example:
        GOVERNANCE hasKeyword policy
        ACCESS_CONTROL hasKeyword authentication
        """
        domain_keywords = {}

        for individual in self.onto.individuals():
            if hasattr(individual, "hasKeyword") and individual.hasKeyword:
                domain_name = individual.name.upper()
                keywords = {
                    keyword.name.lower().replace("_", " ")
                    for keyword in individual.hasKeyword
                }

                domain_keywords[domain_name] = keywords

        return domain_keywords

    def _load_semantic_bridges(self) -> Dict[str, Set[str]]:
        """
        Reads semantic relationships between cybersecurity domains from the OWL ontology.

        Expected OWL object property:
        - relatedTo

        Example:
        GOVERNANCE relatedTo RISK_MGMT
        ACCESS_CONTROL relatedTo NETWORK_SEC
        """
        bridges = {}

        for individual in self.onto.individuals():
            if hasattr(individual, "relatedTo") and individual.relatedTo:
                domain_name = individual.name.upper()
                related_domains = {
                    related.name.upper()
                    for related in individual.relatedTo
                }

                bridges[domain_name] = related_domains

        return bridges

    def get_domain_keywords(self, text: str) -> Dict[str, Set[str]]:
        """
        Identifies which OWL ontology domains and keywords are reflected in a text.
        """
        text = str(text).lower()
        results = {}

        for domain, keywords in self.domain_keywords.items():
            matched_keywords = {
                keyword
                for keyword in keywords
                if re.search(rf"\b{re.escape(keyword)}\b", text)
            }

            if matched_keywords:
                results[domain] = matched_keywords

        return results

    def compute_ontology_score(self, source_text: str, target_text: str) -> float:
        """
        Computes the ontology score using OWL-defined cybersecurity domains,
        OWL keywords, and OWL semantic relationships.

        Scoring logic:
        - 0.45 if no ontology concepts are found in source or target text
        - 0.70 to 1.00 if both texts belong to the same OWL cybersecurity domain
        - 0.60 if the domains are semantically related through OWL relatedTo
        - 0.20 if the domains are unrelated
        """
        source_map = self.get_domain_keywords(source_text)
        target_map = self.get_domain_keywords(target_text)

        # Case 1: No ontology concepts detected in one or both texts
        if not source_map or not target_map:
            return 0.45

        source_domains = set(source_map.keys())
        target_domains = set(target_map.keys())

        # Case 2: Direct OWL domain match
        common_domains = source_domains.intersection(target_domains)

        if common_domains:
            source_keywords = set().union(*source_map.values())
            target_keywords = set().union(*target_map.values())

            keyword_overlap = source_keywords.intersection(target_keywords)
            total_keywords = source_keywords.union(target_keywords)

            if not total_keywords:
                return 0.70

            overlap_ratio = len(keyword_overlap) / len(total_keywords)

            # Same OWL domain = strong semantic match
            return round(0.70 + (0.30 * overlap_ratio), 4)

        # Case 3: Related OWL domains through relatedTo property
        for source_domain in source_domains:
            related_domains = self.semantic_bridges.get(source_domain, set())

            if related_domains.intersection(target_domains):
                return 0.60

        # Case 4: Ontology domain mismatch
        return 0.20


# ============================================================
# LOGGER SETUP
# ============================================================

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


# ============================================================
# MAIN PROCESSING PIPELINE
# ============================================================

def run_ontology_step(
    input_path: str,
    output_path: str,
    ontology_path: str,
    k: int = 10
):
    logger = setup_logger()

    logger.info("=" * 70)
    logger.info("STEP 5: OWL-BASED ONTOLOGY SEMANTIC REFINEMENT")
    logger.info("=" * 70)
    logger.info(f"Loading Step 4 mapping results from: {input_path}")
    logger.info(f"Loading OWL ontology from: {ontology_path}")

    if not Path(input_path).exists():
        logger.error(f"Input file not found: {input_path}")
        return

    if not Path(ontology_path).exists():
        logger.error(f"OWL ontology file not found: {ontology_path}")
        return

    df = pd.read_csv(input_path)

    refiner = OWLOntologyRefiner(ontology_path)

    logger.info(f"Loaded {len(refiner.domain_keywords)} OWL cybersecurity domains.")
    logger.info(f"Loaded {len(refiner.semantic_bridges)} OWL semantic relationship groups.")

    final_data = []

    for _, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc="Processing OWL Ontology Scores"
    ):

        refined_row = {
            "ECC id control": row["control_ref"],
            "Source Text": row["control_text"]
        }

        for i in range(1, k + 1):
            target_ref = row.get(f"mapping_{i}_ref")
            target_text = row.get(f"mapping_{i}_text")
            hybrid_score = row.get(f"hybrid_score_{i}", 0)

            if pd.isna(target_ref):
                continue

            if pd.isna(target_text):
                target_text = ""

            if pd.isna(hybrid_score):
                hybrid_score = 0

            # OWL-based ontology scoring
            ontology_score = refiner.compute_ontology_score(
                row["control_text"],
                target_text
            )

            # Doctor's required formula:
            # Final Score = 60% Hybrid Score + 40% Ontology Score
            final_score = (float(hybrid_score) * 0.6) + (ontology_score * 0.4)

            # Confidence label
            if final_score >= 0.80:
                confidence_label = "High Match"
            elif final_score >= 0.60:
                confidence_label = "Medium Match"
            else:
                confidence_label = "Low Match"

            suffix = f" {i}" if i > 1 else ""
            prefix = f"NIST mapping{suffix}"

            refined_row.update({
                f"{prefix}": target_ref,
                f"Text{suffix}": target_text,
                f"Dense{suffix}": round(row.get(f"dense_score_{i}", 0), 4),
                f"Sparse{suffix}": round(row.get(f"sparse_score_{i}", 0), 4),
                f"Hybrid{suffix}": round(float(hybrid_score), 4),
                f"Ontology score{suffix}": ontology_score,
                f"Final Score{suffix}": round(final_score, 4),
                f"Confidence match{suffix}": confidence_label
            })

        final_data.append(refined_row)

    output_df = pd.DataFrame(final_data)
    output_df.to_csv(output_path, index=False)

    logger.info(f"Success! OWL-based ontology output saved to: {output_path}")


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    MAPPING_INPUT = "data/source_to_target_mappings.csv"
    MAPPING_OUTPUT = "data/final_owl_ontology_refined_mappings.csv"
    OWL_ONTOLOGY_PATH = "data/cybersecurity_ontology.owl"

    run_ontology_step(
        input_path=MAPPING_INPUT,
        output_path=MAPPING_OUTPUT,
        ontology_path=OWL_ONTOLOGY_PATH,
        k=10
    )