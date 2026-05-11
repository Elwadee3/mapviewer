#!/usr/bin/env python3
"""Step 1.5: Add Definitions and Synonyms - Bidirectional Enrichment"""

import pandas as pd
from pathlib import Path
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


# Flat list approach: each list is a group of synonyms
# If ANY word in the group is found, add ALL OTHER words from that group
SYNONYM_GROUPS = [
     ["cybersecurity", "information security"],
    ["entity", "organization"],

    ["strategy", "policy", "objectives", "strategic direction",
     "leadership and commitment", "integration",
     "continuing suitability, adequacy and effectiveness"],

    ["identified, documented, and approved", "established"],
    ["developed", "managed", "performed"],

    ["legislative and regulatory requirements",
     "legal and regulatory requirements",
     "Legal, statutory, regulatory and contractual requirements",
     "interested parties requirements"],

    ["periodically", "regularly", "at planned intervals"],

    ["periodically reviewed", "reviewed",
     "reviewed at planned", "reviewed and updated"],

    ["head of the entity", "top management",
     "authorized official", "internal and external stakeholders"],

    ["in line with", "compatible"],

    ["department for cybersecurity", "responsibility and authority"],

    ["information and technology assets", "inventory",
     "technology assets", "information resources"],

    ["archiving and backup", "backup copies"],

    ["qualified saudi cybersecurity professionals", "adequate resources"],

    ["risk methodology and procedures", "standardized risk method"],

    ["continuity", "availability", "data accessibility"],

    ["response plans", "responses"],

    ["disaster recovery", "restoration"],

    ["asset inventory", "asset identification"],

    ["asset classification", "asset categorization", "data classification"],

    ["ownership assignment", "asset accountability"],

    ["identity management", "identity governance"],

    ["access control", "authorization control"],

    ["multi-factor authentication", "strong authentication"],

    ["least privilege", "minimal access rights"],

    ["segregation of duties", "role-based access control"],

    ["confidentiality", "data privacy"],

    ["integrity", "data integrity protection"],

    ["data protection controls", "data security safeguards"],

    ["vulnerability scanning", "threat and vulnerability identification"],

    ["risk classification", "risk analysis"],

    ["remediation plan", "risk treatment plan"],

    ["incident response", "incident handling"],

    ["threat detection", "event monitoring"],

    ["escalation procedure", "incident coordination"],

    ["containment measures", "mitigation actions"]

]


def build_term_lookup() -> list:
    """Build lookup as list of (term, related_terms) sorted by term length descending.
    This ensures longer phrases match before shorter ones."""
    lookup = {}
    for group in SYNONYM_GROUPS:
        for term in group:
            term_lower = term.lower()
            others = [t for t in group if t.lower() != term_lower]
            if term_lower not in lookup:
                lookup[term_lower] = others
            else:
                lookup[term_lower] = list(set(lookup[term_lower] + others))
    # Sort by term length descending - longer terms first
    return sorted(lookup.items(), key=lambda x: len(x[0]), reverse=True)


TERM_LOOKUP = build_term_lookup()


def enrich_text(text: str) -> tuple:
    """
    Enrich text by finding any synonym and adding all related terms.

    Returns: (enriched_text, found_terms_dict)
    """
    found_terms = {}
    replacements = []  # (start, end, matched_text, related_terms)
    text_lower = text.lower()

    # Track which groups we've already matched (to avoid duplicate enrichment)
    matched_positions = set()

    for term, related_terms in TERM_LOOKUP:
        if not related_terms:
            continue

        # Search with word boundaries
        pattern = r'\b' + re.escape(term) + r'\b'

        for match in re.finditer(pattern, text_lower):
            start, end = match.start(), match.end()

            # Skip if this position overlaps with an already matched term
            if any(start < mp_end and end > mp_start for mp_start, mp_end in matched_positions):
                continue

            matched_text = text[start:end]  # Preserve original case
            matched_positions.add((start, end))

            found_terms[term] = {
                "matched": matched_text,
                "related": related_terms
            }

            # Add ALL occurrences
            replacements.append((start, end, matched_text, related_terms[:4]))

    # Apply replacements in reverse order
    enriched_text = text
    replacements.sort(key=lambda x: x[0], reverse=True)

    for start, end, matched_text, related in replacements:
        related_str = "/".join(related)
        replacement = f"{matched_text} ({related_str})"
        enriched_text = enriched_text[:start] + replacement + enriched_text[end:]

    return enriched_text, found_terms


def add_definitions_to_dataframe(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """Add definitions and synonyms to all controls in a dataframe."""
    logger.info(f"Enriching {dataset_name}...")

    total_terms = 0
    controls_enriched = 0
    sample = None

    for idx, row in df.iterrows():
        original = row['control_text']
        enriched, found = enrich_text(original)
        df.at[idx, 'control_text'] = enriched

        if found:
            total_terms += len(found)
            controls_enriched += 1
            if sample is None:
                sample = (row['control_ref'], list(found.keys())[:5], original[:80], enriched[:80])

    logger.info(f"✓ Enriched {len(df)} controls")
    logger.info(f"  Controls with matches: {controls_enriched}")
    logger.info(f"  Total terms enriched: {total_terms}")

    if sample:
        logger.info(f"\nSample ({sample[0]}):")
        logger.info(f"  Terms: {sample[1]}")
        logger.info(f"  Before: {sample[2]}...")
        logger.info(f"  After:  {sample[3]}...")

    return df


def main():
    source_csv = "data/validated_source.csv"
    target_csv = "data/validated_target.csv"
    output_dir = Path("data")

    logger.info("=" * 60)
    logger.info("STEP 1.5: ADD DEFINITIONS AND SYNONYMS")
    logger.info("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    logger.info("\nLoading validated data...")
    source_df = pd.read_csv(source_csv)
    target_df = pd.read_csv(target_csv)
    logger.info(f"✓ Loaded {len(source_df)} source, {len(target_df)} target controls")

    # Enrich source
    logger.info("\n" + "-" * 60)
    logger.info("ENRICHING SOURCE")
    logger.info("-" * 60)
    source_df = add_definitions_to_dataframe(source_df, "source")

    # Enrich target
    logger.info("\n" + "-" * 60)
    logger.info("ENRICHING TARGET")
    logger.info("-" * 60)
    target_df = add_definitions_to_dataframe(target_df, "target")

    # Save
    source_df[['control_ref', 'control_text']].to_csv(output_dir / "enriched_source.csv", index=False)
    target_df[['control_ref', 'control_text']].to_csv(output_dir / "enriched_target.csv", index=False)

    logger.info(f"\n✓ Saved: data/enriched_source.csv, data/enriched_target.csv")
    print("\n✓ Step 1.5 completed!")


if __name__ == "__main__":
    main()
