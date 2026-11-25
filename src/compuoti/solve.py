"""Single-objective solving, solution extraction, and JSON export.

Unlike the previous version, no second-stage completion-time optimization is
needed: model.py now defines completion dates exactly for every feasible
schedule. The four-objective epsilon-constraint search is in multiobjective.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gurobipy import GRB

from .data import load_instance, validate_instance
from .model import OBJECTIVES, build_model


def calculate_objective_values(artifacts: Any) -> dict[str, float]:
    """Calculate the four objective values of the current feasible solution."""
    v = artifacts.variables
    instance = artifacts.instance
    return {
        "financial": float(sum(
            instance.gain[j] * v["Y"][j].X
            - instance.late_penalty[j] * v["L"][j].X
            for j in instance.projects
        )),
        "completion": float(sum(v["E"][j].X for j in instance.projects)),
        "relationships": float(sum(
            v["Z"][i, j].X
            for i in instance.employees
            for j in instance.projects
        )),
        "late_projects": float(sum(v["W"][j].X for j in instance.projects)),
    }


def status_name(status: int) -> str:
    """Convert common Gurobi status codes to readable names."""
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


def extract_solution(
    artifacts: Any,
    original_instance: Any,
    objective: str,
    primary_status: int,
    secondary_status: int | None = None,
) -> dict[str, Any]:
    """Extract a schedule, supporting typed and normalized instances."""
    v = artifacts.variables
    inst = artifacts.instance

    # Typed data.Instance objects have employee/project objects with names;
    # legacy SimpleNamespace test fixtures have string IDs instead.
    employee_names = {}
    if hasattr(original_instance, "employees"):
        for item in original_instance.employees:
            key = getattr(item, "id", item)
            employee_names[key] = str(getattr(item, "name", key))
    project_names = {}
    if hasattr(original_instance, "projects"):
        for item in original_instance.projects:
            key = getattr(item, "id", item)
            project_names[key] = str(getattr(item, "name", key))

    assignments = []
    for (i, j, k, t), var in v["X"].items():
        if var.X > 0.5:
            assignments.append({
                "employee_id": i,
                "employee_name": employee_names.get(i, str(i)),
                "project_id": j,
                "project_name": project_names.get(j, str(j)),
                "qualification": k,
                "day": t,
            })
    assignments.sort(
        key=lambda x: (
            x["day"], str(x["employee_id"]),
            str(x["project_id"]), str(x["qualification"])
        )
    )

    schedules = []
    for j in inst.projects:
        selected = bool(v["Y"][j].X > 0.5)
        assigned_employees = sorted({
            row["employee_name"]
            for row in assignments if row["project_id"] == j
        })
        schedules.append({
            "project_id": j,
            "project_name": project_names.get(j, str(j)),
            "selected": selected,
            "due_date": inst.deadline[j],
            "completion_day": int(round(v["E"][j].X)),
            "late_days": int(round(v["L"][j].X)),
            "is_late": bool(v["W"][j].X > 0.5),
            "assigned_employees": assigned_employees,
        })

    return {
        "objective_selected": objective,
        "primary_solver_status": primary_status,
        "secondary_solver_status": secondary_status,
        "objective_values": calculate_objective_values(artifacts),
        "assignments": assignments,
        "projects": schedules,
        "selected_project_count": sum(p["selected"] for p in schedules),
    }


def _empty_result(objective: str, status: int) -> dict[str, Any]:
    """Return a consistent result when no feasible schedule was found."""
    return {
        "objective_selected": objective,
        "status": status,
        "status_name": status_name(status),
        "primary_solver_status": status,
        "secondary_solver_status": None,
        "primary_objective_value": None,
        "optimality_proven": False,
        "objective_values": None,
        "assignments": [],
        "projects": [],
        "selected_project_count": 0,
    }


def solve_instance(
    instance: Any,
    objective: str = "financial",
    time_limit: float | None = None,
    mip_gap: float | None = None,
    verbose: bool = False,
    min_selected_projects: int = 0,
) -> dict[str, Any]:
    """Optimize one objective and return the full four-objective evaluation.

    With optional projects, standalone minimization can legitimately choose
    no projects. Set min_selected_projects=1 to exclude the empty portfolio
    when that is a desired *additional* business rule.
    """
    if objective not in OBJECTIVES:
        raise ValueError(
            f"Unknown objective '{objective}'. Choose from: {', '.join(OBJECTIVES)}."
        )
    if time_limit is not None and time_limit <= 0:
        raise ValueError("time_limit must be positive.")
    if mip_gap is not None and not 0 <= mip_gap <= 1:
        raise ValueError("mip_gap must be between 0 and 1.")
    if (
        isinstance(min_selected_projects, bool)
        or not isinstance(min_selected_projects, int)
        or min_selected_projects < 0
    ):
        raise ValueError("min_selected_projects must be a non-negative integer.")

    artifacts = build_model(instance, objective=objective)
    model = artifacts.model
    try:
        if min_selected_projects > len(artifacts.instance.projects):
            raise ValueError("min_selected_projects exceeds the number of projects.")

        model.Params.OutputFlag = 1 if verbose else 0
        if time_limit is not None:
            model.Params.TimeLimit = time_limit
        if mip_gap is not None:
            model.Params.MIPGap = mip_gap

        if min_selected_projects:
            from gurobipy import quicksum
            model.addConstr(
                quicksum(artifacts.variables["Y"].values()) >= min_selected_projects,
                name="minimum_selected_projects",
            )

        model.optimize()
        status = model.Status
        if model.SolCount == 0:
            return _empty_result(objective, status)

        result = extract_solution(
            artifacts, instance, objective,
            primary_status=status, secondary_status=None
        )
        result.update({
            "status": status,
            "status_name": status_name(status),
            "primary_objective_value": float(model.ObjVal),
            "optimality_proven": status == GRB.OPTIMAL,
        })
        return result
    finally:
        model.dispose()


def export_solution(result: dict[str, Any], output_path: str | Path) -> Path:
    """Save a solver result as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)
    return path


def main() -> None:
    """Run a single objective from the command line."""
    parser = argparse.ArgumentParser(
        description="Solve one CompuOpti objective on a course JSON instance."
    )
    parser.add_argument("--instance", required=True, help="Path to an instance JSON.")
    parser.add_argument("--objective", choices=OBJECTIVES, default="financial")
    parser.add_argument("--output", default="results/solution.json")
    parser.add_argument("--time-limit", type=float, default=None)
    parser.add_argument("--mip-gap", type=float, default=None)
    parser.add_argument(
        "--min-selected", type=int, default=0,
        help="Additional business rule: minimum number of projects (default 0).",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    try:
        instance = load_instance(args.instance)
        errors = validate_instance(instance)
        if errors:
            parser.error("; ".join(errors))

        result = solve_instance(
            instance,
            objective=args.objective,
            time_limit=args.time_limit,
            mip_gap=args.mip_gap,
            verbose=args.verbose,
            min_selected_projects=args.min_selected,
        )
        print(f"Solver status: {result['status_name']}")
        if result["objective_values"] is None:
            print("No feasible schedule found.")
            raise SystemExit(1)

        destination = export_solution(result, args.output)
        for name, value in result["objective_values"].items():
            print(f"  {name}: {value:.2f}")
        print(
            f"Selected projects: "
            f"{result['selected_project_count']}/{len(result['projects'])}"
        )
        if not result["optimality_proven"]:
            print("Warning: feasible incumbent, optimality not established.")
        print(f"Saved to: {destination}")
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
