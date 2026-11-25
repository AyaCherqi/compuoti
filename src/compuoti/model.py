"""MILP model for CompuOpti.

The professor's financial objective and BOTH person-day inequalities are
preserved verbatim in mathematical meaning. Additional constraints define
optional-project behavior, exact completion dates, and extra objectives.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import gurobipy as gp
from gurobipy import GRB


OBJECTIVES = ("financial", "completion", "relationships", "late_projects")


@dataclass
class ModelArtifacts:
    model: Any
    variables: dict[str, Any]
    instance: Any


def _adapt_instance(instance: Any) -> Any:
    """Accept either the typed data.Instance or the legacy normalized fixture."""
    if hasattr(instance, "employee_qualifications"):
        return instance

    return SimpleNamespace(
        days=list(instance.days),
        employees=list(instance.employee_ids),
        projects=list(instance.project_ids),
        qualifications=list(instance.qualifications),
        employee_qualifications={
            employee.id: set(employee.qualifications)
            for employee in instance.employees
        },
        leave_days={
            employee.id: set(employee.vacations)
            for employee in instance.employees
        },
        required_qualifications={
            project.id: set(project.requirements)
            for project in instance.projects
        },
        required_person_days={
            (project.id, skill): days
            for project in instance.projects
            for skill, days in project.requirements.items()
        },
        gain={project.id: project.gain for project in instance.projects},
        late_penalty={
            project.id: project.daily_penalty for project in instance.projects
        },
        deadline={project.id: project.due_date for project in instance.projects},
    )


def objective_expression(artifacts: ModelArtifacts, objective: str) -> Any:
    """Return a Gurobi expression for one of the four objectives."""
    instance = artifacts.instance
    variables = artifacts.variables
    X = variables  # Only an alias for compact indexing below.

    if objective == "financial":
        # Professor's first optimization function -- unchanged.
        return gp.quicksum(
            instance.gain[j] * X["Y"][j]
            - instance.late_penalty[j] * X["L"][j]
            for j in instance.projects
        )
    if objective == "completion":
        # Sum of actual last-assignment days (0 for rejected projects).
        return gp.quicksum(X["E"][j] for j in instance.projects)
    if objective == "relationships":
        return gp.quicksum(
            X["Z"][i, j]
            for i in instance.employees
            for j in instance.projects
        )
    if objective == "late_projects":
        return gp.quicksum(X["W"][j] for j in instance.projects)
    raise ValueError(f"Unknown objective: {objective}")


def set_objective(artifacts: ModelArtifacts, objective: str) -> None:
    """Set the requested objective, preserving its intended direction."""
    expression = objective_expression(artifacts, objective)
    direction = GRB.MAXIMIZE if objective == "financial" else GRB.MINIMIZE
    artifacts.model.setObjective(expression, direction)


def build_model(instance: Any, objective: str = "financial") -> ModelArtifacts:
    """Build the MILP with optional projects and exact timing/lateness."""
    if objective not in OBJECTIVES:
        raise ValueError(f"Unknown objective: {objective}")

    instance = _adapt_instance(instance)
    days = list(instance.days)
    if not days:
        raise ValueError("The planning horizon cannot be empty.")

    employees = list(instance.employees)
    projects = list(instance.projects)
    first_day = min(days)
    last_day = max(days)

    model = gp.Model("CompuOpti")

    # X[i,j,k,t] is created only for qualified, non-vacation assignments.
    X = {}
    by_employee_day = {(i, t): [] for i in employees for t in days}
    by_project_skill = {
        (j, k): []
        for j in projects
        for k in instance.required_qualifications[j]
    }
    by_project_day = {(j, t): [] for j in projects for t in days}
    by_employee_project = {
        (i, j): [] for i in employees for j in projects
    }

    for i in employees:
        for j in projects:
            for k in instance.required_qualifications[j]:
                if k not in instance.employee_qualifications[i]:
                    continue
                for t in days:
                    if t in instance.leave_days[i]:
                        continue
                    var = model.addVar(
                        vtype=GRB.BINARY, name=f"X_{i}_{j}_{k}_{t}"
                    )
                    X[i, j, k, t] = var
                    by_employee_day[i, t].append(var)
                    by_project_skill[j, k].append(var)
                    by_project_day[j, t].append(var)
                    by_employee_project[i, j].append(var)

    Y = {
        j: model.addVar(vtype=GRB.BINARY, name=f"Y_{j}")
        for j in projects
    }
    # Zero marks a rejected project; selected projects finish in [first_day,last_day].
    E = {
        j: model.addVar(vtype=GRB.INTEGER, lb=0, ub=last_day, name=f"E_{j}")
        for j in projects
    }
    L = {
        j: model.addVar(vtype=GRB.INTEGER, lb=0, name=f"L_{j}")
        for j in projects
    }
    Z = {
        (i, j): model.addVar(vtype=GRB.BINARY, name=f"Z_{i}_{j}")
        for i in employees for j in projects
    }
    W = {
        j: model.addVar(vtype=GRB.BINARY, name=f"W_{j}")
        for j in projects
    }

    # C1: One assignment at most per employee and day.
    for i in employees:
        for t in days:
            model.addConstr(
                gp.quicksum(by_employee_day[i, t]) <= 1,
                name=f"C1_{i}_{t}",
            )

    # C2 / C3: Leave days, skill compatibility enforced by sparse X creation.

    # C4: Preserve the professor's TWO requirement inequalities.
    # Do NOT replace them with a single equality.
    for j in projects:
        for k in instance.required_qualifications[j]:
            assignments = gp.quicksum(by_project_skill[j, k])
            required = instance.required_person_days[j, k]

            model.addConstr(
                Y[j] * required <= assignments,
                name=f"C4_lower_{j}_{k}",
            )
            model.addConstr(
                assignments <= required,
                name=f"C4_upper_{j}_{k}",
            )

    # Additional selection link: do not spend staff-days on rejected projects.
    for (i, j, k, t), var in X.items():
        model.addConstr(var <= Y[j], name=f"C5_selection_{i}_{j}_{k}_{t}")

    # C6: Z[i,j] is 1 exactly when employee i works on project j.
    for i in employees:
        for j in projects:
            work = by_employee_project[i, j]
            for var in work:
                model.addConstr(var <= Z[i, j])
            model.addConstr(
                Z[i, j] <= gp.quicksum(work),
                name=f"C6_reverse_{i}_{j}",
            )

    # C7: Original professor inequality -- unchanged.
    for (i, j, k, t), var in X.items():
        model.addConstr(E[j] >= t * var, name=f"C7_{i}_{j}_{k}_{t}")

    for j in projects:
        model.addConstr(
            E[j] <= last_day * Y[j], name=f"C7_selected_upper_{j}"
        )
        model.addConstr(
            E[j] >= first_day * Y[j], name=f"C7_selected_lower_{j}"
        )

    # Extra exact-completion-day definition:
    # A[j,t] = 1 iff project j has work on day t.
    # F[j,t] = 1 iff t is the LAST day with work on project j.
    #
    # F chooses a worked day, and every worked day must be at or before
    # that chosen day. Thus E[j] equals the real last assignment day,
    # even when minimizing completion is not the chosen objective.
    A = {}
    F = {}
    for j in projects:
        # The data loader permits zero required person-days. Such a selected
        # project needs no work, so we conventionally finish it on first_day.
        required_total = sum(
            instance.required_person_days[j, k]
            for k in instance.required_qualifications[j]
        )
        if required_total == 0:
            model.addConstr(
                E[j] == first_day * Y[j], name=f"C7_zero_work_{j}"
            )
            continue

        active_days = [t for t in days if by_project_day[j, t]]
        for t in active_days:
            A[j, t] = model.addVar(
                vtype=GRB.BINARY, name=f"A_{j}_{t}"
            )
            F[j, t] = model.addVar(
                vtype=GRB.BINARY, name=f"F_{j}_{t}"
            )
            daily_work = by_project_day[j, t]
            model.addConstr(
                gp.quicksum(daily_work) <= len(daily_work) * A[j, t],
                name=f"C7_work_upper_{j}_{t}",
            )
            model.addConstr(
                A[j, t] <= gp.quicksum(daily_work),
                name=f"C7_work_lower_{j}_{t}",
            )
            model.addConstr(
                F[j, t] <= A[j, t],
                name=f"C7_last_is_worked_{j}_{t}",
            )

        model.addConstr(
            gp.quicksum(F[j, t] for t in active_days) == Y[j],
            name=f"C7_one_last_day_{j}",
        )
        for t in active_days:
            model.addConstr(
                A[j, t] <= gp.quicksum(
                    F[j, s] for s in active_days if s >= t
                ),
                name=f"C7_no_work_after_last_{j}_{t}",
            )
        model.addConstr(
            E[j] == gp.quicksum(t * F[j, t] for t in active_days),
            name=f"C7_exact_completion_{j}",
        )

    # C8: Professor's original lateness lower bound is preserved.
    # C9: Additional inequalities make lateness exact for selected projects.
    for j in projects:
        deadline = instance.deadline[j]
        max_late = max(0, last_day - deadline)
        max_early = max(0, deadline - first_day)

        model.addConstr(
            L[j] >= E[j] - deadline,
            name=f"C8_{j}",
        )
        model.addConstr(
            W[j] <= Y[j],
            name=f"C9_selected_{j}",
        )
        model.addConstr(
            L[j] <= max_late * W[j],
            name=f"C9_upper_{j}",
        )
        model.addConstr(
            L[j] >= W[j],
            name=f"C9_indicator_{j}",
        )
        # Tight when W=1, relaxed for early / unselected projects.
        model.addConstr(
            L[j] <= (
                E[j] - deadline
                + max_early * (1 - W[j])
                + deadline * (1 - Y[j])
            ),
            name=f"C9_exact_{j}",
        )

    model.update()
    artifacts = ModelArtifacts(
        model=model,
        variables={"X": X, "Y": Y, "E": E, "L": L, "Z": Z, "W": W,
                   "A": A, "F": F},
        instance=instance,
    )
    set_objective(artifacts, objective)
    return artifacts
