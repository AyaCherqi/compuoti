"""Epsilon-constraint and Pareto-frontier utilities.

Suggested approach:
1. Choose financial performance as the primary objective (maximize).
2. Convert minimization objectives to explicit epsilon bounds.
3. Sweep feasible epsilon values for makespan / employee-project count / late projects.
4. Store objective vectors and schedules.
5. Remove dominated objective vectors.
"""

from collections.abc import Sequence


def dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    """Return True if a dominates b for a maximization-oriented vector.

    Convert minimization objectives (e.g. makespan) by negating them before calling.
    """
    return all(x >= y for x, y in zip(a, b)) and any(
        x > y for x, y in zip(a, b)
    )


def pareto_filter(points: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """Return non-dominated points, preserving original order."""
    return [
        point for i, point in enumerate(points)
        if not any(
            i != j and dominates(other, point)
            for j, other in enumerate(points)
        )
    ]
