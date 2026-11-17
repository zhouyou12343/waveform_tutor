"""First-round harness tests use only temporary fake keys and MockTransport."""

import asyncio
import json

import httpx
import pytest

from scripts import qa_real_ai_smoke as smoke


def envelope(text="CONNECTIVITY_OK: Mock transport, no waveform claim"):
    explanation = {
        "summary": text,
        "observed_facts": [],
        "possible_explanations": [],
        "related_signals": [],
        "related_code": [],
        "suggested_checks": [],
        "limitations": [],
    }
    return {
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": "gpt-5.6-sol",
        "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps(explanation)}],
            }
        ],
    }


def test_key_read_only_named_file_and_no_eval(tmp_path):
    p = tmp_path / ".env.4router.local"
    p.write_text("AI_API_KEY=fake-key-for-unit-test\n")
    p.chmod(0o600)
    assert smoke.load_key(tmp_path) == "fake-key-for-unit-test"
    p.write_text("AI_API_KEY=fake-key-for-unit-test\nEXTRA=should-not-be-read\n")
    with pytest.raises(ValueError):
        smoke.load_key(tmp_path)


@pytest.mark.parametrize("mode", [0o644, 0o660, 0o666])
def test_unsafe_key_permissions_rejected(tmp_path, mode):
    p = tmp_path / ".env.4router.local"
    p.write_text("AI_API_KEY=fake-key-for-unit-test\n")
    p.chmod(mode)
    with pytest.raises(ValueError):
        smoke.load_key(tmp_path)


def test_key_symlink_rejected(tmp_path):
    p = tmp_path / "unrelated.txt"
    p.write_text("not a credential")
    (tmp_path / ".env.4router.local").symlink_to(p)
    with pytest.raises(OSError):
        smoke.load_key(tmp_path)


def test_reservations_persist_across_invocations_and_hold_budget(tmp_path):
    smoke.reserve(tmp_path, "A")
    with pytest.raises(ValueError):
        smoke.reserve(tmp_path, "A")
    with pytest.raises(ValueError):
        smoke.reserve(tmp_path, "B")
    smoke.save_new(tmp_path / "result-A.json", {"outcome": "SUCCESS"})
    smoke.reserve(tmp_path, "B")
    assert len(smoke.prior_reservations(tmp_path)) == 2
    with pytest.raises(ValueError):
        smoke.reserve(tmp_path, "B")


def test_default_preflight_never_reads_key_or_network(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline default must not touch credential or transport")

    monkeypatch.setattr(smoke, "load_key", forbidden)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", forbidden)
    monkeypatch.setattr(smoke, "check_authorization", lambda root: {})
    monkeypatch.setattr("sys.argv", ["qa_real_ai_smoke.py"])
    smoke.main()
    assert json.loads(capsys.readouterr().out)["real_requests"] == 0


def test_live_flag_required_before_key_read(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "check_authorization", lambda root: {})
    monkeypatch.setattr("sys.argv", ["qa_real_ai_smoke.py", "--stage", "A"])
    with pytest.raises(ValueError, match="explicit authorization"):
        smoke.main()


def test_transport_reserves_before_io_and_refuses_payload_change(tmp_path):
    calls = []
    key = "fake-key-for-unit-test"
    payload = {"model": smoke.MODEL}

    async def handler(request):
        assert (tmp_path / "reservation-A.json").exists()
        calls.append(request)
        return httpx.Response(200, json=envelope())

    record = {}
    transport = smoke.AuditTransport(
        httpx.MockTransport(handler), tmp_path, "A", payload, record, key
    )

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ValueError):
                await client.post(smoke.ENDPOINT, json={"model": "other"})
            assert not calls
            await client.post(smoke.ENDPOINT, json=payload)

    asyncio.run(run())
    assert len(calls) == 1
    assert record["http_status"] == 200


def test_non_success_response_capture_is_bounded_and_redacted(tmp_path):
    key = "fake-key-for-unit-test"
    body = {"error": {"code": "unsupported_parameter", "message": "never show " + key}}
    record = {}
    transport = smoke.AuditTransport(
        httpx.MockTransport(lambda req: httpx.Response(400, json=body)),
        tmp_path,
        "A",
        {},
        record,
        key,
    )

    async def run():
        request = httpx.Request("POST", smoke.ENDPOINT, json={})
        response = await transport.handle_async_request(request)
        assert response.status_code == 400
        await transport.aclose()

    asyncio.run(run())
    assert key not in json.dumps(record)
    assert record["error"]["code"] == "unsupported_parameter"
    assert record["http_attempt_reserved"] is True


def test_real_harness_a_uses_mock_and_redacts_persisted_response(tmp_path):
    key = "fake-key-for-unit-test"
    output = tmp_path / "evidence"
    output.mkdir()
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=envelope("CONNECTIVITY_OK " + key))
    )
    result = asyncio.run(smoke.execute_stage(tmp_path, output, "A", key, transport))
    assert result["outcome"] == "SUCCESS"
    assert result["real_provider"] is False
    assert result["remaining_authorized_attempts"] == 1
    assert all(key not in p.read_text() for p in output.glob("*.json"))


def test_counter_business_uses_actual_demo_without_rtl(tmp_path):
    from backend.app import main

    output = tmp_path / "evidence"
    output.mkdir()
    smoke.reserve(output, "A")
    smoke.save_new(output / "result-A.json", {"outcome": "SUCCESS"})
    data = (main.EXAMPLES["counter"] / "trace.vcd").read_bytes()
    p = tmp_path / "examples/counter/trace.vcd"
    p.parent.mkdir(parents=True)
    p.write_bytes(data)
    calls = []

    def handler(req):
        payload = json.loads(req.content)
        context = json.loads(payload["input"][0]["content"][0]["text"])
        assert "related_code" not in context["analysis"]
        signals = {s["name"]: s for s in context["analysis"]["signals"]}
        assert signals["tb.count[3:0]"]["value"] == "1010"
        assert signals["tb.enable"]["value"] == "0"
        assert context["analysis"]["timescale"] == "1 ps"
        calls.append(req)
        return httpx.Response(200, json=envelope("Only a unit-test mock"))

    result = asyncio.run(
        smoke.execute_stage(
            tmp_path, output, "B", "fake-key-for-unit-test", httpx.MockTransport(handler)
        )
    )
    assert result["outcome"] == "SUCCESS"
    assert result["local_api_status"] == 200
    assert result["remaining_authorized_attempts"] == 0
    assert len(calls) == 1
    assert len(result["independent_expected_values"]) == 6


def test_a_failure_is_recorded_without_retry_and_blocks_b(tmp_path):
    output = tmp_path / "evidence"
    output.mkdir()
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("private error content")

    record = asyncio.run(
        smoke.execute_stage(
            tmp_path, output, "A", "fake-key-for-unit-test", httpx.MockTransport(handler)
        )
    )
    assert record["outcome"] == "FAILED_PROVIDER_OR_VALIDATION"
    assert len(calls) == 1
    assert "private error content" not in (output / "result-A.json").read_text()
    with pytest.raises(ValueError):
        smoke.validate_stage(output, "B")


def test_reasoning_and_secrets_not_exported():
    key = "fake-key-for-unit-test"
    response = envelope()
    response["output"].insert(
        0, {"type": "reasoning", "summary": [{"text": "private reasoning " + key}]}
    )
    record = {}
    smoke.describe_response(json.dumps(response), record, key)
    assert "private reasoning" not in json.dumps(record)
    assert "CONNECTIVITY_OK" in record["provider_explanation_untrusted"]["summary"]


def test_scrub_before_truncate_and_decode_json_escapes():
    key = "test-key-private-fragment-123456"
    escaped = "".join("\\u%04x" % ord(c) for c in key)
    response = envelope("CONNECTIVITY_OK " + key)
    response["output"][0]["content"][0]["text"] = response["output"][0]["content"][0][
        "text"
    ].replace(key, escaped)
    response["model"] = "x" * 195 + key
    response["error"] = {"message": "x" * 995 + key}
    record = {}
    smoke.describe_response(json.dumps(response), record, key)
    saved = json.dumps(record)
    assert key not in saved and "test-key-private" not in saved
    assert "[REDACTED]" in saved
    assert escaped not in saved


def test_invalid_assistant_json_is_not_written_raw():
    response = envelope()
    response["output"][0]["content"][0]["text"] = "broken body with sensitive non-json details"
    record = {}
    smoke.describe_response(json.dumps(response), record, "test-key-private-fragment")
    assert record["provider_explanation_valid_json"] is False
    assert "broken body" not in json.dumps(record)


def test_no_project_root_override(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["qa_real_ai_smoke.py", "--project-root", str(tmp_path)])
    with pytest.raises(SystemExit):
        smoke.main()


def test_save_new_syncs_directory_before_dispatch(tmp_path, monkeypatch):
    synced = []
    original = smoke.sync_directory

    def sync(path):
        synced.append(path)
        original(path)

    monkeypatch.setattr(smoke, "sync_directory", sync)
    output = tmp_path / "new-evidence"
    smoke.reserve(output, "A")
    assert tmp_path in synced and output in synced
    assert (output / "reservation-A.json").exists()
