
"""Solver execution, solution extraction, and JSON export for CompuOpti."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gurobipy import GRB

from .data import load_instance, validate_instance
from .model import build_model


OBJECTIVES = (
    "financial",
    "completion",
    "relationships",
    "late_projects",
)


def calculate_objective_values(artifacts: Any) -> dict[str, float]:
    """Calculate all four objective values from an optimized model."""

    variables = artifacts.variables
    instance = artifacts.instance

    financial = sum(
        instance.gain[j] * variables["Y"][j].X
        - instance.late_penalty[j] * variables["L"][j].X
        for j in instance.projects
    )

    completion = sum(
        variables["E"][j].X
        for j in instance.projects
    )

    relationships = sum(
        variables["Z"][i, j].X
        for i in instance.employees
        for j in instance.projects
    )

    late_projects = sum(
        variables["W"][j].X
        for j in instance.projects
    )

    return {
        "financial": float(financial),
        "completion": float(completion),
        "relationships": float(relationships),
        "late_projects": float(late_projects),
    }


def extract_solution(
    artifacts: Any,
    original_instance: Any,
    objective: str,
    primary_status: int,
    secondary_status: int | None,
) -> dict[str, Any]:
    """Extract assignments, project schedules, and objective values."""

    variables = artifacts.variables

    employees = {
        employee.id: employee
        for employee in original_instance.employees
    }

    projects = {
        project.id: project
        for project in original_instance.projects
    }

    assignments = []

    for (employee_id, project_id, qualification, day), variable in (
        variables["X"].items()
    ):
        if variable.X > 0.5:
            assignments.append({
                "employee_id": employee_id,
                "employee_name": employees[employee_id].name,
                "project_id": project_id,
                "project_name": projects[project_id].name,
                "qualification": qualification,
                "day": day,
            })

    project_schedules = []

    for project_id, project in projects.items():
        completion_day = int(round(variables["E"][project_id].X))
        late_days = int(round(variables["L"][project_id].X))
        is_late = variables["W"][project_id].X > 0.5

        assigned_employees = sorted({
            assignment["employee_name"]
            for assignment in assignments
            if assignment["project_id"] == project_id
        })

        project_schedules.append({
            "project_id": project_id,
            "project_name": project.name,
            "due_date": project.due_date,
            "completion_day": completion_day,
            "late_days": late_days,
            "is_late": is_late,
            "assigned_employees": assigned_employees,
        })

    return {
        "objective_selected": objective,
        "primary_solver_status": primary_status,
        "secondary_solver_status": secondary_status,
        "objective_values": calculate_objective_values(artifacts),
        "assignments": assignments,
        "projects": project_schedules,
    }


def status_name(status: int) -> str:
    """Convert a Gurobi status code into a readable name."""

    names = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.INF_OR_UNBD: "INFEASIBLE_OR_UNBOUNDED",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.TIME_LIMIT: "TIME_LIMIT",
        GRB.INTERRUPTED: "INTERRUPTED",
        GRB.SUBOPTIMAL: "SUBOPTIMAL",
        GRB.NUMERIC: "NUMERIC",
    }

    return names.get(status, f"OTHER_STATUS_{status}")


def solve_instance(
    instance: Any,
    objective: str = "financial",
    time_limit: float | None = None,
    mip_gap: float | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Optimize an instance using two-stage lexicographic optimization.

    Stage 1 optimizes the selected primary objective.
    Stage 2 minimizes total completion time without worsening
    the primary objective beyond a small numerical tolerance.
    """

    if objective not in OBJECTIVES:
        raise ValueError(
            f"Unknown objective '{objective}'. "
            f"Choose from: {', '.join(OBJECTIVES)}."
        )

    artifacts = build_model(instance, objective=objective)
    model = artifacts.model

    try:
        model.Params.OutputFlag = 1 if verbose else 0

        if time_limit is not None:
            if time_limit <= 0:
                raise ValueError("time_limit must be positive.")
            model.Params.TimeLimit = time_limit

        if mip_gap is not None:
            if mip_gap < 0:
                raise ValueError("mip_gap cannot be negative.")
            model.Params.MIPGap = mip_gap

        # =================================================
        # STAGE 1: Optimize the selected primary objective
        # =================================================

        model.optimize()

        primary_status = model.Status

        if model.SolCount == 0:
            return {
                "objective_selected": objective,
                "status": primary_status,
                "status_name": status_name(primary_status),
                "primary_solver_status": primary_status,
                "secondary_solver_status": None,
                "objective_values": None,
                "assignments": [],
                "projects": [],
            }

        # Capture the objective expression and value
        # after the first optimization.
        primary_expression = model.getObjective()
        primary_value = model.ObjVal

        # =================================================
        # STAGE 2: Preserve primary objective and minimize
        # total project completion time
        # =================================================

        tolerance = 1e-6

        if objective == "financial":
            model.addConstr(
                primary_expression >= primary_value - tolerance,
                name="fix_primary_objective",
            )
        else:
            model.addConstr(
                primary_expression <= primary_value + tolerance,
                name="fix_primary_objective",
            )

        total_completion_time = sum(
            artifacts.variables["E"][j]
            for j in artifacts.instance.projects
        )

        model.setObjective(total_completion_time, GRB.MINIMIZE)

        model.optimize()

        secondary_status = model.Status

        if model.SolCount == 0:
            return {
                "objective_selected": objective,
                "status": secondary_status,
                "status_name": status_name(secondary_status),
                "primary_solver_status": primary_status,
                "secondary_solver_status": secondary_status,
                "primary_objective_value": float(primary_value),
                "objective_values": None,
                "assignments": [],
                "projects": [],
                "error": "Stage 2 did not find a feasible solution.",
            }

        # =================================================
        # EXTRACT FINAL SOLUTION
        # =================================================

        result = extract_solution(
            artifacts,
            instance,
            objective,
            primary_status,
            secondary_status,
        )

        result["status"] = secondary_status
        result["status_name"] = status_name(secondary_status)
        result["primary_objective_value"] = float(primary_value)

        return result

    finally:
        model.dispose()


def export_solution(
    result: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Export a solver result to a JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    return path


def main() -> None:
    """Command-line interface for running CompuOpti."""

    parser = argparse.ArgumentParser(
        description="Run CompuOpti employee/project scheduling optimization."
    )

    parser.add_argument(
        "--instance",
        required=True,
        help="Path to the JSON instance.",
    )

    parser.add_argument(
        "--objective",
        choices=OBJECTIVES,
        default="financial",
        help="Objective to optimize (default: financial).",
    )

    parser.add_argument(
        "--output",
        default="results/solution.json",
        help="Path where the solution JSON will be saved.",
    )

    parser.add_argument(
        "--time-limit",
        type=float,
        default=None,
        help="Optional solver time limit in seconds per optimization stage.",
    )

    parser.add_argument(
        "--mip-gap",
        type=float,
        default=None,
        help="Optional relative MIP optimality gap.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display Gurobi optimization logs.",
    )

    args = parser.parse_args()

    try:
        instance = load_instance(args.instance)

        errors = validate_instance(instance)

        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            raise SystemExit(1)

        print(f"Loaded instance: {instance.source}")
        print(f"Selected objective: {args.objective}")

        result = solve_instance(
            instance,
            objective=args.objective,
            time_limit=args.time_limit,
            mip_gap=args.mip_gap,
            verbose=args.verbose,
        )

        print(f"Solver status: {result['status_name']}")

        if result["objective_values"] is None:
            print("No feasible solution was found.")
            raise SystemExit(1)

        output_path = export_solution(result, args.output)

        print("\nObjective values:")

        for name, value in result["objective_values"].items():
            print(f"  {name}: {value:.2f}")

        print(f"\nSolution exported to: {output_path}")

    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
