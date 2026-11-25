"""Four-objective epsilon-constraint exploration for CompuOpti.

Primary objective (unchanged): maximize financial performance.
Epsilon bounds: completion <= epsilon_2, relationships <= epsilon_3,
                late_projects <= epsilon_4.

Every epsilon subproblem is solved lexicographically:
    maximize financial,
    then minimize completion without losing financial performance,
    then minimize relationships,
    then minimize late projects.

This refinement prevents returning weakly dominated schedules merely
because profit ties. The returned solutions are filtered in objective space.

A finite epsilon grid samples the Pareto frontier; it does NOT guarantee
enumeration of every possible nondominated schedule.
"""

from __future__ import annotations

import argparse
import itertools
from collections.abc import Iterable
from typing import Any

import gurobipy as gp
from gurobipy import GRB

from .data import load_instance, validate_instance
from .model import build_model, objective_expression, set_objective
from .pareto import nondominated_solutions
from .solve import export_solution, extract_solution, status_name


REFINEMENT_ORDER = (
    "financial", "completion", "relationships", "late_projects"
)


def epsilon_levels(upper: int, count: int) -> list[int]:
    """Generate inclusive, evenly spaced integer epsilon bounds."""
    if upper < 0:
        raise ValueError("upper must be non-negative.")
    if count < 2:
        raise ValueError("grid_levels must be at least 2.")
    return sorted({
        (upper * index + (count - 1) // 2) // (count - 1)
        for index in range(count)
    })


def _solve_epsilon_case(
    instance: Any,
    epsilon_completion: int,
    epsilon_relationships: int,
    epsilon_late_projects: int,
    min_selected_projects: int,
    time_limit: float | None,
    mip_gap: float,
    verbose: bool,
    tolerance: float,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Solve a single epsilon subproblem and return schedule + diagnostics."""
    artifacts = build_model(instance, objective="financial")
    model = artifacts.model
    v = artifacts.variables
    norm = artifacts.instance
    bounds = {
        "completion": epsilon_completion,
        "relationships": epsilon_relationships,
        "late_projects": epsilon_late_projects,
    }

    diagnostics: dict[str, Any] = {
        "epsilon_bounds": bounds,
        "stage_statuses": {},
        "number_of_optimizations": 0,
        "status": "NOT_STARTED",
    }
    try:
        model.Params.OutputFlag = 1 if verbose else 0
        model.Params.MIPGap = mip_gap
        if time_limit is not None:
            model.Params.TimeLimit = time_limit

        model.addConstr(
            objective_expression(artifacts, "completion") <= epsilon_completion,
            name="epsilon_completion",
        )
        model.addConstr(
            objective_expression(artifacts, "relationships")
            <= epsilon_relationships,
            name="epsilon_relationships",
        )
        model.addConstr(
            objective_expression(artifacts, "late_projects")
            <= epsilon_late_projects,
            name="epsilon_late_projects",
        )

        if min_selected_projects:
            model.addConstr(
                gp.quicksum(v["Y"].values()) >= min_selected_projects,
                name="minimum_selected_projects",
            )

        previous_objective = None
        previous_value = None
        primary_status = None
        financial_optimum = None

        for name in REFINEMENT_ORDER:
            if previous_objective is not None:
                old_expr = objective_expression(artifacts, previous_objective)
                # Keep previously optimized objectives at their best values,
                # within a small absolute numerical tolerance.
                if previous_objective == "financial":
                    model.addConstr(
                        old_expr >= previous_value - tolerance,
                        name="preserve_financial",
                    )
                else:
                    model.addConstr(
                        old_expr <= previous_value + tolerance,
                        name=f"preserve_{previous_objective}",
                    )

            set_objective(artifacts, name)
            model.optimize()
            status = model.Status
            diagnostics["number_of_optimizations"] += 1
            diagnostics["stage_statuses"][name] = status_name(status)

            if name == "financial":
                primary_status = status

            # Do not claim a (strong) Pareto candidate for an unfinished
            # optimization: a better objective vector may still exist.
            if status != GRB.OPTIMAL or model.SolCount == 0:
                diagnostics["status"] = (
                    "INFEASIBLE"
                    if status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD)
                    else "INCOMPLETE"
                )
                return None, diagnostics

            previous_objective = name
            previous_value = float(model.ObjVal)
            if name == "financial":
                financial_optimum = previous_value

        # All four refinement stages finished at Gurobi's OPTIMAL status.
        result = extract_solution(
            artifacts,
            original_instance=instance,
            objective="financial",
            primary_status=primary_status,
            secondary_status=model.Status,
        )
        result.update({
            "status": model.Status,
            "status_name": status_name(model.Status),
            "primary_objective_value": financial_optimum,
            "optimality_proven": mip_gap == 0.0,
            "epsilon_bounds": bounds,
            "lexicographic_stage_statuses": diagnostics["stage_statuses"],
        })
        diagnostics["status"] = "SOLVED"
        return result, diagnostics
    finally:
        model.dispose()


def explore_pareto_frontier(
    instance: Any,
    grid_levels: int = 3,
    min_selected_projects: int = 0,
    time_limit: float | None = None,
    mip_gap: float = 0.0,
    verbose: bool = False,
    max_runs: int | None = None,
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Sample the four-objective Pareto frontier using epsilon constraints.

    grid_levels=3 means up to 3^3=27 epsilon subproblems.
    Each may require four Gurobi optimizations to avoid weak dominance.

    Bounds are generated from SAFE upper limits, not arbitrary profit
    percentages. A sampled frontier may miss other nondominated points.

    min_selected_projects=0 preserves the professor's optional-project
    feasible set (including an empty portfolio). Set to 1 explicitly to
    exclude that trivial portfolio for business-focused experiments.

    Incomplete/timeout cases are not included in the reported frontier.
    """
    if grid_levels < 2:
        raise ValueError("grid_levels must be at least 2.")
    if (
        isinstance(min_selected_projects, bool)
        or not isinstance(min_selected_projects, int)
        or min_selected_projects < 0
    ):
        raise ValueError("min_selected_projects must be a non-negative integer.")
    if time_limit is not None and time_limit <= 0:
        raise ValueError("time_limit must be positive.")
    if not 0 <= mip_gap <= 1:
        raise ValueError("mip_gap must be between 0 and 1.")
    if max_runs is not None and max_runs < 1:
        raise ValueError("max_runs must be positive.")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive.")

    # Compatible with both the typed data instance and normalized fixtures.
    from .model import _adapt_instance
    norm = _adapt_instance(instance)
    if min_selected_projects > len(norm.projects):
        raise ValueError("min_selected_projects exceeds the number of projects.")

    # These are mathematical upper bounds for the three minimizing
    # objectives, so the final grid value never artificially cuts off a
    # feasible schedule. A finite sampling grid can still miss Pareto points.
    completion_max = max(norm.days) * len(norm.projects)
    relationships_max = len(norm.employees) * len(norm.projects)
    late_projects_max = len(norm.projects)

    grids = {
        "completion": epsilon_levels(completion_max, grid_levels),
        "relationships": epsilon_levels(relationships_max, grid_levels),
        "late_projects": epsilon_levels(late_projects_max, grid_levels),
    }

    candidates = []
    attempts = []
    # Begin with the loosest epsilon limits. This finds a feasible baseline
    # early (when one exists), even if --max-runs limits exploration.
    combinations: Iterable[tuple[int, int, int]] = itertools.product(
        reversed(grids["completion"]),
        reversed(grids["relationships"]),
        reversed(grids["late_projects"]),
    )

    for eps2, eps3, eps4 in combinations:
        if max_runs is not None and len(attempts) >= max_runs:
            break

        candidate, diagnostic = _solve_epsilon_case(
            instance=instance,
            epsilon_completion=eps2,
            epsilon_relationships=eps3,
            epsilon_late_projects=eps4,
            min_selected_projects=min_selected_projects,
            time_limit=time_limit,
            mip_gap=mip_gap,
            verbose=verbose,
            tolerance=tolerance,
        )
        attempts.append(diagnostic)
        if candidate is not None:
            candidates.append(candidate)

    frontier = nondominated_solutions(candidates, tolerance=tolerance)
    frontier.sort(
        key=lambda result: (
            -result["objective_values"]["financial"],
            result["objective_values"]["completion"],
            result["objective_values"]["relationships"],
            result["objective_values"]["late_projects"],
        )
    )

    successful = sum(a["status"] == "SOLVED" for a in attempts)
    incomplete = sum(a["status"] == "INCOMPLETE" for a in attempts)
    infeasible = sum(a["status"] == "INFEASIBLE" for a in attempts)
    total_combinations = (
        len(grids["completion"])
        * len(grids["relationships"])
        * len(grids["late_projects"])
    )

    return {
        "method": "epsilon_constraint",
        "primary_objective": "financial",
        "minimized_objectives": [
            "completion", "relationships", "late_projects"
        ],
        "min_selected_projects": min_selected_projects,
        "grid_levels": grid_levels,
        "epsilon_grid": grids,
        "total_grid_combinations": total_combinations,
        "attempted_combinations": len(attempts),
        "successful_combinations": successful,
        "infeasible_combinations": infeasible,
        "incomplete_combinations": incomplete,
        "number_of_gurobi_optimizations": sum(
            a["number_of_optimizations"] for a in attempts
        ),
        "search_complete": (
            len(attempts) == total_combinations and incomplete == 0
        ),
        "all_refinements_zero_gap": mip_gap == 0.0,
        "frontier_is_sampled": True,
        "candidate_count": len(candidates),
        "nondominated_count": len(frontier),
        "solutions": frontier,
        "attempts": attempts,
    }


def main() -> None:
    """CLI for a sampled four-objective epsilon-constraint experiment."""
    parser = argparse.ArgumentParser(
        description="Sample a CompuOpti Pareto frontier with epsilon constraints."
    )
    parser.add_argument("--instance", required=True, help="JSON instance path.")
    parser.add_argument(
        "--grid-levels", type=int, default=3,
        help="Integer levels per epsilon dimension (default 3 => up to 27 cases).",
    )
    parser.add_argument(
        "--min-selected", type=int, default=0,
        help="Optional extra rule: require this many projects (0 preserves baseline).",
    )
    parser.add_argument(
        "--time-limit", type=float, default=None,
        help="Optional time limit in seconds per Gurobi optimization.",
    )
    parser.add_argument(
        "--mip-gap", type=float, default=0.0,
        help="MIP gap for each subproblem (default 0 for strongest guarantees).",
    )
    parser.add_argument(
        "--max-runs", type=int, default=None,
        help="Optional cap on epsilon combinations attempted.",
    )
    parser.add_argument("--output", default="results/pareto.json")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    try:
        instance = load_instance(args.instance)
        errors = validate_instance(instance)
        if errors:
            parser.error("; ".join(errors))

        result = explore_pareto_frontier(
            instance,
            grid_levels=args.grid_levels,
            min_selected_projects=args.min_selected,
            time_limit=args.time_limit,
            mip_gap=args.mip_gap,
            verbose=args.verbose,
            max_runs=args.max_runs,
        )
        destination = export_solution(result, args.output)
        print(f"Epsilon combinations checked: {result['attempted_combinations']}")
        print(f"Solved: {result['successful_combinations']}")
        print(f"Infeasible: {result['infeasible_combinations']}")
        print(f"Incomplete: {result['incomplete_combinations']}")
        print(f"Sampled nondominated objective vectors: {result['nondominated_count']}")
        if not result["search_complete"]:
            print("Warning: not every planned epsilon subproblem completed.")
        print("Note: a sampled grid cannot guarantee the complete Pareto frontier.")
        print(f"Saved to: {destination}")
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
