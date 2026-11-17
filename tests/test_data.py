
import pytest

from compuoti.data import (
    load_instance,
    instance_from_dict,
    validate_instance,
)


@pytest.mark.parametrize(
    "filename, expected_projects",
    [
        ("toy_instance.json", 5),
        ("medium_instance.json", 15),
        ("large_instance.json", 25),
    ],
)
def test_load_datasets(filename, expected_projects):
    instance = load_instance(f"data/instances/{filename}")

    assert len(instance.projects) == expected_projects
    assert instance.horizon > 0
    assert len(instance.employees) > 0
    assert validate_instance(instance) == []


def test_missing_required_field():
    invalid_data = {
        "horizon": 5,
        "qualifications": ["A"],
        "staff": [],
        # Missing "jobs"
    }

    with pytest.raises(ValueError, match="Missing top-level keys"):
        instance_from_dict(invalid_data)


def test_invalid_vacation_day():
    invalid_data = {
        "horizon": 5,
        "qualifications": ["A"],
        "staff": [
            {
                "name": "Olivia",
                "qualifications": ["A"],
                "vacations": [10],
            }
        ],
        "jobs": [
            {
                "name": "Job1",
                "gain": 100,
                "due_date": 3,
                "daily_penalty": 10,
                "working_days_per_qualification": {"A": 1},
            }
        ],
    }

    with pytest.raises(ValueError, match="vacations"):
        instance_from_dict(invalid_data)
