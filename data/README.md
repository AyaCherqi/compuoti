# Input data

Copy the provided `toy_instance.json`, `medium_instance.json`, and `large_instance.json` into `data/instances/`.

Before writing the parser:
1. Inspect all three JSON files.
2. Record their exact top-level keys and nested fields here.
3. Check whether all instances share the same schema.
4. Validate data types, index conventions (0-based vs 1-based), day horizon, qualification identifiers, and deadline units.
5. Keep a normalized internal representation in `src/compuoti/data.py`.

Do not modify the original course files. Keep an untouched copy for reproducibility.
