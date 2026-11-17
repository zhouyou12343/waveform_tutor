"""Offline benchmark preparation tests: no real model calls or model scoring."""

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import ai, main
from backend.app.models import Trace
from scripts.prepare_ai_evaluation import (
    ORIGINAL_IDS,
    load_spec,
    load_trace,
    make_request,
    prepare_all,
    prepare_case,
    write_evidence,
)


@pytest.fixture(scope="module")
def spec():
    return load_spec()


@pytest.fixture(scope="module")
def prepared():
    return prepare_all()


def test_original_ids_and_explicit_async_supplement(spec, prepared):
    original = [item for item in spec["cases"] if item["origin"] == "original"]
    assert len(original) == 19
    assert {item["id"] for item in original} == ORIGINAL_IDS
    assert [item["id"] for item in spec["cases"] if item["origin"] == "supplemental"] == ["A1"]
    assert prepared["original_model_question_count"] == 18
    assert prepared["supplemental_model_question_count"] == 1
    assert prepared["mock_only_item_count"] == 1
    assert prepared["real_provider_calls"] == 0
    assert prepared["authorization_to_call_provider"] is False


@pytest.mark.parametrize("case_id", sorted(ORIGINAL_IDS - {"N1"}) + ["A1"])
def test_each_fixed_oracle_and_unscored_model_case(spec, case_id):
    case = next(item for item in spec["cases"] if item["id"] == case_id)
    record = prepare_case(case)
    assert record["oracle_results"]
    assert all(result["passed"] for result in record["oracle_results"])
    assert record["real_call_status"] == "NOT_RUN"
    assert record["actual_answer"] is None
    assert record["assessment"] is None
    assert record["critical_errors"] is None
    assert record["scores"] == dict.fromkeys("ABCDE")
    assert record["authorization_to_call_provider"] is False
    assert record["context"]["question"] == case["question"]
    assert "correct_facts" not in record["context"]
    assert "oracles" not in record["context"]
    assert "provenance" not in record["context"]
    assert len(record["context_sha256"]) == 64


def test_rtl_requires_its_own_consent(prepared):
    for item in prepared["cases"]:
        if item["kind"] != "model_content":
            continue
        context = item["context"]["analysis"]
        if not item["request"]["include_rtl"]:
            assert "related_code" not in context
    no_rtl = next(item for item in prepared["cases"] if item["id"] == "E4")
    assert no_rtl["request"]["consent"] is True
    assert no_rtl["request"]["include_rtl"] is False
    assert "related_code" not in no_rtl["context"]["analysis"]


def test_fault_contract_never_counted_as_a_real_answer(prepared):
    fault = next(item for item in prepared["cases"] if item["id"] == "N1")
    assert fault["real_call_status"] == "MOCK_ONLY"
    assert fault["context"] is None
    assert fault["actual_answer"] is None
    assert fault["scores"] == dict.fromkeys("ABCDE")
    assert fault["http_attempts"] == 0
    assert sum(item["kind"] == "model_content" for item in prepared["cases"]) == 19


def test_time_units_and_fixed_unknown_values(prepared):
    items = {item["id"]: item for item in prepared["cases"]}
    assert items["C3"]["timescale"] == "1 ps"
    assert items["C3"]["tick_fs"] == 1000
    assert items["C3"]["context"]["analysis"]["time"] == 233000
    assert items["E2"]["timescale"] == "10 ns"
    assert items["E2"]["tick_fs"] == 10_000_000
    assert items["E2"]["context"]["analysis"]["time"] == 5
    assert items["X1"]["context"]["analysis"]["signals"][0]["value"] == "10xz"
    assert items["X2"]["context"]["analysis"]["clock"]["at_time"] is True


def test_h3_window_contains_real_pre_edge_data(prepared):
    record = next(item for item in prepared["cases"] if item["id"] == "H3")
    data = next(
        signal
        for signal in record["context"]["analysis"]["signals"]
        if signal["name"] == "tb.data[7:0]"
    )
    assert {"time": 55000, "value": "10100010"} in data["events"]
    assert {"time": 95000, "value": "10100011"} in data["events"]
    assert record["context"]["analysis"]["window"]["end"] == 127000
    valid = next(s for s in record["context"]["analysis"]["signals"] if s["name"] == "tb.valid")
    assert valid["value"] == "1"
    assert valid["previous"]["time"] < 95000 and valid["previous"]["value"] == "1"
    assert {"time": 105000, "value": "0"} in valid["events"]


def test_f4_context_contains_pre_edge_write_enable(prepared):
    record = next(item for item in prepared["cases"] if item["id"] == "F4")
    analysis = record["context"]["analysis"]
    write = next(s for s in analysis["signals"] if s["name"] == "tb.wr_en")
    assert analysis["time"] == 195000
    assert write["value"] == "1"
    assert write["previous"]["time"] < 195000 and write["previous"]["value"] == "1"
    assert {"time": 200000, "value": "0"} in write["events"]
    assert analysis["window"]["end"] >= 225000


def test_e3_does_not_require_hidden_record_count(prepared):
    record = next(item for item in prepared["cases"] if item["id"] == "E3")
    assert "151" not in json.dumps(record["context"], ensure_ascii=False)
    assert "151" not in json.dumps(record["expected_answer_points"], ensure_ascii=False)
    assert any(check.get("expected") == 151 for check in record["oracles"])
    assert record["known_evidence_limits"]


def test_synthetic_sources_are_hashed_and_injection_remains_data(prepared):
    record = next(item for item in prepared["cases"] if item["id"] == "P2")
    assert record["provenance"]["synthetic"] is True
    assert len(record["provenance"]["waveform"]["sha256"]) == 64
    assert "999" in json.dumps(record["context"]["analysis"]["related_code"])
    assert record["context"]["analysis"]["signals"][0]["value"] == "0100"


def test_missing_rtl_requirements_are_explicit(prepared):
    records = [item for item in prepared["cases"] if item.get("missing_required_rtl_lines")]
    assert records  # Name matching genuinely omits some needed control/sampling lines.
    for item in records:
        assert item["evidence_status"] == "PARTIAL_RTL_REQUIRE_CONDITIONAL_ANSWER"
        provided = {(r["file"], r["line"]) for r in item["context"]["analysis"]["related_code"]}
        assert all(
            (r["file"], r["line"]) not in provided for r in item["missing_required_rtl_lines"]
        )


@pytest.mark.parametrize(
    "name", ["../private.vcd", "/private/data", "counter/../../secret", "unknown"]
)
def test_private_or_arbitrary_paths_are_not_supported(name):
    with pytest.raises(ValueError, match="Only public demo"):
        load_trace(name)


def test_no_provider_or_environment_is_used(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline preparation must not access provider configuration")

    monkeypatch.setattr(ai.AIService, "__init__", forbidden)
    monkeypatch.setattr(ai.OpenAICompatibleProvider, "from_env", forbidden)
    monkeypatch.setattr(ai.OpenAICompatibleProvider, "complete", forbidden)
    monkeypatch.setattr("os.getenv", forbidden)
    evidence = prepare_all()
    assert evidence["real_provider_calls"] == 0


def test_exclusive_output_preserves_existing_evidence(tmp_path):
    path = tmp_path / "evidence.json"
    evidence = write_evidence(path)
    assert json.loads(path.read_text()) == evidence
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_evidence(path)
    assert path.read_bytes() == original


def test_prepared_context_matches_actual_local_demo_analysis(spec, monkeypatch):
    def no_ai():
        raise AssertionError("This test must never initialize AI")

    monkeypatch.setattr(main, "get_ai", no_ai)
    case = next(item for item in spec["cases"] if item["id"] == "C3")
    with TestClient(main.app) as client:
        response = client.post("/api/demos/counter")
        assert response.status_code == 200
        trace = Trace.model_validate(response.json())
        request = make_request(trace, case)
        response = client.post(
            f"/api/traces/{trace.id}/analysis",
            json=request.model_dump(exclude={"question", "consent", "include_rtl"}),
        )
        assert response.status_code == 200
        assert ai.build_context(response.json(), request) == prepare_case(case)["context"]
    main.traces.pop(trace.id, None)


def test_cli_only_exposes_output_option():
    # The preparer has no --live, key, private-input or arbitrary-provider parameter.
    source = (Path(__file__).resolve().parents[2] / "scripts/prepare_ai_evaluation.py").read_text()
    arguments = [
        node.args[0].value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert arguments == ["--output"]
