"""
backend/app/services/embeddings.py
Local embeddings using sentence-transformers (completely free, no API key needed).
Model: all-MiniLM-L6-v2
  - 384 dimensions (small and fast)
  - Downloads ~90MB on first use, cached locally after that
  - Good enough for knowledge base retrieval

NOTE: The knowledge_base table has embedding vector(1536) for OpenAI compatibility.
      We'll use 384 dimensions and update the schema accordingly.
      In production you'd use text-embedding-3-small, but for portfolio/dev this is fine.
"""

import logging
import numpy as np
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lazy load — model only loads when first embedding is requested
_model = None
EMBEDDING_DIM = 384   # all-MiniLM-L6-v2 output dimension
MODEL_NAME = "all-MiniLM-L6-v2"


def get_model():
    """Load model once and cache it in memory."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model '{MODEL_NAME}'...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded successfully")
    return _model


def embed_text(text: str) -> list[float]:
    """
    Embed a single text string.
    Returns a list of floats (384 dimensions).
    """
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Batch embed multiple texts (more efficient than one at a time).
    """
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Manual cosine similarity — used in tests without DB."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))