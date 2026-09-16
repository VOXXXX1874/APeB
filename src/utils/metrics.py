"""Canonical release metrics."""

from __future__ import annotations


def recall_at_k(
    predicted_indices: list[int], ground_truth_indices: list[int], k: int
) -> float:
    """Compute Recall@K for one sample."""

    if k < 1:
        raise ValueError("k must be positive")
    ground_truth = set(ground_truth_indices)
    if not ground_truth:
        return 0.0
    hits = len(set(predicted_indices[:k]) & ground_truth)
    return hits / len(ground_truth)


def evaluate_ranking(
    predicted_indices: list[int], ground_truth_indices: list[int]
) -> dict[str, float]:
    """Return the three metrics reported by the camera-ready release."""

    return {
        "recall_at_1": recall_at_k(predicted_indices, ground_truth_indices, 1),
        "recall_at_3": recall_at_k(predicted_indices, ground_truth_indices, 3),
        "recall_at_5": recall_at_k(predicted_indices, ground_truth_indices, 5),
    }
