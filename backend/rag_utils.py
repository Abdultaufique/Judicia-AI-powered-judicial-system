"""
LIGHTWEIGHT RAG ENGINE — TF-IDF Based Retriever
================================================
• Zero heavyweight dependencies (no LangChain, FAISS, HuggingFace, PyTorch)
• Uses scikit-learn TfidfVectorizer + cosine_similarity
• Loads laws.txt and precedents.txt from data/ folder
• Chunks text into ~500-char passages, builds in-memory TF-IDF index
• Works on Render free tier, any Python 3.8+
"""

import os
import re
import numpy as np
from typing import List, Dict, Optional

# ─── Text Chunking Utility ────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks by paragraph boundaries."""
    # Split by double-newline (paragraph) boundaries first
    paragraphs = re.split(r'\n\n+', text.strip())

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph exceeds chunk_size, save current and start new
        if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Overlap: keep last `overlap` chars of current chunk
            if len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + "\n\n" + para
            else:
                current_chunk = para
        else:
            current_chunk = (current_chunk + "\n\n" + para).strip()

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ─── Lightweight RAG Engine ───────────────────────────────────────────────────

class LightweightRAG:
    """
    TF-IDF based retriever for legal documents.
    Loads laws.txt and precedents.txt, chunks them, and allows
    similarity-based retrieval against uploaded PDF text.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.chunks: List[str] = []
        self.sources: List[str] = []  # Which file each chunk came from
        self.vectorizer = None
        self.tfidf_matrix = None
        self.is_ready = False
        self.num_chunks = 0
        self.files_loaded: List[str] = []

        # Determine data directory
        if data_dir:
            self.data_dir = data_dir
        else:
            # Default: project_root/data/
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(backend_dir)
            self.data_dir = os.path.join(project_root, "data")

        # Auto-build index on init
        self._build_index()

    def _load_file(self, filepath: str, source_name: str) -> List[str]:
        """Load and chunk a single text file."""
        if not os.path.exists(filepath):
            print(f"[RAG] File not found: {filepath}")
            return []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()

            if len(text.strip()) < 50:
                print(f"[RAG] File too small, skipping: {filepath}")
                return []

            file_chunks = chunk_text(text, chunk_size=500, overlap=100)
            # Filter out tiny chunks
            file_chunks = [c for c in file_chunks if len(c) > 30]
            self.files_loaded.append(source_name)
            print(f"[RAG] Loaded {source_name}: {len(file_chunks)} chunks from {len(text)} chars")
            return file_chunks

        except Exception as e:
            print(f"[RAG] Error loading {filepath}: {e}")
            return []

    def _build_index(self):
        """Load all data files and build the TF-IDF index."""
        print("[RAG] Building TF-IDF index...")

        # Load laws and precedents
        laws_file = os.path.join(self.data_dir, "laws.txt")
        precedents_file = os.path.join(self.data_dir, "precedents.txt")

        laws_chunks = self._load_file(laws_file, "laws.txt")
        precedents_chunks = self._load_file(precedents_file, "precedents.txt")

        # Combine all chunks with source tracking
        for chunk in laws_chunks:
            self.chunks.append(chunk)
            self.sources.append("Indian Penal Code (IPC)")

        for chunk in precedents_chunks:
            self.chunks.append(chunk)
            self.sources.append("Landmark Precedents")

        self.num_chunks = len(self.chunks)

        if self.num_chunks == 0:
            print("[RAG] No data loaded. RAG will be inactive.")
            return

        # Build TF-IDF matrix
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self.vectorizer = TfidfVectorizer(
                max_features=10000,
                stop_words='english',
                ngram_range=(1, 2),     # Unigrams and bigrams for better legal term matching
                sublinear_tf=True,      # Apply log normalization
                min_df=1,
                max_df=0.95
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(self.chunks)
            self.is_ready = True
            print(f"[RAG] Index ready: {self.num_chunks} chunks, {self.tfidf_matrix.shape[1]} features")

        except ImportError:
            print("[RAG] scikit-learn not installed. RAG will be inactive.")
            print("[RAG] Install with: pip install scikit-learn")
        except Exception as e:
            print(f"[RAG] Error building index: {e}")

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Retrieve the most relevant chunks for a given query.

        Args:
            query: The text to search for (typically extracted PDF content or key terms)
            top_k: Number of results to return

        Returns:
            List of dicts with keys: text, source, relevance
        """
        if not self.is_ready or not query.strip():
            return []

        try:
            from sklearn.metrics.pairwise import cosine_similarity

            # Transform query using the fitted vectorizer
            query_vec = self.vectorizer.transform([query])

            # Compute cosine similarity against all chunks
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

            # Get top-k indices (sorted by relevance descending)
            top_indices = np.argsort(similarities)[::-1][:top_k]

            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                if score < 0.01:  # Skip near-zero relevance
                    continue
                results.append({
                    "text": self.chunks[idx],
                    "source": self.sources[idx],
                    "relevance": round(score, 4)
                })

            return results

        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")
            return []

    def retrieve_for_judgment(self, judgment_text: str, top_k: int = 8) -> Dict:
        """
        High-level method: extract key terms from judgment text,
        retrieve relevant laws and precedents, and format as context string.

        Returns:
            {
                "context": str (formatted for agent prompts),
                "sources": list[dict] (individual retrieved chunks)
            }
        """
        if not self.is_ready:
            return {"context": "", "sources": []}

        # Extract key legal terms from the judgment for targeted retrieval
        # Use first 2000 chars as query (covers case background + charges)
        query = judgment_text[:2000]

        # Also try to extract specific IPC sections for targeted search
        sections = re.findall(r'(?:Section|S\.)\s*(\d+[A-Z]?)', judgment_text[:5000])
        if sections:
            section_query = " ".join([f"Section {s} IPC" for s in set(sections[:5])])
            query = section_query + "\n" + query

        # Retrieve relevant chunks
        results = self.retrieve(query, top_k=top_k)

        if not results:
            return {"context": "", "sources": []}

        # Format as context string for agent prompts
        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(
                f"[RAG Source {i} — {r['source']} (relevance: {r['relevance']:.2f})]:\n"
                f"{r['text']}"
            )

        context = "\n\n---\n\n".join(context_parts)

        return {
            "context": context,
            "sources": results
        }

    def status(self) -> Dict:
        """Return status information about the RAG engine."""
        return {
            "is_ready": self.is_ready,
            "num_chunks": self.num_chunks,
            "files_loaded": self.files_loaded,
            "data_dir": self.data_dir,
            "features": self.tfidf_matrix.shape[1] if self.tfidf_matrix is not None else 0
        }


# ─── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  LIGHTWEIGHT RAG ENGINE — TEST")
    print("=" * 60 + "\n")

    rag = LightweightRAG()
    print(f"\nStatus: {rag.status()}\n")

    if rag.is_ready:
        # Test retrieval
        test_queries = [
            "Section 302 IPC murder",
            "Section 498A cruelty wife",
            "bail conditions anticipatory",
            "right to life Article 21"
        ]
        for q in test_queries:
            print(f"\n🔎 Query: '{q}'")
            results = rag.retrieve(q, top_k=3)
            for r in results:
                print(f"   [{r['source']}] (score: {r['relevance']:.3f})")
                print(f"   {r['text'][:120]}...\n")