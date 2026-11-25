
from pathlib import Path

import pytest
from gurobipy import GRB

from compuoti.data import load_instance, validate_instance
from compuoti.model import build_model


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "instances"


@pytest.mark.parametrize(
    "filename",
    [
        "toy_instance.json",
        "medium_instance.json",
        "large_instance.json",
    ],
)
def test_real_data_builds_milp(filename):
    """Check that every real dataset loads and builds the MILP."""

    instance = load_instance(DATA_DIR / filename)

    assert validate_instance(instance) == []

    artifacts = build_model(instance, objective="financial")

    try:
        assert artifacts.model.NumVars > 0
        assert artifacts.model.NumConstrs > 0
        assert len(artifacts.variables["Y"]) == len(instance.projects)
        assert len(artifacts.variables["E"]) == len(instance.projects)
        assert len(artifacts.variables["Z"]) == (
            len(instance.employees) * len(instance.projects)
        )
    finally:
        artifacts.model.dispose()


def test_toy_dataset_optimization():
    """Solve the toy dataset and report its actual solver status."""

    instance = load_instance(DATA_DIR / "toy_instance.json")
    artifacts = build_model(instance, objective="financial")

    try:
        artifacts.model.optimize()

        assert artifacts.model.Status in (
            GRB.OPTIMAL,
            GRB.INFEASIBLE,
        )

        if artifacts.model.Status == GRB.OPTIMAL:
            assert artifacts.model.SolCount > 0
            print("Toy dataset objective:", artifacts.model.ObjVal)

        elif artifacts.model.Status == GRB.INFEASIBLE:
            print("Toy dataset is infeasible.")
            artifacts.model.computeIIS()
            artifacts.model.write("infeasible_model.ilp")
            print("IIS saved to infeasible_model.ilp")

    finally:
        artifacts.model.dispose()
