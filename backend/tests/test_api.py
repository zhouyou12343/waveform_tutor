import asyncio
import json
import threading
from io import BytesIO

import httpx
import pytest
from fastapi import HTTPException, Request, UploadFile
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.ai import AIService
from backend.app.main import app, traces
from backend.tests.test_parser import HEADER


@pytest.fixture
def client(monkeypatch):
    for name in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    traces.clear()
    app.state.ai = AIService()
    with TestClient(app) as client:
        yield client


def test_invalid_ai_configuration_does_not_break_offline(client, monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("AI_MODEL", "mock")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "invalid")
    app.state.ai = AIService()
    assert client.get("/api/health").json()["ai_configured"] is False
    assert client.post("/api/demos/counter").status_code == 200


def test_full_offline_flow(client):
    assert client.get("/api/health").json()["ai_configured"] is False
    trace = client.post("/api/demos/counter").json()
    assert trace["timescale"] == "1 ps"
    assert len(trace["sources"]) == 2
    signals = {signal["name"]: signal["id"] for signal in trace["signals"]}
    body = {
        "time": 120000,
        "signals": [signals["tb.count[3:0]"], signals["tb.enable"]],
        "clock": signals["tb.clk"],
        "window": 20000,
    }
    response = client.post(f"/api/traces/{trace['id']}/analysis", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["signals"][0]["value"] == "1010"
    assert result["clock"]["previous"] == 115000
    assert result["clock"]["next"] == 125000
    assert result["related_code"]
    report = client.post(f"/api/traces/{trace['id']}/report", json=body)
    assert report.status_code == 200
    assert "1010" in report.text
    response = client.post(
        f"/api/traces/{trace['id']}/explain", json=body | {"question": "Why?", "consent": True}
    )
    assert response.status_code == 503
    assert client.post(f"/api/traces/{trace['id']}/analysis", json=body).status_code == 200


def test_upload_sanitizes_filename_without_disk_access(client):
    response = client.post("/api/traces", files={"file": ("../../test.vcd", HEADER + b"0!\nbx #")})
    assert response.status_code == 200
    trace = response.json()
    assert trace["name"] == "test.vcd"
    response = client.post(
        f"/api/traces/{trace['id']}/sources", files={"file": ("../a.sv", "module a; endmodule")}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "a.sv"
    assert (
        client.post(
            f"/api/traces/{trace['id']}/sources", files={"file": ("a.sv", "module b; endmodule")}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    ("name", "data", "status"),
    [
        ("a.vcd", b"", 422),
        ("a.txt", HEADER, 422),
        ("a.vcd", b"bad", 422),
        ("a.vcd", b" " * (8 * 1024 * 1024 + 1), 413),
    ],
)
def test_bad_upload(client, name, data, status):
    assert client.post("/api/traces", files={"file": (name, data)}).status_code == status


def test_local_security_and_limits(client):
    assert (
        client.post("/api/demos/counter", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert (
        client.post(
            "/api/traces",
            content=b"x" * (8 * 1024 * 1024 + 65537),
            headers={"Content-Type": "multipart/form-data; boundary=x"},
        ).status_code
        == 413
    )
    assert client.post("/api/demos/counter", content=b"x" * 32769).status_code == 413
    assert client.post("/api/demos/not-a-demo").status_code == 404
    assert (
        client.post("/api/traces/absent/analysis", json={"time": 0, "signals": ["s0"]}).status_code
        == 404
    )


def test_explicit_ai_consent(client):
    trace = client.post("/api/demos/counter").json()
    body = {"time": 0, "signals": ["s0"], "question": "why"}
    response = client.post(f"/api/traces/{trace['id']}/explain", json=body)
    assert response.status_code == 403


def test_mock_ai_api(client):
    class MockProvider:
        async def complete(self, context):
            assert "related_code" not in context["analysis"]
            return json.dumps(
                {
                    "summary": "需要检查enable",
                    "observed_facts": ["model invented fact"],
                    "possible_explanations": ["使能可能关闭"],
                    "related_signals": ["tb.count[3:0]"],
                    "related_code": [],
                    "suggested_checks": ["查看RTL"],
                    "limitations": [],
                }
            )

    app.state.ai = AIService(provider=MockProvider())
    trace = client.post("/api/demos/counter").json()
    response = client.post(
        f"/api/traces/{trace['id']}/explain",
        json={"time": 120000, "signals": ["s0"], "question": "为什么", "consent": True},
    )
    assert response.status_code == 200
    assert "1010" in response.json()["observed_facts"][0]
    assert "model invented fact" not in str(response.json())
    assert client.get("/api/health").json()["requests"] == 1


def test_responses_mock_transport_through_real_counter_analysis(client):
    from backend.app.ai import OpenAICompatibleProvider
    from backend.tests.test_ai import responses_envelope, result

    calls = []

    def handler(req):
        calls.append(req)
        assert req.url.path == "/v1/responses"
        body = json.loads(req.content)
        context = json.loads(body["input"][0]["content"][0]["text"])
        assert "related_code" not in context["analysis"]
        assert context["analysis"]["signals"][0]["name"] == "tb.count[3:0]"
        assert context["analysis"]["signals"][0]["value"] == "1010"
        return httpx.Response(
            200, json=responses_envelope(json.dumps(result(related_signals=["tb.count[3:0]"])))
        )

    provider = OpenAICompatibleProvider(
        "https://example.test/v1",
        "fake-test-key",
        "test-model",
        api_format="responses",
        max_attempts=1,
        request_budget=1,
        transport=httpx.MockTransport(handler),
    )
    app.state.ai = AIService(provider)
    trace = client.post("/api/demos/counter").json()
    response = client.post(
        f"/api/traces/{trace['id']}/explain",
        json={"time": 120000, "signals": ["s0"], "question": "为什么", "consent": True},
    )
    assert response.status_code == 200
    assert "1010" in response.json()["observed_facts"][0]
    assert "fabricated fact" not in str(response.json())
    assert len(calls) == client.get("/api/health").json()["provider_http_attempts"] == 1


@pytest.mark.asyncio
async def test_api_cancellation_releases_provider_and_slot():
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class SlowProvider:
        async def complete(self, context):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    app.state.ai = AIService(provider=SlowProvider())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        trace = (await client.post("/api/demos/counter")).json()
        task = asyncio.create_task(
            client.post(
                f"/api/traces/{trace['id']}/explain",
                json={"time": 0, "signals": ["s0"], "question": "why", "consent": True},
            )
        )
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()
        assert not app.state.ai_busy


@pytest.mark.asyncio
async def test_disconnected_upload_does_not_evict_traces(monkeypatch):
    traces.clear()
    for _ in range(4):
        main.remember(main.parse_vcd(HEADER, "existing.vcd"))
    previous = list(traces.items())
    parsed = False
    original = main.parse_vcd

    def parse(*args):
        nonlocal parsed
        trace = original(*args)
        parsed = True
        return trace

    async def receive():
        assert parsed
        return {"type": "http.disconnect"}

    monkeypatch.setattr(main, "parse_vcd", parse)
    upload = UploadFile(filename="new.vcd", file=BytesIO(HEADER))
    with pytest.raises(HTTPException) as exc:
        await main.upload_trace(Request({"type": "http"}, receive), upload)
    assert exc.value.status_code == 499
    assert list(traces.items()) == previous
    assert upload.file.closed


def test_busy_rejects_before_analysis(client, monkeypatch):
    def unexpected(*args):
        pytest.fail("busy request must not analyze")

    monkeypatch.setattr(main, "run_analysis", unexpected)
    monkeypatch.setattr(app.state, "ai_busy", True, raising=False)
    response = client.post(
        "/api/traces/absent/explain",
        json={"time": 0, "signals": ["s0"], "question": "why", "consent": True},
    )
    assert response.status_code == 429


@pytest.mark.parametrize("failure", [HTTPException(422, "invalid"), RuntimeError("failed")])
@pytest.mark.asyncio
async def test_analysis_failure_releases_slot(monkeypatch, failure):
    def fail(*args):
        raise failure

    async def receive():
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "run_analysis", fail)
    monkeypatch.setattr(app.state, "ai_busy", False, raising=False)
    from backend.app.models import ExplainRequest

    with pytest.raises(type(failure)):
        await main.explain(
            "trace",
            ExplainRequest(time=0, signals=["s0"], question="why"),
            Request({"type": "http"}, receive),
        )
    assert not app.state.ai_busy


@pytest.mark.asyncio
async def test_analysis_thread_holds_busy_until_cancelled_work_finishes(monkeypatch):
    from backend.app.models import ExplainRequest

    entered = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    main_thread = threading.get_ident()

    def slow(*args):
        assert threading.get_ident() != main_thread
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return None, {}

    async def receive():
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "run_analysis", slow)
    monkeypatch.setattr(app.state, "ai_busy", False, raising=False)
    body = ExplainRequest(time=0, signals=["s0"], question="why")
    task = asyncio.create_task(main.explain("trace", body, Request({"type": "http"}, receive)))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(HTTPException) as exc:
            await main.explain("trace", body, Request({"type": "http"}, receive))
        assert exc.value.status_code == 429
        assert app.state.ai_busy
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not app.state.ai_busy


@pytest.mark.asyncio
async def test_disconnect_during_analysis_prevents_first_provider_dispatch(monkeypatch):
    from backend.app.models import ExplainRequest

    disconnected = threading.Event()
    calls = []

    def prepare(*args):
        disconnected.set()
        return None, {"observed_facts": [], "signals": []}

    class Provider:
        async def complete(self, context):
            calls.append(context)
            pytest.fail("A disconnect before dispatch must not reach provider")

    async def receive():
        if disconnected.is_set():
            return {"type": "http.disconnect"}
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "run_analysis", prepare)
    monkeypatch.setattr(app.state, "ai", AIService(Provider()), raising=False)
    monkeypatch.setattr(app.state, "ai_busy", False, raising=False)
    with pytest.raises(HTTPException) as error:
        await main.explain(
            "trace",
            ExplainRequest(time=0, signals=["s0"], question="why", consent=True),
            Request({"type": "http"}, receive),
        )
    assert error.value.status_code == 499
    assert calls == []
    assert app.state.ai.requests == 0
    assert not app.state.ai_busy


def test_health_separates_logical_requests_from_transport_attempts(client):
    health = client.get("/api/health").json()
    assert health["requests"] == 0 and health["provider_http_attempts"] == 0
    assert "AI_API_KEY" not in str(health)


def test_bounded_session_store(client):
    first = client.post("/api/demos/counter").json()
    for _ in range(4):
        assert client.post("/api/demos/counter").status_code == 200
    assert len(traces) == 4
    assert (
        client.post(
            f"/api/traces/{first['id']}/analysis", json={"time": 0, "signals": ["s0"]}
        ).status_code
        == 404
    )


def test_invalid_times_and_rtl(client):
    trace = client.post("/api/demos/counter").json()
    base = f"/api/traces/{trace['id']}"
    for body in (
        {"time": -1, "signals": ["s0"]},
        {"time": True, "signals": ["s0"]},
        {"time": 0.5, "signals": ["s0"]},
        {"time": "0", "signals": ["s0"]},
        {"time": 0, "signals": []},
        {"time": 999999, "signals": ["s0"]},
    ):
        assert client.post(base + "/analysis", json=body).status_code == 422
    assert client.post(base + "/sources", files={"file": ("a.sv", b"\xff")}).status_code == 422
    assert (
        client.post(
            base + "/sources", files={"file": ("a.sv", b"x" * (128 * 1024 + 1))}
        ).status_code
        == 413
    )
