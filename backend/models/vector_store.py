"""FAISS-based vector similarity search for face embeddings."""

import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import Optional
from config import settings


class VectorStore:
    """Manages FAISS index for face embedding similarity search."""

    def __init__(self) -> None:
        self._index: Optional[faiss.Index] = None
        self._id_map: dict[int, int] = {}  # FAISS id -> actor_id
        self._reverse_map: dict[int, set[int]] = {}  # actor_id -> FAISS ids
        self._next_faiss_id: int = 0
        self._loaded: bool = False
        self._embedding_dim: int = settings.embedding_dim

    @property
    def is_loaded(self) -> bool:
        return self._loaded and self._index is not None

    @property
    def index_size(self) -> int:
        if self._index is None:
            return 0
        return self._index.ntotal

    def load_index(self) -> bool:
        """Load existing FAISS index from disk."""
        try:
            if not settings.faiss_index_path.exists():
                self._loaded = False
                return False

            self._index = faiss.read_index(str(settings.faiss_index_path))
            self._loaded = True

            # Load ID mapping
            if settings.faiss_id_map_path.exists():
                with open(settings.faiss_id_map_path, "rb") as f:
                    self._id_map = pickle.load(f)
                    self._rebuild_reverse_map()
                    self._next_faiss_id = max(self._id_map.keys()) + 1 if self._id_map else 0
            else:
                self._id_map = {}
                self._reverse_map = {}
                self._next_faiss_id = 0

            print(f"[VectorStore] Loaded index with {self.index_size} vectors")
            return True
        except Exception as e:
            print(f"[VectorStore] Error loading index: {e}")
            self._index = None
            self._loaded = False
            return False

    def save_index(self) -> bool:
        """Save FAISS index to disk."""
        try:
            settings.faiss_index_dir.mkdir(parents=True, exist_ok=True)
            if self._index is not None:
                faiss.write_index(self._index, str(settings.faiss_index_path))
            with open(settings.faiss_id_map_path, "wb") as f:
                pickle.dump(self._id_map, f)
            print(f"[VectorStore] Saved index with {self.index_size} vectors")
            return True
        except Exception as e:
            print(f"[VectorStore] Error saving index: {e}")
            return False

    def create_index(self) -> None:
        """Create a new FAISS index."""
        index_type = settings.faiss_index_type.upper()

        if index_type == "HNSW32":
            base_index = faiss.IndexHNSWFlat(
                self._embedding_dim,
                settings.faiss_m,
                faiss.METRIC_INNER_PRODUCT,
            )
            base_index.hnsw.efConstruction = settings.faiss_ef_construction
            base_index.hnsw.M = settings.faiss_m
            self._index = faiss.IndexIDMap2(base_index)
        elif index_type == "IVFFlat":
            n_lists = 100
            base_index = faiss.IndexIVFFlat(
                faiss.IndexFlatL2(self._embedding_dim),
                self._embedding_dim,
                n_lists,
                faiss.METRIC_INNER_PRODUCT,
            )
            base_index.is_trained = True
            self._index = faiss.IndexIDMap2(base_index)
        else:
            # Default to Flat index (exact search, most accurate)
            self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(self._embedding_dim))

        self._loaded = False

    def add_vectors(
        self,
        embeddings: list[np.ndarray],
        actor_id: int,
    ) -> list[int]:
        """
        Add face embeddings to the index.

        Args:
            embeddings: List of embedding vectors
            actor_id: The actor ID these embeddings belong to

        Returns:
            List of FAISS IDs assigned
        """
        if self._index is None:
            self.create_index()

        assigned_ids: list[int] = []
        for embedding in embeddings:
            faiss_id = self._next_faiss_id
            self._id_map[faiss_id] = actor_id
            self._reverse_map.setdefault(actor_id, set()).add(faiss_id)
            self._next_faiss_id += 1
            assigned_ids.append(faiss_id)

        # Normalize embeddings for inner product (cosine similarity)
        normalized = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(normalized)

        # Add to index
        faiss_ids_array = np.array(assigned_ids, dtype=np.int64)
        self._index.add_with_ids(normalized, faiss_ids_array)

        self._loaded = True
        return assigned_ids

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        threshold: float = 0.0,
    ) -> list[tuple[int, float]]:
        """
        Search for similar faces.

        Args:
            query_embedding: Query embedding vector
            k: Number of top results
            threshold: Minimum similarity threshold (0.0 = no threshold)

        Returns:
            List of (actor_id, similarity_score) tuples
        """
        if self._index is None or self.index_size == 0:
            return []

        # Normalize query
        query = query_embedding.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(query)

        # Search more vectors than the final actor count because one actor can
        # have multiple reference photos and occupy several nearest slots.
        multiplier = max(settings.faiss_candidate_multiplier, 1)
        candidate_k = min(max(k * multiplier, k), self.index_size)
        distances, indices = self._index.search(query, candidate_k)

        metric_type = getattr(self._index, "metric_type", faiss.METRIC_INNER_PRODUCT)
        similarities_by_actor: dict[int, list[float]] = {}
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # No result
                continue
            if metric_type == faiss.METRIC_L2:
                # For L2 indexes built from normalized embeddings, FAISS returns
                # squared L2 distance: d = 2 - 2*cosine.
                similarity = 1.0 - (float(dist) / 2.0)
            else:
                # Inner product over normalized embeddings is cosine similarity.
                similarity = float(dist)
            actor_id = self._id_map.get(idx, -1)
            if actor_id != -1:
                similarities_by_actor.setdefault(actor_id, []).append(similarity)

        actor_scores = self._aggregate_actor_scores(similarities_by_actor)
        if threshold > 0:
            actor_scores = {
                actor_id: score
                for actor_id, score in actor_scores.items()
                if score >= threshold
            }

        return sorted(actor_scores.items(), key=lambda item: item[1], reverse=True)[:k]

    def _aggregate_actor_scores(self, similarities_by_actor: dict[int, list[float]]) -> dict[int, float]:
        """Score actors by their best match plus support from nearby references.

        Several good reference photos for the same actor should be stronger than
        one isolated nearest vector. This keeps the old best-vector behavior as
        the dominant signal and adds a small vote from the next closest vectors.
        """
        top_n = max(settings.face_reference_vote_top_n, 1)
        vote_weight = min(max(settings.face_reference_vote_weight, 0.0), 1.0)
        vote_bonus = max(settings.face_reference_vote_bonus, 0.0)

        scores: dict[int, float] = {}
        for actor_id, similarities in similarities_by_actor.items():
            if not similarities:
                continue
            top = sorted(similarities, reverse=True)[:top_n]
            best = top[0]
            mean_top = float(np.mean(top))
            support_bonus = min(max(len(top) - 1, 0) * vote_bonus, 0.03)
            scores[actor_id] = min(
                (best * (1.0 - vote_weight)) + (mean_top * vote_weight) + support_bonus,
                1.0,
            )

        return scores

    def remove_actor(self, actor_id: int) -> bool:
        """Remove all vectors for an actor from the index."""
        if self._index is None:
            return False

        # Find FAISS IDs for this actor
        faiss_ids_to_remove = [
            fid for fid, aid in self._id_map.items() if aid == actor_id
        ]

        if not faiss_ids_to_remove:
            return False

        # FAISS doesn't support direct deletion for all index types, so we rebuild.
        old_id_map = dict(self._id_map)
        remaining_ids = [fid for fid, aid in old_id_map.items() if aid != actor_id]

        if not remaining_ids:
            self._index = None
            self._id_map = {}
            self._reverse_map = {}
            self._next_faiss_id = 0
            self._loaded = False
            return True

        # Get remaining vectors before resetting the index.
        remaining_items: list[tuple[np.ndarray, int]] = []
        for fid in remaining_ids:
            vec = self._index.reconstruct(fid)
            remaining_items.append((vec, old_id_map[fid]))

        # Rebuild index
        self.create_index()
        self._id_map = {}
        self._reverse_map = {}
        self._next_faiss_id = 0
        for embedding, remaining_actor_id in remaining_items:
            self.add_vectors([embedding], remaining_actor_id)

        self._loaded = True
        return True

    def get_actor_ids(self) -> set[int]:
        """Get all unique actor IDs in the index."""
        return set(self._id_map.values())

    def _rebuild_reverse_map(self) -> None:
        """Rebuild actor_id -> FAISS ids map from the persisted FAISS id map."""
        self._reverse_map = {}
        for faiss_id, actor_id in self._id_map.items():
            self._reverse_map.setdefault(actor_id, set()).add(faiss_id)

    def clear(self) -> None:
        """Clear the index."""
        self._index = None
        self._id_map = {}
        self._reverse_map = {}
        self._next_faiss_id = 0
        self._loaded = False
