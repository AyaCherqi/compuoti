# CompuOpti

Multi-objective project selection and employee scheduling using Python, Gurobi, and the ε-constraint method.

CompuOpti selects projects and assigns qualified employees to project tasks over a fixed planning horizon. The optimization balances net profit, project completion dates, employee–project relationships, and late deliveries.

## Features

- Mixed-integer linear programming (MILP) model with optional project selection
- Employee skill, daily capacity, and vacation constraints
- Project qualification coverage and deadline penalties
- Four optimization criteria
- ε-constraint search and Pareto dominance filtering
- JSON exports and readable result summaries
- Synthetic instance generation
- Streamlit dashboard for objective-space and schedule visualizations

## Optimization objectives

| Objective | Direction | Definition |
| --- | --- | --- |
| `financial` | Maximize | Total gains from completed projects minus lateness penalties |
| `completion` | Minimize | Sum of completion-day indices of selected projects |
| `relationships` | Minimize | Number of distinct employee–project assignments |
| `late_projects` | Minimize | Number of projects delivered late |

The model supports rejecting projects when staffing capacity is insufficient. The multi-objective solver maximizes `financial` subject to varying bounds on the other three criteria, then filters dominated results. The reported Pareto set is sampled, not an exhaustive enumeration.

## Project structure

```text
compuoti/
├── app.py                       # Streamlit results dashboard
├── show_pareto_summary.py      # Compact results summaries
├── data/
│   ├── instances/              # Toy, medium, and large JSON instances
│   └── README.md               # Dataset schema
├── results/                    # Pareto JSON outputs and summaries
├── src/compuoti/
│   ├── data.py                  # Data loading and validation
│   ├── generate.py              # Synthetic instance generator
│   ├── model.py                 # MILP model and objective definitions
│   ├── solve.py                 # Single-objective solver and export
│   ├── multiobjective.py        # ε-constraint optimization
│   └── pareto.py                # Dominance and Pareto filtering
├── tests/                       # Automated tests
├── pyproject.toml
└── requirements.txt
```

## Requirements

- Python 3.10+
- Gurobi Optimizer with a valid license

## Installation

### Windows (PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,dashboard]"
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,dashboard]'
```

## Usage

### Single-objective optimization

```bash
python -m compuoti.solve --instance data/instances/toy_instance.json --objective financial --output results/toy_single.json
```

Available objectives: `financial`, `completion`, `relationships`, `late_projects`.

### Multi-objective optimization

```bash
python -m compuoti.multiobjective --instance data/instances/toy_instance.json --grid-levels 3 --min-selected 1 --output results/toy_pareto.json
```

`--grid-levels` controls the number of ε values explored per constrained objective. `--min-selected 1` requires at least one completed project; omit it to allow an empty project portfolio.

### Results summaries

```bash
python show_pareto_summary.py --results results/toy_pareto.json
python show_pareto_summary.py --results results/medium_pareto.json
python show_pareto_summary.py --results results/large_pareto.json
```

### Dashboard

```bash
streamlit run app.py
```

The dashboard displays objective trade-offs, selected projects, deadlines, and employee assignments by day.

### Generate a dataset

```bash
python -m compuoti.generate --employees 5 --projects 15 --horizon 22 --skills 5 --seed 42 --output data/generated/benchmark_42.json
```

### Run tests

```bash
python -m pytest -v
```

## Output format

Multi-objective runs write a JSON file containing ε-grid statistics and a list of sampled nondominated solutions. Each solution includes:

- `objective_values`: net profit, completion score, relationship count, and late-project count
- `projects`: selected projects, completion dates, lateness, and assigned employees
- `assignments`: employee, project, qualification, and workday

The `financial` value is net profit after late penalties. The `completion` value is the sum of project completion-day indices, **not** elapsed project duration or overall makespan.

## Datasets

The repository includes the original toy, medium, and large JSON instances. Additional instances can be generated with a fixed random seed for reproducible experiments.

## License

Gurobi is a separately licensed dependency. Use is subject to the terms of the installed Gurobi license.
