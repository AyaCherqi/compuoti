"""Command-line entry point for instance validation and optimization."""

import argparse
from .data import load_instance, validate_instance


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CompuOpti on a JSON instance.")
    parser.add_argument("--instance", required=True, help="Path to a course JSON instance.")
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Load and run input checks without constructing the MILP."
    )
    args = parser.parse_args()

    instance = load_instance(args.instance)
    errors = validate_instance(instance)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(f"Loaded instance: {instance.source}")
    if args.validate_only:
        print("Basic JSON validation passed. Schema-specific checks are still TODO.")
        return

    from .model import build_model
    artifacts = build_model(instance)
    artifacts.model.optimize()


if __name__ == "__main__":
    main()
