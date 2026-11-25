
from types import SimpleNamespace

import pytest

from compuoti.model import build_model

from gurobipy import GRB


@pytest.fixture
def sample_instance():
    return SimpleNamespace(
        days=[1, 2, 3],
        employees=["Alice", "Bob"],
        projects=["Project1"],
        qualifications=["Python", "SQL"],
        employee_qualifications={
            "Alice": {"Python"},
            "Bob": {"SQL"},
        },
        leave_days={
            "Alice": {2},
            "Bob": set(),
        },
        required_qualifications={
            "Project1": {"Python", "SQL"},
        },
        required_person_days={
            ("Project1", "Python"): 1,
            ("Project1", "SQL"): 1,
        },
        gain={"Project1": 1000},
        late_penalty={"Project1": 100},
        deadline={"Project1": 2},
    )


def test_variables_are_created_correctly(sample_instance):
    artifacts = build_model(sample_instance)

    try:
        variables = artifacts.variables

        assert len(variables["Y"]) == 1
        assert len(variables["E"]) == 1
        assert len(variables["L"]) == 1
        assert len(variables["Z"]) == 2
        assert len(variables["W"]) == 1

    finally:
        artifacts.model.dispose()


def test_incompatible_and_leave_assignments_are_excluded(sample_instance):
    artifacts = build_model(sample_instance)

    try:
        X = artifacts.variables["X"]

        # Alice cannot perform SQL.
        assert not any(i == "Alice" and k == "SQL" for i, j, k, t in X)

        # Bob cannot perform Python.
        assert not any(i == "Bob" and k == "Python" for i, j, k, t in X)

        # Alice is on leave on day 2.
        assert not any(i == "Alice" and t == 2 for i, j, k, t in X)

    finally:
        artifacts.model.dispose()



def test_projects_are_optional(sample_instance):
    artifacts = build_model(sample_instance)

    try:
        y = artifacts.variables["Y"]["Project1"]

        # A project can be rejected or selected.
        assert y.LB == 0
        assert y.UB == 1
        assert y.VType == GRB.BINARY

    finally:
        artifacts.model.dispose()



def test_all_four_objectives_are_available(sample_instance):
    objectives = [
        "financial",
        "completion",
        "relationships",
        "late_projects",
    ]

    for objective in objectives:
        artifacts = build_model(sample_instance, objective=objective)

        try:
            assert artifacts.model.NumVars > 0
            assert artifacts.model.NumConstrs > 0

        finally:
            artifacts.model.dispose()


def test_invalid_objective_raises_error(sample_instance):
    from compuoti.model import set_objective

    artifacts = build_model(sample_instance)

    try:
        with pytest.raises(ValueError):
            set_objective(artifacts, "unknown")

    finally:
        artifacts.model.dispose()


def test_rejected_project_has_no_work(sample_instance):
    artifacts = build_model(sample_instance, objective="financial")

    try:
        model = artifacts.model
        variables = artifacts.variables
        j = "Project1"

        # Force the project to be rejected.
        variables["Y"][j].LB = 0
        variables["Y"][j].UB = 0

        model.optimize()

        assert model.Status == GRB.OPTIMAL

        # Rejected projects have no completion or lateness.
        assert variables["E"][j].X == pytest.approx(0)
        assert variables["L"][j].X == pytest.approx(0)
        assert variables["W"][j].X == pytest.approx(0)

        # No assignments are allowed for a rejected project.
        for (i, project, k, t), x in variables["X"].items():
            if project == j:
                assert x.X == pytest.approx(0)

    finally:
        artifacts.model.dispose()


def test_selected_project_covers_requirements(sample_instance):
    artifacts = build_model(sample_instance, objective="financial")

    try:
        model = artifacts.model
        variables = artifacts.variables
        j = "Project1"

        # Force the project to be selected.
        variables["Y"][j].LB = 1
        variables["Y"][j].UB = 1

        model.optimize()

        assert model.Status == GRB.OPTIMAL

        for qualification in sample_instance.required_qualifications[j]:
            assigned_days = sum(
                x.X
                for (i, project, k, t), x in variables["X"].items()
                if project == j and k == qualification
            )

            required_days = sample_instance.required_person_days[
                j, qualification
            ]

            assert assigned_days == pytest.approx(required_days)

        assert variables["E"][j].X >= 1

    finally:
        artifacts.model.dispose()

