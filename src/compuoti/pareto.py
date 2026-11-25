"""Pareto dominance and nondominated filtering for CompuOpti.

Objective directions:
    financial: maximize
    completion, relationships, late_projects: minimize

The legacy functions dominates() and pareto_filter() operate on vectors
with ALL coordinates already oriented toward maximization.
"""

from collections.abc import Mapping, Sequence
from typing import Any


OBJECTIVE_NAMES = (
    "financial", "completion", "relationships", "late_projects"
)


def dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    """True if maximization-oriented vector a strictly dominates b."""
    if len(a) != len(b):
        raise ValueError("Objective vectors must have equal lengths.")
    return (
        all(x >= y for x, y in zip(a, b))
        and any(x > y for x, y in zip(a, b))
    )


def pareto_filter(points: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """Remove dominated maximization-oriented vectors, preserving order."""
    return [
        point
        for i, point in enumerate(points)
        if not any(
            i != j and dominates(other, point)
            for j, other in enumerate(points)
        )
    ]


def objective_vector(values: Mapping[str, float]) -> tuple[float, ...]:
    """Convert the four objectives into maximization-oriented coordinates."""
    return (
        float(values["financial"]),
        -float(values["completion"]),
        -float(values["relationships"]),
        -float(values["late_projects"]),
    )


def dominates_objectives(
    a: Mapping[str, float],
    b: Mapping[str, float],
    tolerance: float = 1e-6,
) -> bool:
    """True if a dominates b in the original mixed-direction objectives."""
    if tolerance < 0:
        raise ValueError("tolerance must not be negative.")
    av = objective_vector(a)
    bv = objective_vector(b)
    return (
        all(x >= y - tolerance for x, y in zip(av, bv))
        and any(x > y + tolerance for x, y in zip(av, bv))
    )


def _same_objective_values(
    a: Mapping[str, float],
    b: Mapping[str, float],
    tolerance: float,
) -> bool:
    return all(
        abs(float(a[name]) - float(b[name])) <= tolerance
        for name in OBJECTIVE_NAMES
    )


def nondominated_solutions(
    solutions: list[dict[str, Any]],
    tolerance: float = 1e-6,
) -> list[dict[str, Any]]:
    """Return sampled nondominated solutions, one per objective vector.

    Each item must include an ``objective_values`` mapping. Duplicates with
    the same objective values are collapsed to the first encountered schedule.
    This is a frontier in objective space, not enumeration of every decision-
    space schedule yielding those same values.
    """
    if tolerance < 0:
        raise ValueError("tolerance must not be negative.")
    valid = [s for s in solutions if s.get("objective_values") is not None]
    result = []
    for i, candidate in enumerate(valid):
        values = candidate["objective_values"]
        if any(
            j != i
            and dominates_objectives(
                other["objective_values"], values, tolerance
            )
            for j, other in enumerate(valid)
        ):
            continue
        if any(
            _same_objective_values(
                earlier["objective_values"], values, tolerance
            )
            for earlier in result
        ):
            continue
        result.append(candidate)
    return result
