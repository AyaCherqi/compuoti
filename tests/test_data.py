from pathlib import Path
import json
import pytest
from compuoti.data import load_instance, validate_instance, Instance


def test_loads_json_object(tmp_path: Path):
    path = tmp_path / "toy.json"
    path.write_text(json.dumps({"example": 1}), encoding="utf-8")
    instance = load_instance(path)
    assert instance.raw == {"example": 1}
    assert validate_instance(instance) == []


def test_rejects_non_object_json(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_instance(path)
