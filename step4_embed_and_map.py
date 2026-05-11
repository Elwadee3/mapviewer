import pandas as pd
import numpy as np
from pathlib import Path
import sys
from tqdm import tqdm
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

# Ensure you have installed these:
# pip install FlagEmbedding torch pandas numpy tqdm
try:
    from FlagEmbedding import BGEM3FlagModel, FlagReranker
except ImportError:
    print("Missing dependencies. Please run: pip install FlagEmbedding torch")
    sys.exit(1)

# ============================================================
# CORE EMBEDDING & RERANKER CLASSES
# ============================================================

@dataclass
class HybridEmbeddings:
    """Container for dense and sparse embedding representations."""
    dense: np.ndarray
    sparse: List[Dict[str, float]]

class BGEM3HybridModel:
    def __init__(self, model_name: str = "BAAI/bge-m3", use_fp16: bool = True):
        logger.info(f"Initializing BGE-M3 model: {model_name}")
        self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
        
    def encode(self, sentences: List[str], batch_size: int = 32) -> HybridEmbeddings:
        """Generates both dense and lexical (sparse) embeddings."""
        output = self.model.encode(
            sentences, 
            batch_size=batch_size, 
            return_dense=True, 
            return_sparse=True
        )
        return HybridEmbeddings(
            dense=output['dense_vecs'],
            sparse=output['lexical_weights']
        )

    def compute_sparse_similarity(self, query_sparse: Dict[str, float], target_sparse: Dict[str, float]) -> float:
        """Compute the lexical overlap score between two sparse weight dictionaries."""
        score = 0.0
        if len(query_sparse) > len(target_sparse):
            query_sparse, target_sparse = target_sparse, query_sparse
        for token, weight in query_sparse.items():
            if token in target_sparse:
                score += (weight * target_sparse[token]) * 5
        return score

class BGEReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", use_fp16: bool = True):
        logger.info(f"Initializing Reranker model: {model_name}")
        self.model = FlagReranker(model_name, use_fp16=use_fp16)

    def compute_scores(self, pairs: List[List[str]]) -> List[float]:
        return self.model.compute_score(pairs)

# ============================================================
# PIPELINE UTILITIES
# ============================================================

def setup_logger(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = logging.getLogger(__name__)

METADATA_FIELDS = [
    ('subject', 'Subject'), ('verbs', 'Actions'), ('context', 'Context'),
    ('semantic_summary', 'Summary'), ('key_concepts', 'Concepts'),
    ('scope', 'Scope'), ('security_domains', 'Domains'),
]

def build_embedding_text(row: pd.Series, use_metadata: bool = True) -> str:
    if 'control_text_enriched' in row.index and pd.notna(row['control_text_enriched']):
        base_text = row['control_text_enriched']
    else:
        base_text = row.get('control_text', '')
    
    parts = [str(base_text)]
    if use_metadata:
        for field_name, label in METADATA_FIELDS:
            if field_name in row.index and pd.notna(row[field_name]) and row[field_name]:
                parts.append(f"{label}: {row[field_name]}")
    return " | ".join(parts)

# ============================================================
# SEARCH & MAPPING LOGIC
# ============================================================

def create_mapping_dataframe_batched(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    source_embeddings: HybridEmbeddings,
    target_embeddings: HybridEmbeddings,
    hybrid_model: BGEM3HybridModel,
    reranker: Optional[BGEReranker],
    initial_k: int = 50,
    final_k: int = 10,
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3
) -> pd.DataFrame:
    source_refs = source_df['control_ref'].tolist()
    source_texts = source_df['control_text'].tolist()
    target_refs = target_df['control_ref'].tolist()
    target_texts = target_df['control_text'].tolist()
    
    source_embed_texts = source_df['control_text_enriched'].tolist() if 'control_text_enriched' in source_df.columns else source_texts
    target_embed_texts = target_df['control_text_enriched'].tolist() if 'control_text_enriched' in target_df.columns else target_texts

    # 1. Compute Matrices
    logger.info("Computing dense similarity matrix...")
    from numpy.linalg import norm
    source_norm = source_embeddings.dense / norm(source_embeddings.dense, axis=1, keepdims=True)
    target_norm = target_embeddings.dense / norm(target_embeddings.dense, axis=1, keepdims=True)
    dense_scores_matrix = np.dot(source_norm, target_norm.T)
    
    logger.info("Computing sparse similarity matrix...")
    sparse_scores_matrix = np.zeros((len(source_refs), len(target_refs)))
    for i in tqdm(range(len(source_refs)), desc="Sparse Scoring"):
        q_sparse = source_embeddings.sparse[i]
        for j, t_sparse in enumerate(target_embeddings.sparse):
            sparse_scores_matrix[i, j] = hybrid_model.compute_sparse_similarity(q_sparse, t_sparse)
    
    # 2. Hybrid Calculation
    hybrid_scores_matrix = (dense_weight * dense_scores_matrix) + (sparse_weight * sparse_scores_matrix)
    top_k_indices = np.argsort(hybrid_scores_matrix, axis=1)[:, ::-1][:, :initial_k]
    
    # 3. Optional Reranking
    rerank_scores_matrix = None
    if reranker is not None:
        all_pairs = []
        for i in range(len(source_refs)):
            query_text = source_embed_texts[i]
            for target_idx in top_k_indices[i]:
                all_pairs.append([query_text, target_embed_texts[target_idx]])
        
        logger.info(f"Reranking {len(all_pairs)} pairs...")
        scores = reranker.compute_scores(all_pairs)
        rerank_scores_matrix = np.array(scores).reshape(len(source_refs), initial_k)

    # 4. Build Results with Dense and Sparse scores
    results = []
    for i in range(len(source_refs)):
        row_data = {'control_ref': source_refs[i], 'control_text': source_texts[i]}
        
        if reranker is not None:
            rel_idx_in_topk = np.argsort(rerank_scores_matrix[i])[::-1][:final_k]
            sorted_target_indices = top_k_indices[i][rel_idx_in_topk]
        else:
            sorted_target_indices = top_k_indices[i][:final_k]

        for rank, target_idx in enumerate(sorted_target_indices, start=1):
            row_data[f'mapping_{rank}_ref'] = target_refs[target_idx]
            row_data[f'mapping_{rank}_text'] = target_texts[target_idx]
            
            # Extract individual score components
            row_data[f'dense_score_{rank}'] = float(dense_scores_matrix[i, target_idx])
            row_data[f'sparse_score_{rank}'] = float(sparse_scores_matrix[i, target_idx])
            row_data[f'hybrid_score_{rank}'] = float(hybrid_scores_matrix[i, target_idx])
            
            if reranker is not None:
                cand_pos = np.where(top_k_indices[i] == target_idx)[0][0]
                row_data[f'rerank_score_{rank}'] = float(rerank_scores_matrix[i, cand_pos])
        
        results.append(row_data)
    
    return pd.DataFrame(results)

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    USE_RERANKING = False  
    USE_METADATA = True    
    INITIAL_K = 20         
    FINAL_K = 10           

    source_csv = "data/source_with_metadata.csv"
    target_csv = "data/target_with_metadata.csv"
    output_dir = "data"
    
    global logger
    logger = setup_logger()
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        source_df = pd.read_csv(source_csv)
        target_df = pd.read_csv(target_csv)
        
        hybrid_model = BGEM3HybridModel()
        reranker = BGEReranker() if USE_RERANKING else None
        
        source_texts = source_df.apply(lambda r: build_embedding_text(r, USE_METADATA), axis=1).tolist()
        target_texts = target_df.apply(lambda r: build_embedding_text(r, USE_METADATA), axis=1).tolist()
        
        source_embs = hybrid_model.encode(source_texts, batch_size=32)
        target_embs = hybrid_model.encode(target_texts, batch_size=32)
        
        mapping_df = create_mapping_dataframe_batched(
            source_df, target_df, source_embs, target_embs,
            hybrid_model, reranker, initial_k=INITIAL_K, final_k=FINAL_K
        )
        
        out_path = Path(output_dir) / "source_to_target_mappings.csv"
        mapping_df.to_csv(out_path, index=False)
        logger.info(f"DONE! Columns include Dense, Sparse, and Hybrid scores.")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()