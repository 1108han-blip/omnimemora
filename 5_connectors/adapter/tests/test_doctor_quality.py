import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DOCTOR_PATH = REPO_ROOT / "tools" / "doctor_quality.py"


def load_doctor_module():
    spec = importlib.util.spec_from_file_location("doctor_quality", DOCTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_static_doctor_passes_current_boundary_contract():
    doctor = load_doctor_module()

    checks = doctor.run_omni_doctor() + doctor.run_token_doctor()
    failures = [check for check in checks if check["status"] != "pass"]

    assert failures == []


def test_doctor_json_report_is_observe_only(capsys):
    doctor = load_doctor_module()

    assert doctor.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "omnimemora-doctor-quality-v1"
    assert payload["mode"] == "observe_only"
    assert payload["summary"]["static_errors"] == 0


def test_react_doctor_package_is_pinned_by_default():
    doctor = load_doctor_module()

    assert doctor.REACT_DOCTOR_PACKAGE == "react-doctor@0.1.6"
