"""Readable summary of CompuOpti epsilon-constraint results."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Summarize CompuOpti Pareto solutions"
    )
    parser.add_argument("--results", default="results/toy_pareto.json")
    parser.add_argument("--instance", default="data/instances/toy_instance.json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    # Automatically determine the dataset name and output path
    results_path = Path(args.results)
    dataset_name = results_path.stem.removesuffix("_pareto")

    output = (
        Path(args.output)
        if args.output
        else results_path.with_name(f"{results_path.stem}_summary.txt")
    )

    with results_path.open(encoding="utf-8") as file:
        data = json.load(file)

    with Path(args.instance).open(encoding="utf-8") as file:
        instance = json.load(file)

    jobs = instance["jobs"]
    solutions = data.get("solutions", [])

    lines = [
        f"COMPUOPTI — {dataset_name.upper()} DATASET: PARETO SUMMARY",
        "=" * 70,
        f"Epsilon combinations checked: {data.get('attempted_combinations', '?')}",
        f"Feasible combinations: {data.get('successful_combinations', '?')}",
        f"Infeasible combinations: {data.get('infeasible_combinations', '?')}",
        f"Sampled nondominated solutions: {len(solutions)}",
        "",
        "Note: Financial = total gain of selected projects - late penalties.",
        "Completion = sum of completion-day values (not calendar duration).",
        "Relationships = distinct employee/project pairs.",
        "",
    ]

    for index, solution in enumerate(solutions, 1):
        scores = solution["objective_values"]

        selected = [
            p for p in solution["projects"]
            if p.get("selected", False)
        ]

        gross = sum(
            float(jobs[int(p["project_id"])]["gain"])
            for p in selected
        )

        penalties = sum(
            int(p["late_days"])
            * float(jobs[int(p["project_id"])]["daily_penalty"])
            for p in selected
        )

        lines.extend([
            f"SOLUTION {index}",
            "-" * 70,
            f"Net profit:         {scores['financial']:.2f}",
            f"Gross project gain: {gross:.2f}",
            f"Late penalties:     {penalties:.2f}",
            f"Completion score:   {scores['completion']:.0f}",
            f"Relationships:      {scores['relationships']:.0f}",
            f"Late projects:      {scores['late_projects']:.0f}",
            "Selected projects:  " + (
                ", ".join(p["project_name"] for p in selected) or "none"
            ),
            "Project details:",
        ])

        for p in selected:
            lines.append(
                f"  - {p['project_name']}: "
                f"finish day {p['completion_day']}, "
                f"late {p['late_days']} day(s), "
                f"employees: {', '.join(p['assigned_employees']) or 'none'}"
            )

        lines.append("")

    report = "\n".join(lines)
    print(report)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report + "\n", encoding="utf-8")

    print(f"Short report saved to: {output}")


if __name__ == "__main__":
    main()