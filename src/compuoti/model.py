"""MILP model for the CompuOpti employee/project scheduling problem."""

from dataclasses import dataclass
from typing import Any

import gurobipy as gp
from gurobipy import GRB


@dataclass
class ModelArtifacts:
    model: Any
    variables: dict[str, Any]
    instance: Any


def build_model(instance, objective: str = "financial") -> ModelArtifacts:
    """
    Build the CompuOpti MILP.

    Expected normalized Instance attributes:
        days: list[int]
        employees: list[str]
        projects: list[str]
        qualifications: list[str]
        employee_qualifications: dict[employee, set[qualification]]
        leave_days: dict[employee, set[day]]
        required_qualifications: dict[project, set[qualification]]
        required_person_days: dict[(project, qualification), int]
        gain: dict[project, float]
        late_penalty: dict[project, float]
        deadline: dict[project, int]

    Invalid assignments (unqualified employees and leave days) are
    excluded when creating X variables.
    """

    days = instance.days
    employees = instance.employees
    projects = instance.projects

    horizon = max(days)

    model = gp.Model("CompuOpti")

    # --------------------------------------------------
    # 1. Decision variables
    # --------------------------------------------------

    X = {}

    for i in employees:
        for j in projects:
            for k in instance.required_qualifications[j]:
                if k not in instance.employee_qualifications[i]:
                    continue

                for t in days:
                    if t in instance.leave_days[i]:
                        continue

                    X[i, j, k, t] = model.addVar(
                        vtype=GRB.BINARY,
                        name=f"X_{i}_{j}_{k}_{t}",
                    )

    Y = {
        j: model.addVar(vtype=GRB.BINARY, name=f"Y_{j}")
        for j in projects
    }

    E = {
        j: model.addVar(
            vtype=GRB.INTEGER,
            lb=min(days),
            ub=horizon,
            name=f"E_{j}",
        )
        for j in projects
    }

    L = {
        j: model.addVar(
            vtype=GRB.INTEGER,
            lb=0,
            name=f"L_{j}",
        )
        for j in projects
    }

    Z = {
        (i, j): model.addVar(
            vtype=GRB.BINARY,
            name=f"Z_{i}_{j}",
        )
        for i in employees
        for j in projects
    }

    W = {
        j: model.addVar(
            vtype=GRB.BINARY,
            name=f"W_{j}",
        )
        for j in projects
    }

    model.update()

    # --------------------------------------------------
    # 2. Constraints
    # --------------------------------------------------

    # C1: At most one assignment per employee per day.
    for i in employees:
        for t in days:
            model.addConstr(
                gp.quicksum(
                    var
                    for (ii, j, k, tt), var in X.items()
                    if ii == i and tt == t
                ) <= 1,
                name=f"C1_{i}_{t}",
            )

    # C2 and C3: Leave days and qualification compatibility.
    # Invalid variables are not created, so these restrictions
    # are enforced directly by the variable index set.

    # C4: Required person-days, using the professor's two inequalities.
    for j in projects:
        for k in instance.required_qualifications[j]:
            assignments = gp.quicksum(
                var
                for (i, jj, kk, t), var in X.items()
                if jj == j and kk == k
            )

            required = instance.required_person_days[j, k]

            model.addConstr(
                Y[j] * required <= assignments,
                name=f"C4_lower_{j}_{k}",
            )

            model.addConstr(
                assignments <= required,
                name=f"C4_upper_{j}_{k}",
            )

    # C5: All projects are mandatory.
    for j in projects:
        Y[j].LB = 1
        Y[j].UB = 1

    # C6: Link Z to assignments in both directions.
    for i in employees:
        for j in projects:
            for (ii, jj, k, t), var in X.items():
                if ii == i and jj == j:
                    model.addConstr(
                        var <= Z[i, j],
                        name=f"C6_link_{i}_{j}_{k}_{t}",
                    )

            model.addConstr(
                Z[i, j] <= gp.quicksum(
                    var
                    for (ii, jj, k, t), var in X.items()
                    if ii == i and jj == j
                ),
                name=f"C6_reverse_{i}_{j}",
            )

    # C7: Completion date cannot precede any assignment.
    for (i, j, k, t), var in X.items():
        model.addConstr(
            E[j] >= t * var,
            name=f"C7_{i}_{j}_{k}_{t}",
        )

    # C8 and C9: Exact lateness and late-project indicator.
    for j in projects:
        deadline = instance.deadline[j]
        big_m = max(0, horizon - deadline)

        model.addConstr(
            L[j] >= E[j] - deadline,
            name=f"C8_{j}",
        )

        model.addConstr(
            L[j] <= big_m * W[j],
            name=f"C9_upper_{j}",
        )

        model.addConstr(
            L[j] >= W[j],
            name=f"C9_indicator_{j}",
        )

        model.addConstr(
            L[j] <= E[j] - deadline + big_m * (1 - W[j]),
            name=f"C9_exact_{j}",
        )

    model.update()

    variables = {
        "X": X,
        "Y": Y,
        "E": E,
        "L": L,
        "Z": Z,
        "W": W,
    }

    artifacts = ModelArtifacts(
        model=model,
        variables=variables,
        instance=instance,
    )
    set_objective(artifacts, objective)

    return artifacts


def set_objective(artifacts: ModelArtifacts, objective: str) -> None:
    """Set one of the four agreed objectives."""

    model = artifacts.model
    variables = artifacts.variables

    Y = variables["Y"]
    E = variables["E"]
    L = variables["L"]
    Z = variables["Z"]
    W = variables["W"]

    instance = artifacts.instance

    if objective == "financial":
        expression = gp.quicksum(
            instance.gain[j] * Y[j]
            - instance.late_penalty[j] * L[j]
            for j in instance.projects
        )
        model.setObjective(expression, GRB.MAXIMIZE)

    elif objective == "completion":
        expression = gp.quicksum(E[j] for j in instance.projects)
        model.setObjective(expression, GRB.MINIMIZE)

    elif objective == "relationships":
        expression = gp.quicksum(Z[i, j] for i in instance.employees for j in instance.projects)
        model.setObjective(expression, GRB.MINIMIZE)

    elif objective == "late_projects":
        expression = gp.quicksum(W[j] for j in instance.projects)
        model.setObjective(expression, GRB.MINIMIZE)

    else:
        raise ValueError(f"Unknown objective: {objective}")
