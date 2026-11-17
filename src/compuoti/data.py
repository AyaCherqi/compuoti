"""Typed loader and validation for the course JSON instances."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

@dataclass(frozen=True)
class Employee:
    id: int
    name: str
    qualifications: frozenset[str]
    vacations: frozenset[int]

@dataclass(frozen=True)
class Project:
    id: int
    name: str
    gain: float
    due_date: int
    daily_penalty: float
    requirements: dict[str, int]

@dataclass(frozen=True)
class Instance:
    horizon: int
    qualifications: tuple[str, ...]
    employees: tuple[Employee, ...]
    projects: tuple[Project, ...]
    source: Path | None = None

    @property
    def days(self) -> tuple[int, ...]:
        return tuple(range(1, self.horizon + 1))

    @property
    def employee_ids(self) -> tuple[int, ...]:
        return tuple(e.id for e in self.employees)

    @property
    def project_ids(self) -> tuple[int, ...]:
        return tuple(p.id for p in self.projects)

    def employee(self, employee_id: int) -> Employee:
        return self.employees[employee_id]

    def project(self, project_id: int) -> Project:
        return self.projects[project_id]


def instance_from_dict(raw: dict[str, Any], source: Path | None = None) -> Instance:
    """Normalize the observed schema: horizon, qualifications, staff, jobs."""
    if not isinstance(raw, dict):
        raise ValueError("The JSON root must be an object.")
    required = {"horizon", "qualifications", "staff", "jobs"}
    missing = required - raw.keys()
    if missing:
        raise ValueError(f"Missing top-level keys: {sorted(missing)}")
    horizon = raw["horizon"]
    quals = raw["qualifications"]
    staff = raw["staff"]
    jobs = raw["jobs"]
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    if not isinstance(quals, list) or not quals or len(set(quals)) != len(quals):
        raise ValueError("qualifications must be a non-empty list of unique identifiers")
    if not isinstance(staff, list) or not staff:
        raise ValueError("staff must be a non-empty list")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("jobs must be a non-empty list")
    qset = set(quals)
    employees=[]
    for idx, item in enumerate(staff):
        if not isinstance(item, dict):
            raise ValueError(f"staff[{idx}] must be an object")
        for key in ("name", "qualifications", "vacations"):
            if key not in item: raise ValueError(f"staff[{idx}] missing '{key}'")
        eq=set(item["qualifications"])
        if not eq <= qset: raise ValueError(f"staff[{idx}] has unknown qualifications: {eq-qset}")
        vacations=item["vacations"]
        if not isinstance(vacations, list) or any(not isinstance(d,int) or not 1 <= d <= horizon for d in vacations):
            raise ValueError(f"staff[{idx}].vacations must contain days in 1..horizon")
        employees.append(Employee(idx, str(item["name"]), frozenset(eq), frozenset(vacations)))
    projects=[]
    seen_names=set()
    for idx, item in enumerate(jobs):
        if not isinstance(item, dict): raise ValueError(f"jobs[{idx}] must be an object")
        for key in ("name", "gain", "due_date", "daily_penalty", "working_days_per_qualification"):
            if key not in item: raise ValueError(f"jobs[{idx}] missing '{key}'")
        name=str(item["name"])
        if name in seen_names: raise ValueError(f"Duplicate project name: {name}")
        seen_names.add(name)
        req=item["working_days_per_qualification"]
        if not isinstance(req, dict) or not req: raise ValueError(f"jobs[{idx}] requirements must be a non-empty object")
        if not set(req) <= qset: raise ValueError(f"jobs[{idx}] has unknown qualifications: {set(req)-qset}")
        for q,n in req.items():
            if not isinstance(n,int) or n < 0: raise ValueError(f"jobs[{idx}] requirement for {q} must be a non-negative integer")
        due=item["due_date"]
        if not isinstance(due,int) or due < 1: raise ValueError(f"jobs[{idx}].due_date must be a positive integer")
        gain=float(item["gain"]); penalty=float(item["daily_penalty"])
        if gain < 0 or penalty < 0: raise ValueError(f"jobs[{idx}] gain and penalty must be non-negative")
        projects.append(Project(idx,name,gain,due,penalty,{str(k):int(v) for k,v in req.items()}))
    # A skill required by a project must exist in at least one employee; feasibility
    # over time is left to Gurobi because leave/capacity interactions are global.
    return Instance(horizon, tuple(str(q) for q in quals), tuple(employees), tuple(projects), source)


def load_instance(file_path: str | Path) -> Instance:
    """Load and validate a JSON scheduling instance."""
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Instance file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    return instance_from_dict(raw, source=path)


def validate_instance(instance: Instance) -> list[str]:
    """
    Validate the scheduling instance.

    Returns a list of errors.
    An empty list means no validation errors were found.
    """

    errors = []

    # 1. Check planning horizon
    if instance.horizon <= 0:
        errors.append("Planning horizon must be positive.")

    # 2. Check qualifications
    valid_qualifications = set(instance.qualifications)

    if not valid_qualifications:
        errors.append("The qualification list cannot be empty.")

    if len(valid_qualifications) != len(instance.qualifications):
        errors.append("Duplicate qualifications are not allowed.")

    # 3. Check employees
    available_qualifications = set()

    for employee in instance.employees:

        for qualification in employee.qualifications:
            if qualification not in valid_qualifications:
                errors.append(
                    f"Employee {employee.name} has unknown "
                    f"qualification {qualification}."
                )

            available_qualifications.add(qualification)

        for day in employee.vacations:
            if not isinstance(day, int) or not 1 <= day <= instance.horizon:
                errors.append(
                    f"Employee {employee.name} has invalid "
                    f"vacation day {day}."
                )

    # 4. Check projects
    for project in instance.projects:

        if project.due_date <= 0:
            errors.append(
                f"Project {project.name} has an invalid deadline."
            )

        if project.gain < 0:
            errors.append(
                f"Project {project.name} has a negative gain."
            )

        if project.daily_penalty < 0:
            errors.append(
                f"Project {project.name} has a negative penalty."
            )

        for qualification, required_days in project.requirements.items():

            if qualification not in valid_qualifications:
                errors.append(
                    f"Project {project.name} requires unknown "
                    f"qualification {qualification}."
                )

            if not isinstance(required_days, int) or required_days < 0:
                errors.append(
                    f"Project {project.name} has invalid required "
                    f"days for qualification {qualification}."
                )

            if qualification not in available_qualifications:
                errors.append(
                    f"No employee has qualification {qualification}, "
                    f"required by project {project.name}."
                )

    return errors

