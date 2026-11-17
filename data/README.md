
# CompuOpti — Data Layer

## Purpose

This module loads and validates the JSON datasets used by
the CompuOpti scheduling optimization model.

## Available datasets

| Dataset | Employees | Projects | Horizon |
|---------|-----------|----------|---------|
| Toy     | 3         | 5        | 5 days  |
| Medium  | 5         | 15       | 22 days |
| Large   | 6         | 25       | 36 days |

## Data structures

- Employee: ID, name, qualifications, vacation days.
- Project: ID, name, gain, deadline, daily penalty,
  and required person-days per qualification.
- Instance: planning horizon, qualifications,
  employees, and projects.

## Main functions

- `load_instance(path)`: reads a JSON file.
- `instance_from_dict(raw)`: converts JSON data
  into Python objects.
- `validate_instance(instance)`: reports
  structural and basic capacity problems.

## Validation

The loader checks required fields, qualifications,
vacation days, deadlines, gains, penalties,
and project requirements.

Validation does not guarantee that a feasible
schedule exists. Feasibility is determined by Gurobi.

## Running tests

```bash
python -m pytest tests/test_data.py -v
```
