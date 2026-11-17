"""MILP model construction.

Build the model only after data.py normalizes the course JSON format.
Notation follows the course formulation:
X[i,j,k,t] employee/project/qualification/day assignment
Y[j] project selection
E[j] project completion day
L[j] number of late days

Candidate multi-objective extensions:
Z[i,j] employee-project indicator
W[j] late-project indicator
U[j,t] project completion-day indicator
T overall makespan (if makespan is the agreed time objective)
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelArtifacts:
    model: Any
    variables: dict[str, Any]


def build_model(instance, *, include_makespan: bool = True) -> ModelArtifacts:
    """Create variables and constraints from a normalized Instance.

    TODO implementation order:
      1. Create gurobipy.Model.
      2. Create X, Y, E, L variables.
      3. Add professor baseline constraints:
         - at most one assignment per employee/day
         - no assignments during leave
         - qualification compatibility
         - required person-days and project selection
         - completion-day and lateness definitions
      4. Add and link Z, W, U, and optionally T.
      5. Set one objective at a time for epsilon-constraint runs.

    Do not use guessed JSON fields here. Keep the model independent from raw JSON.
    """
    raise NotImplementedError(
        "Implement after the JSON schema and final mathematical formulation are confirmed."
    )
