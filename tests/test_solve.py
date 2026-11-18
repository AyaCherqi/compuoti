
"""Tests for the CompuOpti solver."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from compuoti.data import instance_from_dict, validate_instance
from compuoti.solve import (
    OBJECTIVES,
    calculate_objective_values,
    export_solution,
    solve_instance,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "instances"


@pytest.fixture
def feasible_toy_instance():
    """Create a feasible copy of the toy dataset without changing the original."""

    with (DATA_DIR / "toy_instance.json").open(
        encoding="utf-8"
    ) as file:
        original_data = json.load(file)

    data = deepcopy(original_data)

    # Make Liam available on day 1.
    # This gives the instance 14 available employee-days.
    data["staff"][1]["vacations"].remove(1)

    instance = instance_from_dict(data)

    errors = validate_instance(instance)
    assert not errors, f"Invalid test instance: {errors}"

    return instance


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_solve_toy_instance_all_objectives(
    feasible_toy_instance,
    objective,
):
    """Check that every objective can solve the feasible toy instance."""

    result = solve_instance(
        feasible_toy_instance,
        objective=objective,
    )

    assert result["status_name"] == "OPTIMAL"
    assert result["objective_selected"] == objective
    assert result["objective_values"] is not None

    assert set(result["objective_values"]) == set(OBJECTIVES)

    assert len(result["projects"]) == len(feasible_toy_instance.projects)
    assert len(result["assignments"]) > 0


def test_objective_values_are_non_negative_for_toy_instance(
    feasible_toy_instance,
):
    """Check the basic ranges of the calculated objective values."""

    result = solve_instance(
        feasible_toy_instance,
        objective="financial",
    )

    values = result["objective_values"]

    assert values["completion"] > 0
    assert values["relationships"] > 0
    assert values["late_projects"] >= 0
    assert isinstance(values["financial"], float)


def test_completion_dates_match_last_assignments(
    feasible_toy_instance,
):
    """Check that project completion dates match their last assignments."""

    result = solve_instance(
        feasible_toy_instance,
        objective="financial",
    )

    for project in result["projects"]:
        project_id = project["project_id"]

        project_days = [
            assignment["day"]
            for assignment in result["assignments"]
            if assignment["project_id"] == project_id
        ]

        assert project_days
        assert project["completion_day"] == max(project_days)


def test_invalid_objective_is_rejected(feasible_toy_instance):
    """Check that an unsupported objective raises ValueError."""

    with pytest.raises(ValueError, match="Unknown objective"):
        solve_instance(
            feasible_toy_instance,
            objective="unknown",
        )


def test_solution_can_be_exported_to_json(feasible_toy_instance, tmp_path):
    """Check that a solution can be exported as a JSON file."""

    result = solve_instance(
        feasible_toy_instance,
        objective="financial",
    )

    output_file = tmp_path / "solution.json"

    saved_path = export_solution(result, output_file)

    assert saved_path.exists()
    assert saved_path == output_file
    assert saved_path.stat().st_size > 0

    with saved_path.open(encoding="utf-8") as file:
        saved_result = json.load(file)

    assert saved_result["status_name"] == "OPTIMAL"
