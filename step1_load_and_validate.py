import pandas as pd
from pathlib import Path
import sys
import re
from collections import defaultdict
from difflib import SequenceMatcher
# from src.utils.logger import setup_logger, logger

# Add parent directory to path to access src
sys.path.append(str(Path(__file__).parent.parent))

# from src.utils.logger import setup_logger, logger


def find_common_prefix(texts):
    """
    Find the longest common prefix among a list of texts.
    Uses word-level matching to avoid cutting words in half.
    """
    if not texts or len(texts) == 1:
        return ""
    
    # Split into words
    word_lists = [text.split() for text in texts]
    
    # Find common prefix words
    common_words = []
    min_length = min(len(words) for words in word_lists)
    
    for i in range(min_length):
        first_word = word_lists[0][i]
        if all(words[i] == first_word for words in word_lists):
            common_words.append(first_word)
        else:
            break
    
    return " ".join(common_words)


def extract_unique_part(full_text, common_prefix):
    """
    Extract the unique part of text after removing common prefix.
    Also removes common sentence patterns to avoid repetition.
    """
    if not common_prefix:
        return full_text
    
    # Remove common prefix
    if full_text.startswith(common_prefix):
        unique = full_text[len(common_prefix):].strip()
    else:
        unique = full_text
    
    # Remove leading colons and whitespace
    unique = unique.lstrip(': ')
    
    # If the unique part is very short or empty, return the full text
    if len(unique) < 10:
        return full_text
    
    return unique


def create_parent_sections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Intelligently create parent section controls from hierarchical children.
    
    For example, if we have 9.3.1, 9.3.2, 9.3.3, this will create/update 9.3
    with the combined text, avoiding duplication of common prefixes.
    
    Args:
        df: DataFrame with control_ref and control_text columns
        
    Returns:
        DataFrame with parent sections added/updated
    """
    # logger.info("Creating parent section controls...")
    
    # Group controls by potential parent
    parent_groups = defaultdict(list)
    
    for idx, row in df.iterrows():
        ref = str(row['control_ref']).strip()
        
        # Match hierarchical patterns like 9.3.1, A.5.2.1, etc.
        # Only create first-gen parents: X.Y from X.Y.Z (not X from X.Y)
        # Pattern: parent must have at least one dot, child adds one more level
        match = re.match(r'^([A-Z]?\d+\.\d+(?:\.[a-z])?)\.(\d+[a-z]?)$', ref)
        if match:
            parent_ref = match.group(1)
            parent_groups[parent_ref].append({
                'ref': ref,
                'text': row['control_text'],
                'full_row': row
            })
    
    # Create parent controls
    new_rows = []
    parents_created = 0
    parents_updated = 0
    
    for parent_ref, children in parent_groups.items():
        if len(children) < 2:
            # Need at least 2 children to create a meaningful parent
            continue
        
        # Extract texts
        child_texts = [child['text'] for child in children]
        
        # Find common prefix
        common_prefix = find_common_prefix(child_texts)
        
        # Build parent text
        if common_prefix and len(common_prefix.split()) > 3:
            # We have a meaningful common prefix
            parent_text = common_prefix
            
            # Add unique portions from each child
            unique_parts = []
            for child in sorted(children, key=lambda x: x['ref']):
                unique_part = extract_unique_part(child['text'], common_prefix)
                
                # Only add if there's meaningful unique content
                if unique_part and unique_part != child['text']:
                    unique_parts.append(unique_part)
                elif unique_part:
                    # If extraction didn't work well, skip it
                    pass
            
            # Combine: common prefix + unique parts separated by semicolons
            if unique_parts:
                parent_text = parent_text + "; " + "; ".join(unique_parts)
        else:
            # No meaningful common prefix, use first child as base
            # and add references to others
            base_child = sorted(children, key=lambda x: x['ref'])[0]
            parent_text = base_child['text']
            
            # Add note about other children
            other_refs = [c['ref'] for c in sorted(children, key=lambda x: x['ref'])[1:]]
            if other_refs:
                parent_text += f"; Also see: {', '.join(other_refs)}"
        
        # Check if parent already exists
        existing_parent = df[df['control_ref'] == parent_ref]
        
        if not existing_parent.empty:
            # Update existing parent
            df.loc[df['control_ref'] == parent_ref, 'control_text'] = parent_text
            parents_updated += 1
            # logger.info(f"  Updated parent {parent_ref} (from {len(children)} children)")
        else:
            # Create new parent row
            new_row = children[0]['full_row'].copy()
            new_row['control_ref'] = parent_ref
            new_row['control_text'] = parent_text
            new_rows.append(new_row)
            parents_created += 1
            # logger.info(f"  Created parent {parent_ref} (from {len(children)} children)")
    
    # Add new parent rows to dataframe
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    
    # logger.info(f"✓ Parent sections: {parents_created} created, {parents_updated} updated")
    
    return df


def load_and_validate_csv(input_path: str, output_path: str, dataset_name: str) -> pd.DataFrame:
    """
    Load and validate a CSV file.
    
    Args:
        input_path: Path to input CSV file
        output_path: Path to save validated CSV
        dataset_name: Name of the dataset (for logging)
        
    Returns:
        Validated DataFrame
    """
    # logger.info(f"Loading {dataset_name} from: {input_path}")
    
    # Check if file exists
    if not Path(input_path).exists():
        raise FileNotFoundError(f"File not found: {input_path}")
    
    # Load CSV
    df = pd.read_csv(input_path)
    # logger.info(f"Loaded {len(df)} rows and {len(df.columns)} columns")
    
    # Validate required columns
    required_columns = ['control_ref', 'control_text']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns in {dataset_name}: {missing_columns}")
    
    # logger.info(f"✓ Required columns present: {required_columns}")
    
    # Basic data cleaning
    # Handle null values in text columns
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('')
        else:
            df[col] = df[col].fillna(0)
    
    # Remove completely empty rows
    initial_count = len(df)
    df = df[df['control_text'].str.strip() != '']
    df = df[df['control_ref'].str.strip() != '']
    removed_count = initial_count - len(df)
    
    if removed_count > 0:
        logger.warning(f"Removed {removed_count} empty rows")
    
    # Convert control_ref to string
    df['control_ref'] = df['control_ref'].astype(str)
    df['control_text'] = df['control_text'].astype(str)
    
    # Check for duplicates
    duplicates = df['control_ref'].duplicated().sum()
    if duplicates > 0:
        logger.warning(f"Found {duplicates} duplicate control_ref entries")
        # Keep first occurrence
        df = df.drop_duplicates(subset=['control_ref'], keep='first')
    
    # Create parent sections from hierarchical controls
    df = create_parent_sections(df)
    
    # Sort by control_ref for better organization
    df = df.sort_values('control_ref').reset_index(drop=True)
    
    # Save validated data
    df.to_csv(output_path, index=False)
    # logger.info(f"✓ Saved validated {dataset_name} to: {output_path}")
    #logger.info(f"  Final count: {len(df)} controls")
    
    # Print sample
    #logger.info(f"\nSample from {dataset_name}:")
    #logger.info(f"  {df['control_ref'].iloc[0]}: {df['control_text'].iloc[0][:100]}...")
    
    return df


def main():
    """Main function for Step 1."""
    # Hardcoded configuration
    source_csv = "data/ecc_parsed.csv"
    target_csv = "data/nist_parsed.csv"
    output_dir = "data/"
    log_level = "INFO"
    
    # Setup logging
    global logger
    logger = None
    
    print("="*60)
    print("STEP 1: LOAD AND VALIDATE DATA")
    print("="*60)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Load and validate source CSV
        source_output = output_path / "validated_source.csv"
        source_df = load_and_validate_csv(
            source_csv, 
            str(source_output),
            "source dataset"
        )
        
        # Load and validate target CSV
        target_output = output_path / "validated_target.csv"
        target_df = load_and_validate_csv(
            target_csv,
            str(target_output),
            "target dataset"
        )
        
        # Print summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Source controls: {len(source_df)}")
        print(f"Target controls: {len(target_df)}")
        print(f"\nOutput files:")
        print(f"  {source_output}")
        print(f"  {target_output}")
        print("="*60)
        print("\n✓ Step 1 completed successfully!")
        print("\nNext step: Run step2_embed_and_map.py")
        
    except Exception as e:
        logger.error(f"Error in Step 1: {str(e)}")
        raise


if __name__ == "__main__":
    main()
