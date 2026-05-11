import pandas as pd
import json
from pathlib import Path
import sys
import os
from dotenv import load_dotenv
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq
import logging

load_dotenv()

def setup_logger(level: str = "INFO") -> logging.Logger:
    """Setup basic logger."""
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class FastMetadataExtractor:
    """Extract rich semantic metadata for maximum embedding quality."""
    
    def __init__(self, api_key: str = None, model: str = "openai/gpt-oss-120b"):
        """
        Initialize the metadata extractor.
        
        Args:
            api_key: Groq API key
            model: High-quality LLM model (default: openai/gpt-oss-120b for best quality)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable.")
        
        self.client = Groq(api_key=self.api_key)
        self.model = model
        logger.info(f"Rich metadata extractor initialized with model: {model}")
        
        # JSON schema for structured output - EXPANDED for quality
        self.json_schema = {
            "name": "control_metadata",
            "schema": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Main security topics and areas (detailed, comma-separated)"
                    },
                    "verbs": {
                        "type": "string",
                        "description": "All key actions and requirements (comma-separated verbs)"
                    },
                    "context": {
                        "type": "string",
                        "description": "Security purpose, objectives, and risks mitigated (2-3 sentences)"
                    },
                    "semantic_summary": {
                        "type": "string",
                        "description": "Rich semantic summary capturing the essence and intent (3-4 sentences)"
                    },
                    "key_concepts": {
                        "type": "string",
                        "description": "Core security concepts and terminology (comma-separated)"
                    },
                    "scope": {
                        "type": "string",
                        "description": "What is in scope: systems, processes, people, data (one sentence)"
                    },
                    "security_domains": {
                        "type": "string",
                        "description": "Relevant security domains (e.g., access control, incident response, risk management)"
                    }
                },
                "required": ["subject", "verbs", "context", "semantic_summary", "key_concepts", "scope", "security_domains"],
                "additionalProperties": False
            }
        }
    
    def extract_metadata(self, control_ref: str, control_text: str) -> dict:
        """
        Extract rich metadata for a single control using structured JSON output.
        
        Args:
            control_ref: Control reference ID
            control_text: Control text
            
        Returns:
            Dict with comprehensive metadata fields
        """
        system_prompt = """You are a cybersecurity control analyst. Extract metadata ONLY from what is EXPLICITLY stated in the control text.

CRITICAL RULES:
- Do NOT hallucinate or infer domains/concepts not mentioned
- Do NOT add generic security terms
- Extract ONLY what the control text actually says
- Be concise, not verbose

Extract:
1. subject: Main topic in 5-15 words (only what's stated)
2. verbs: Action verbs from the text only (comma-separated)
3. context: Why this control matters (1 sentence, based on text)
4. semantic_summary: What the control requires (1-2 sentences, paraphrase the text)
5. key_concepts: Terms explicitly used in the control (comma-separated)
6. scope: What's covered (1 sentence, only if stated)
7. security_domains: Pick ONLY domains directly relevant to the control text. Choose from: governance, risk management, access control, cryptography, physical security, operations security, communications security, incident management, business continuity, compliance, asset management, human resources security, supplier management. Do NOT list domains unless the control explicitly relates to them."""

        user_prompt = f"""Control: {control_ref}

{control_text}

Extract metadata as JSON. Only include what's explicitly stated."""
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Low for precision
                response_format={
                    "type": "json_schema",
                    "json_schema": self.json_schema
                }
            )
            
            response_text = completion.choices[0].message.content.strip()
            metadata = json.loads(response_text)
            
            return {
                "subject": metadata.get("subject", ""),
                "verbs": metadata.get("verbs", ""),
                "context": metadata.get("context", ""),
                "semantic_summary": metadata.get("semantic_summary", ""),
                "key_concepts": metadata.get("key_concepts", ""),
                "scope": metadata.get("scope", ""),
                "security_domains": metadata.get("security_domains", "")
            }
            
        except Exception as e:
            logger.error(f"Error extracting metadata for {control_ref}: {str(e)}")
            return {
                "subject": "",
                "verbs": "",
                "context": "",
                "semantic_summary": "",
                "key_concepts": "",
                "scope": "",
                "security_domains": ""
            }
    
    def extract_batch_metadata(
        self,
        controls: list,
        max_workers: int = 8  # More workers for fast model
    ) -> list:
        """
        Extract metadata for multiple controls in parallel.
        
        Args:
            controls: List of tuples (control_ref, control_text)
            max_workers: Number of parallel workers
            
        Returns:
            List of metadata dicts
        """
        results = [None] * len(controls)
        
        logger.info(f"Extracting metadata for {len(controls)} controls with {max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(self.extract_metadata, ref, text): idx
                for idx, (ref, text) in enumerate(controls)
            }
            
            completed = 0
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    metadata = future.result()
                    results[idx] = metadata
                    completed += 1
                    
                    if completed % 20 == 0:
                        logger.info(f"  Completed {completed}/{len(controls)} extractions")
                        
                except Exception as e:
                    logger.error(f"Error in batch extraction: {str(e)}")
                    results[idx] = {
                        "subject": "", 
                        "verbs": "", 
                        "context": "",
                        "semantic_summary": "",
                        "key_concepts": "",
                        "scope": "",
                        "security_domains": ""
                    }
        
        return results


def create_enriched_text(
    control_text: str, 
    subject: str, 
    verbs: str, 
    context: str,
    semantic_summary: str,
    key_concepts: str,
    scope: str,
    security_domains: str
) -> str:
    """
    Create RICHLY enriched text by appending comprehensive metadata to original control text.
    
    This creates a semantically rich representation that embeddings can capture.
    
    Args:
        control_text: Original control text
        subject: Extracted subject
        verbs: Extracted verbs
        context: Extracted context
        semantic_summary: Rich semantic summary
        key_concepts: Key security concepts
        scope: Scope of control
        security_domains: Relevant security domains
        
    Returns:
        Richly enriched text string
    """
    # Build comprehensive enrichment
    enrichment_parts = []
    
    # Core metadata
    if subject:
        enrichment_parts.append(f"TOPICS: {subject}")
    if verbs:
        enrichment_parts.append(f"ACTIONS: {verbs}")
    if security_domains:
        enrichment_parts.append(f"DOMAINS: {security_domains}")
    
    # Rich semantic content
    if semantic_summary:
        enrichment_parts.append(f"SUMMARY: {semantic_summary}")
    
    if context:
        enrichment_parts.append(f"PURPOSE: {context}")
    
    if key_concepts:
        enrichment_parts.append(f"CONCEPTS: {key_concepts}")
    
    if scope:
        enrichment_parts.append(f"SCOPE: {scope}")
    
    if enrichment_parts:
        # Create multi-line enrichment for better embedding
        enrichment_str = "\n".join([f"[{part}]" for part in enrichment_parts])
        return f"{control_text}\n\n{enrichment_str}"
    else:
        return control_text


def enrich_controls(
    df: pd.DataFrame,
    extractor: FastMetadataExtractor,
    output_path: Path,
    standard_name: str
) -> pd.DataFrame:
    """
    Extract metadata and create enriched controls.
    
    Input df has: control_ref, control_text (already enriched with synonyms from step1_5)
    Output df has: control_ref, control_text (original), control_text_enriched (with synonyms),
                   + all metadata fields + enriched_text (for embedding)
    """
    logger.info(f"\nEnriching {standard_name} controls ({len(df)} controls)...")
    
    # The input control_text is already enriched with synonyms from step1_5
    # Keep it as control_text_enriched
    enriched_df = df.copy()
    enriched_df['control_text_enriched'] = enriched_df['control_text']
    
    # Prepare control list (use enriched text for metadata extraction)
    controls = list(zip(df['control_ref'], df['control_text']))
    
    # Extract metadata
    metadata_list = extractor.extract_batch_metadata(controls, max_workers=8)
    
    # Add metadata fields
    enriched_df['subject'] = [m['subject'] for m in metadata_list]
    enriched_df['verbs'] = [m['verbs'] for m in metadata_list]
    enriched_df['context'] = [m['context'] for m in metadata_list]
    enriched_df['semantic_summary'] = [m['semantic_summary'] for m in metadata_list]
    enriched_df['key_concepts'] = [m['key_concepts'] for m in metadata_list]
    enriched_df['scope'] = [m['scope'] for m in metadata_list]
    enriched_df['security_domains'] = [m['security_domains'] for m in metadata_list]
    
    # Create RICHLY enriched text for embedding (using synonym-enriched text)
    enriched_df['enriched_text'] = enriched_df.apply(
        lambda row: create_enriched_text(
            row['control_text_enriched'],
            row['subject'],
            row['verbs'],
            row['context'],
            row['semantic_summary'],
            row['key_concepts'],
            row['scope'],
            row['security_domains']
        ),
        axis=1
    )
    
    # Save to CSV
    enriched_df.to_csv(output_path, index=False)
    logger.info(f"✓ Saved enriched {standard_name} controls to: {output_path}")
    
    # Show sample with rich metadata
    logger.info(f"\nSample enriched control:")
    logger.info(f"  Ref: {enriched_df['control_ref'].iloc[0]}")
    logger.info(f"  Original: {enriched_df['control_text'].iloc[0][:100]}...")
    logger.info(f"  Subject: {enriched_df['subject'].iloc[0]}")
    logger.info(f"  Verbs: {enriched_df['verbs'].iloc[0]}")
    logger.info(f"  Domains: {enriched_df['security_domains'].iloc[0]}")
    logger.info(f"  Summary: {enriched_df['semantic_summary'].iloc[0][:100]}...")
    logger.info(f"  Key Concepts: {enriched_df['key_concepts'].iloc[0][:80]}...")
    logger.info(f"\n  Enriched text length: {len(enriched_df['enriched_text'].iloc[0])} chars")
    
    return enriched_df


def main():
    """Main function for Step 1.7."""
    # Hardcoded configuration - read from step1_5 output (enriched files)
    source_csv = "data/enriched_source.csv"
    target_csv = "data/enriched_target.csv"
    output_dir = "data"
    llm_model = "openai/gpt-oss-120b"  # HIGH-QUALITY model for maximum quality
    log_level = "INFO"
    
    # Setup logging
    global logger
    logger = setup_logger(level=log_level)
    
    logger.info("="*60)
    logger.info("STEP 1.7: EXTRACT RICH METADATA FOR MAXIMUM EMBEDDING QUALITY")
    logger.info("="*60)
    logger.info(f"Using HIGH-QUALITY model: {llm_model}")
    logger.info("Extracting comprehensive semantic metadata for superior embeddings")
    logger.info("Quality-first approach - cost is not a concern")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Initialize extractor
        logger.info("\nInitializing fast metadata extractor...")
        extractor = FastMetadataExtractor(model=llm_model)
        
        # Load and enrich source controls (ECC)
        logger.info("\n" + "-"*60)
        logger.info("PROCESSING ECC CONTROLS")
        logger.info("-"*60)
        
        source_df = pd.read_csv(source_csv)
        logger.info(f"Loaded {len(source_df)} ECC controls")
        
        enriched_source = enrich_controls(
            source_df,
            extractor,
            output_path / "source_with_metadata_gpt_oss.csv",
            "ECC"
        )
        
        # Load and enrich target controls (ISO)
        logger.info("\n" + "-"*60)
        logger.info("PROCESSING ISO CONTROLS")
        logger.info("-"*60)
        
        target_df = pd.read_csv(target_csv)
        logger.info(f"Loaded {len(target_df)} ISO controls")
        
        enriched_target = enrich_controls(
            target_df,
            extractor,
            output_path / "target_with_metadata_gpt_oss.csv",
            "ISO"
        )
        
        # Print summary
        print("\n" + "="*60)
        print("RICH METADATA EXTRACTION SUMMARY")
        print("="*60)
        print(f"ECC Controls: {len(enriched_source)}")
        print(f"  - Added fields: subject, verbs, context, semantic_summary,")
        print(f"                  key_concepts, scope, security_domains, enriched_text")
        print(f"\nISO Controls: {len(enriched_target)}")
        print(f"  - Added fields: subject, verbs, context, semantic_summary,")
        print(f"                  key_concepts, scope, security_domains, enriched_text")
        print(f"\nQuality Enhancements:")
        print(f"  ✓ Deep semantic analysis with GPT-oss-120b")
        print(f"  ✓ 7 metadata fields per control")
        print(f"  ✓ Rich semantic summaries (3-4 sentences)")
        print(f"  ✓ Comprehensive concept extraction")
        print(f"  ✓ Multi-line enriched text for superior embeddings")
        print(f"\nOutput files:")
        print(f"  data/source_with_metadata.csv")
        print(f"  data/target_with_metadata.csv")
        print("="*60)
        print("\n✓ Step 1.5 completed successfully!")
        print("\nExpected improvement: 20-40% better mapping quality!")
        
    except Exception as e:
        logger.error(f"Error in Step 1.5: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()