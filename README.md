# CompuOpti

Multi-objective project selection and employee scheduling using Mixed-Integer Linear Programming (MILP), Gurobi, and the epsilon-constraint method.

## Project status

Early development: repository structure and implementation interfaces are prepared. The mathematical formulation and JSON data adapter must be validated against the course specification before solving.

## Objectives (to confirm with the project team)

1. Maximize financial performance: project gains minus delay penalties.
2. Minimize portfolio makespan (or another agreed completion-time measure).
3. Minimize employee–project relationships.
4. Minimize the number of late projects.

The last three objectives are multi-objective extensions. Confirm the exact interpretation with the professor/team before treating them as final.

## Repository structure

```text
compuoti/
├── app.py
├── data/
│   ├── README.md
│   └── instances/          # Put toy/medium/large JSON instances here
├── docs/
│   ├── mathematical_model.md
│   └── decisions.md
├── notebooks/
├── outputs/                # Generated results (not committed)
├── src/compuoti/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── model.py
│   ├── solve.py
│   └── pareto.py
├── tests/
│   ├── conftest.py
│   ├── test_data.py
│   └── test_model.py
├── .env.example
├── .gitignore
├── pyproject.toml
└── requirements.txt
```

## Setup

### 1. Requirements

- Python 3.10 or newer
- Git
- A Gurobi installation and a valid academic license for optimization runs

### 2. Create and activate a virtual environment

**macOS/Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

If Gurobi is not yet available, install the Python package with `pip install gurobipy`, then configure and test your academic license according to Gurobi's official instructions. A package installation alone does not provide a solver license.

### 4. Add the supplied instances

Copy the course-provided files into `data/instances/` and use these names:

- `toy_instance.json`
- `medium_instance.json`
- `large_instance.json`

Do not commit private, licensed, or restricted data. These sample files are normally fine for a course repository, but check your course rules first.

### 5. Inspect the data

```bash
python -m compuoti.solve --instance data/instances/toy_instance.json --validate-only
```

The JSON adapter is intentionally a TODO until its schema has been checked. Do not guess key names: document the real schema in `data/README.md`.

### 6. Run tests

```bash
pytest
```

### 7. Run the application (starter)

```bash
streamlit run app.py
```

## Mathematical model

Read [`docs/mathematical_model.md`](docs/mathematical_model.md). It records the current candidate notation and explicitly flags decisions that still need validation.

## Team workflow

- `main`: stable, reviewed code.
- `dev`: integration branch (optional for a small team).
- Feature branches: `feature/data-loader`, `feature/milp-model`, `feature/pareto`, `feature/dashboard`.
- Open a Pull Request for changes to `main`.
- Add tests with each feature; do not commit `.env`, virtual environments, solver logs, or generated outputs.

## Reproducibility

Record the instance name, solver status, objective values, solver version, runtime, and model settings for every experiment. Store generated schedules under `outputs/` locally; commit only small, anonymized result summaries when appropriate.
