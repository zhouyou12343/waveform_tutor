import asyncio
import json

import httpx
import pytest

from backend.app.ai import (
    AI_LIMITATION,
    MAX_RESPONSE_BYTES,
    SYSTEM_PROMPT,
    AIError,
    AIService,
    OpenAICompatibleProvider,
    build_context,
)
from backend.app.models import ExplainRequest

ANALYSIS = {
    "signals": [{"name": "top.q"}],
    "observed_facts": ["q 在时间 10 为 1"],
    "related_code": [
        {
            "file": "top.sv",
            "line": 12,
            "text": "secret RTL",
            "signal": "top.q",
            "match": "name-only",
        }
    ],
}


def result(**updates):
    value = {
        "summary": "可能为寄存器更新",
        "observed_facts": ["fabricated fact"],
        "possible_explanations": ["时钟触发"],
        "related_signals": ["top.q"],
        "related_code": [],
        "suggested_checks": ["检查时钟"],
        "limitations": [],
    }
    value.update(updates)
    return value


def request(**updates):
    return ExplainRequest(
        **{"time": 10, "signals": ["top.q"], "question": "为什么？", "consent": True, **updates}
    )


class MockProvider:
    def __init__(self, output=None, error=None):
        self.output = json.dumps(result()) if output is None else output
        self.error = error
        self.contexts = []

    async def complete(self, context: dict) -> str:
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self.output


def run(awaitable):
    return asyncio.run(awaitable)


def provider(handler, **kwargs):
    return OpenAICompatibleProvider(
        "https://example.test/v1/",
        "test-private-key",
        "arbitrary-model",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_success_and_rtl_not_sent():
    mock = MockProvider()
    service = AIService(mock)
    explanation = run(service.explain(ANALYSIS, request()))
    assert service.configured and service.requests == 1
    assert explanation.observed_facts == ANALYSIS["observed_facts"]
    assert explanation.summary.startswith("推测：")
    assert all(s.startswith("推测：") for s in explanation.possible_explanations)
    assert AI_LIMITATION in explanation.limitations
    assert "related_code" not in mock.contexts[0]["analysis"]
    assert "secret RTL" not in json.dumps(mock.contexts)
    assert "related_code" in ANALYSIS


@pytest.mark.parametrize("length", [3997, 3998, 4000])
def test_summary_prefix_respects_final_limit(length):
    mock = MockProvider(json.dumps(result(summary="长" * length, limitations=["限制"] * 32)))
    value = run(AIService(mock).explain(ANALYSIS, request()))
    assert value.summary == "推测：" + "长" * min(length, 3997)
    assert len(value.summary) <= 4000
    assert len(value.limitations) == 32
    assert value.limitations[-1] == AI_LIMITATION


def test_summary_over_provider_limit_is_rejected():
    with pytest.raises(AIError):
        run(
            AIService(MockProvider(json.dumps(result(summary="长" * 4001)))).explain(
                ANALYSIS, request()
            )
        )


def test_rtl_opt_in_and_reference():
    mock = MockProvider(json.dumps(result(related_code=["top.sv:12"])))
    value = run(AIService(mock).explain(ANALYSIS, request(include_rtl=True)))
    assert value.related_code == ["top.sv:12"]
    assert mock.contexts[0]["analysis"]["related_code"] == ANALYSIS["related_code"]


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        json.dumps({k: v for k, v in result().items() if k != "summary"}),
        json.dumps(result(summary=42)),
        json.dumps(result(observed_facts=[42])),
        json.dumps(result(extra="forbidden")),
        json.dumps(result(related_signals=["invented"])),
        json.dumps(result(related_code=["unprovided.sv:1"])),
        json.dumps(result(related_code=["top.sv:12"])),
        '{"summary":"first",' + json.dumps(result())[1:],
        "x" * (MAX_RESPONSE_BYTES + 1),
    ],
)
def test_invalid_output(raw):
    with pytest.raises(AIError) as error:
        run(AIService(MockProvider(raw)).explain(ANALYSIS, request()))
    assert error.value.status_code == 502
    assert raw not in error.value.message


def test_consent():
    mock = MockProvider()
    service = AIService(mock)
    with pytest.raises(AIError) as error:
        run(service.explain(ANALYSIS, request(consent=False)))
    assert error.value.status_code == 403
    assert not mock.contexts
    assert service.requests == 1


@pytest.mark.parametrize("missing", ["AI_BASE_URL", "AI_API_KEY", "AI_MODEL", "all"])
def test_missing_configuration(monkeypatch, missing):
    for key, value in {
        "AI_BASE_URL": "https://example.test/v1",
        "AI_API_KEY": "key",
        "AI_MODEL": "model",
    }.items():
        monkeypatch.setenv(key, value)
    for key in ["AI_BASE_URL", "AI_API_KEY", "AI_MODEL"] if missing == "all" else [missing]:
        monkeypatch.delenv(key, raising=False)
    service = AIService()
    assert not service.configured
    with pytest.raises(AIError) as error:
        run(service.explain(ANALYSIS, request()))
    assert error.value.status_code == 503


def test_environment_configuration(monkeypatch):
    for key, value in {
        "AI_BASE_URL": "https://example.test/v1/",
        "AI_API_KEY": "key",
        "AI_MODEL": "custom",
        "AI_TIMEOUT_SECONDS": "2.5",
        "AI_MAX_OUTPUT_TOKENS": "99",
    }.items():
        monkeypatch.setenv(key, value)
    p = OpenAICompatibleProvider.from_env()
    assert p._url == "https://example.test/v1/chat/completions"
    assert p._timeout == 2.5 and p._max_tokens == 99
    assert AIService().configured
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "nan")
    with pytest.raises(AIError):
        OpenAICompatibleProvider.from_env()


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.test",
        "http://example.test/v1",
        "https://user:password@example.test",
        "https://example.test?q=x",
        "https://example.test#fragment",
        "https://example.test?",
        "https://example.test#",
        "https:///missing",
        "https://example.test:bad",
        "https://example.test\n",
    ],
)
def test_invalid_base_url(url):
    with pytest.raises(AIError) as error:
        OpenAICompatibleProvider(url, "key", "model")
    assert error.value.status_code == 503


def test_http_payload_and_response(monkeypatch):
    # A configured environment proxy must never be used.
    monkeypatch.setenv("HTTPS_PROXY", "http://invalid-proxy.invalid:1")
    calls = []

    def handler(req):
        calls.append(req)
        assert str(req.url) == "https://example.test/v1/chat/completions"
        assert req.method == "POST"
        assert req.headers["authorization"] == "Bearer test-private-key"
        payload = json.loads(req.content)
        assert "response_format" not in payload
        assert payload["stream"] is False
        assert payload["model"] == "arbitrary-model"
        assert "不可信" in payload["messages"][0]["content"]
        assert "secret RTL" not in payload["messages"][1]["content"]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(result())}}]}
        )

    run(AIService(provider(handler)).explain(ANALYSIS, request()))
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["timeout", 429, 502, 503])
@pytest.mark.parametrize("recover", [False, True])
def test_retries(monkeypatch, failure, recover):
    calls = []
    sleeps = []

    async def sleep(delay):
        assert 0 <= delay < 1
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    def handler(req):
        calls.append(req)
        if recover and len(calls) == 2:
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(result())}}]}
            )
        if failure == "timeout":
            raise httpx.ReadTimeout("private raw body", request=req)
        return httpx.Response(failure, text="private raw body")

    service = AIService(provider(handler))
    if recover:
        run(service.explain(ANALYSIS, request()))
    else:
        with pytest.raises(AIError) as error:
            run(service.explain(ANALYSIS, request()))
        assert error.value.status_code == (504 if failure == "timeout" else 503)
        assert "private" not in error.value.message
    assert len(calls) == 2 and len(sleeps) == 1
    assert service.requests == 1


@pytest.mark.parametrize("status", [301, 307, 400, 401, 500])
def test_no_redirect_or_other_status_retry(status, caplog):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            status, headers={"location": "https://other.test"}, text="secret body"
        )

    with pytest.raises(AIError) as error:
        run(AIService(provider(handler)).explain(ANALYSIS, request()))
    assert len(calls) == 1
    assert "secret body" not in str(error.value)
    assert "secret body" not in caplog.text and "test-private-key" not in caplog.text


@pytest.mark.parametrize(
    "body", [b"bad JSON", b"{}", b'{"choices":[]}', b'{"choices":[{"message":{"content":123}}]}']
)
def test_invalid_http_response(body):
    with pytest.raises(AIError):
        run(provider(lambda req: httpx.Response(200, content=body)).complete({}))


def test_stream_size_limit():
    class Chunks(httpx.AsyncByteStream):
        def __init__(self):
            self.count = 0
            self.closed = False

        async def __aiter__(self):
            for _ in range(100):
                self.count += 1
                yield b"x" * 8192

        async def aclose(self):
            self.closed = True

    stream = Chunks()
    with pytest.raises(AIError, match="大小限制"):
        run(provider(lambda req: httpx.Response(200, stream=stream)).complete({}))
    assert stream.count == MAX_RESPONSE_BYTES // 8192 + 1
    assert stream.closed


def test_cancellation_propagates():
    service = AIService(MockProvider(error=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        run(service.explain(ANALYSIS, request()))
    assert service.requests == 1


def test_http_cancellation_propagates():
    calls = []

    def handler(req):
        calls.append(req)
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        run(AIService(provider(handler)).explain(ANALYSIS, request()))
    assert len(calls) == 1


def test_network_unavailable():
    calls = []

    def handler(req):
        calls.append(req)
        raise httpx.ConnectError("secret headers", request=req)

    with pytest.raises(AIError) as error:
        run(provider(handler).complete({}))
    assert error.value.status_code == 503 and len(calls) == 1
    assert "secret" not in str(error.value)


def test_provider_errors_are_sanitized(caplog):
    with pytest.raises(AIError) as error:
        run(AIService(MockProvider(error=RuntimeError("secret-key"))).explain(ANALYSIS, request()))
    assert "secret-key" not in str(error.value) + caplog.text


def test_context_builder_is_allowlisted_and_copies_data():
    original = {**ANALYSIS, "sources": "private full project", "local_path": "/private/path"}
    context = build_context(original, request())
    assert "sources" not in context["analysis"]
    assert "local_path" not in context["analysis"]
    assert "related_code" not in context["analysis"]
    context["analysis"]["signals"][0]["name"] = "changed"
    assert original["signals"][0]["name"] == "top.q"
    assert (
        build_context(original, request(include_rtl=True))["analysis"]["related_code"]
        == ANALYSIS["related_code"]
    )


@pytest.mark.parametrize("failure", ["timeout", 429, 502, 503])
def test_single_attempt_does_not_retry(failure):
    calls = []

    def handler(req):
        calls.append(req)
        if failure == "timeout":
            raise httpx.ReadTimeout("private", request=req)
        return httpx.Response(failure)

    p = provider(handler, max_attempts=1, request_budget=2)
    with pytest.raises(AIError) as error:
        run(p.complete({}))
    assert error.value.status_code == (504 if failure == "timeout" else 503)
    assert len(calls) == p.http_attempts == 1


def test_budget_blocks_before_third_http_attempt():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(result())}}]}
        )

    p = provider(handler, max_attempts=1, request_budget=2)
    service = AIService(p)
    run(service.explain(ANALYSIS, request()))
    run(service.explain(ANALYSIS, request()))
    with pytest.raises(AIError, match="预算") as error:
        run(service.explain(ANALYSIS, request()))
    assert error.value.status_code == 429
    assert service.requests == 3
    assert service.http_attempts == len(calls) == 2


def test_retry_also_consumes_budget():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503)

    p = provider(handler, request_budget=1)
    with pytest.raises(AIError, match="预算"):
        run(p.complete({}))
    assert len(calls) == p.http_attempts == 1


def test_budget_is_reserved_before_concurrent_io():
    calls = []

    async def handler(req):
        calls.append(req)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    p = provider(handler, max_attempts=1, request_budget=2)

    async def concurrent():
        return await asyncio.gather(*(p.complete({}) for _ in range(5)), return_exceptions=True)

    values = run(concurrent())
    assert len(calls) == p.http_attempts == 2
    assert sum(isinstance(value, AIError) for value in values) == 3


def test_cancelled_http_attempt_still_consumes_budget():
    def handler(req):
        raise asyncio.CancelledError

    p = provider(handler, request_budget=1)
    with pytest.raises(asyncio.CancelledError):
        run(p.complete({}))
    assert p.http_attempts == 1
    with pytest.raises(AIError, match="预算"):
        run(p.complete({}))


def test_no_consent_uses_no_http_budget():
    def handler(req):
        pytest.fail("No consent must never reach transport")

    service = AIService(provider(handler, request_budget=1))
    with pytest.raises(AIError) as error:
        run(service.explain(ANALYSIS, request(consent=False)))
    assert error.value.status_code == 403
    assert service.http_attempts == 0


@pytest.mark.parametrize(
    "options",
    [
        {"max_attempts": 0},
        {"max_attempts": 3},
        {"max_attempts": True},
        {"request_budget": 0},
        {"request_budget": -1},
        {"request_budget": True},
    ],
)
def test_invalid_attempt_configuration(options):
    with pytest.raises(AIError):
        provider(lambda req: httpx.Response(200), **options)


def test_budget_environment_configuration(monkeypatch):
    for name, value in {
        "AI_BASE_URL": "https://example.test/v1",
        "AI_API_KEY": "test-key",
        "AI_MODEL": "test-model",
        "AI_MAX_ATTEMPTS": "1",
        "AI_REQUEST_BUDGET": "2",
    }.items():
        monkeypatch.setenv(name, value)
    p = OpenAICompatibleProvider.from_env()
    assert p._max_attempts == 1 and p._request_budget == 2
    monkeypatch.setenv("AI_REQUEST_BUDGET", "invalid")
    with pytest.raises(AIError):
        OpenAICompatibleProvider.from_env()


def test_truncated_completion_is_not_accepted_even_when_json_is_valid():
    p = provider(
        lambda req: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": json.dumps(result())},
                    }
                ]
            },
        )
    )
    with pytest.raises(AIError, match="长度限制"):
        run(AIService(p).explain(ANALYSIS, request()))
    assert p.http_attempts == 1


def responses_envelope(text=None, **updates):
    value = {
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": json.dumps(result()) if text is None else text}
                ],
            }
        ],
    }
    value.update(updates)
    return value


@pytest.mark.parametrize("include_rtl", [False, True])
def test_responses_payload_and_complete_explanation(include_rtl):
    calls = []

    def handler(req):
        calls.append(req)
        assert str(req.url) == "https://example.test/v1/responses"
        assert req.headers["authorization"] == "Bearer test-private-key"
        payload = json.loads(req.content)
        assert set(payload) == {
            "model",
            "instructions",
            "input",
            "max_output_tokens",
            "store",
            "stream",
        }
        assert payload["model"] == "arbitrary-model"
        assert payload["instructions"] == SYSTEM_PROMPT
        assert payload["max_output_tokens"] == 321
        assert payload["store"] is False and payload["stream"] is False
        assert payload["input"][0]["role"] == "user"
        assert payload["input"][0]["content"][0]["type"] == "input_text"
        context = json.loads(payload["input"][0]["content"][0]["text"])
        assert context == build_context(ANALYSIS, request(include_rtl=include_rtl))
        assert ("related_code" in context["analysis"]) == include_rtl
        return httpx.Response(200, json=responses_envelope())

    p = provider(handler, api_format="responses", max_output_tokens=321)
    value = run(AIService(p).explain(ANALYSIS, request(include_rtl=include_rtl)))
    assert value.observed_facts == ANALYSIS["observed_facts"]
    assert value.summary.startswith("推测：")
    assert AI_LIMITATION in value.limitations
    assert len(calls) == p.http_attempts == 1


def test_responses_skips_reasoning_and_combines_text_parts():
    text = json.dumps(result())
    body = responses_envelope(text[:12])
    body["output"][0]["content"].append({"type": "output_text", "text": text[12:]})
    body["output"].insert(
        0, {"type": "reasoning", "summary": [{"type": "summary_text", "text": "not a user answer"}]}
    )
    body["output_text"] = "not a raw REST answer"
    p = provider(lambda req: httpx.Response(200, json=body), api_format="responses")
    assert run(p.complete({})) == text


@pytest.mark.parametrize(
    "status", [None, "incomplete", "failed", "queued", "in_progress", "cancelled"]
)
def test_responses_rejects_unfinished_status_even_with_valid_text(status):
    p = provider(
        lambda req: httpx.Response(200, json=responses_envelope(status=status)),
        api_format="responses",
    )
    with pytest.raises(AIError, match="完整解释"):
        run(p.complete({}))
    assert p.http_attempts == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        None,
        responses_envelope(error={"message": "private provider error"}),
        responses_envelope(incomplete_details={"reason": "max_output_tokens"}),
        responses_envelope(output=[]),
        responses_envelope(output={}),
        responses_envelope(output=[None]),
        responses_envelope(output=[{"type": "reasoning", "summary": []}]),
        responses_envelope(
            output=[{"type": "message", "role": "user", "status": "completed", "content": []}]
        ),
        responses_envelope(
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "incomplete",
                    "content": [{"type": "output_text", "text": "{}"}],
                }
            ]
        ),
        responses_envelope(
            output=[
                {"type": "message", "role": "assistant", "status": "completed", "content": "{}"}
            ]
        ),
        responses_envelope(
            output=[{"type": "message", "role": "assistant", "status": "completed", "content": []}]
        ),
        responses_envelope(
            output=[
                {"type": "message", "role": "assistant", "status": "completed", "content": [None]}
            ]
        ),
        responses_envelope(
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": 123}],
                }
            ]
        ),
        responses_envelope(
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "input_text", "text": "{}"}],
                }
            ]
        ),
        responses_envelope(text="   "),
        responses_envelope(output=[], output_text=json.dumps(result())),
    ],
)
def test_responses_malformed_envelopes_are_sanitized(body, caplog):
    p = provider(
        lambda req: httpx.Response(200, content=json.dumps(body).encode()), api_format="responses"
    )
    with pytest.raises(AIError) as exc:
        run(p.complete({}))
    assert exc.value.status_code == 502
    assert "private provider error" not in str(exc.value) + caplog.text
    assert "test-private-key" not in str(exc.value) + caplog.text
    assert p.http_attempts == 1


def test_responses_refusal_is_not_accepted_as_explanation(caplog):
    body = responses_envelope()
    body["output"][0]["content"].append({"type": "refusal", "refusal": "private refusal body"})
    p = provider(lambda req: httpx.Response(200, json=body), api_format="responses")
    with pytest.raises(AIError, match="拒绝") as exc:
        run(p.complete({}))
    assert "private refusal body" not in str(exc.value) + caplog.text


@pytest.mark.parametrize(
    "tool_type", ["function_call", "web_search_call", "computer_call", "custom_tool_call"]
)
def test_responses_does_not_accept_or_execute_tool_output(tool_type):
    body = responses_envelope()
    body["output"].insert(0, {"type": tool_type, "arguments": "private untrusted command"})
    p = provider(lambda req: httpx.Response(200, json=body), api_format="responses")
    with pytest.raises(AIError, match="不支持"):
        run(p.complete({}))
    assert p.http_attempts == 1


@pytest.mark.parametrize(
    "text",
    [
        "not JSON",
        json.dumps(result(related_signals=["invented"])),
        json.dumps(result(related_code=["private.sv:1"])),
    ],
)
def test_responses_still_requires_application_schema_and_allowlists(text):
    p = provider(
        lambda req: httpx.Response(200, json=responses_envelope(text)), api_format="responses"
    )
    with pytest.raises(AIError):
        run(AIService(p).explain(ANALYSIS, request()))


def test_responses_multiple_json_messages_are_not_silently_discarded():
    body = responses_envelope()
    body["output"].append(responses_envelope()["output"][0])
    p = provider(lambda req: httpx.Response(200, json=body), api_format="responses")
    with pytest.raises(AIError):
        run(AIService(p).explain(ANALYSIS, request()))


@pytest.mark.parametrize("api_format", ["chat_completions", "responses"])
def test_duplicate_envelope_fields_are_rejected(api_format):
    body = '{"status":"completed","status":"incomplete",' + json.dumps(responses_envelope())[1:]
    if api_format == "chat_completions":
        body = '{"choices":[],"choices":[{"message":{"content":"{}"}}]}'
    p = provider(lambda req: httpx.Response(200, content=body), api_format=api_format)
    with pytest.raises(AIError, match="格式无效"):
        run(p.complete({}))


@pytest.mark.parametrize("api_format", ["responses", "chat_completions"])
def test_protocol_mismatch_does_not_try_another_endpoint(api_format):
    body = (
        {"choices": [{"message": {"content": json.dumps(result())}}]}
        if api_format == "responses"
        else responses_envelope()
    )
    p = provider(lambda req: httpx.Response(200, json=body), api_format=api_format)
    with pytest.raises(AIError):
        run(p.complete({}))
    assert p.http_attempts == 1


@pytest.mark.parametrize(
    "value", ["", "auto", "chat/completions", "response", "Responses", None, True, []]
)
def test_unknown_api_format_is_rejected(value):
    with pytest.raises(AIError, match="配置无效"):
        provider(lambda req: httpx.Response(200), api_format=value)


def test_responses_environment_configuration(monkeypatch):
    for name, value in {
        "AI_BASE_URL": "https://example.test/v1/",
        "AI_API_KEY": "test-key",
        "AI_MODEL": "custom",
        "AI_API_FORMAT": "responses",
        "AI_MAX_ATTEMPTS": "1",
        "AI_REQUEST_BUDGET": "2",
    }.items():
        monkeypatch.setenv(name, value)
    p = OpenAICompatibleProvider.from_env()
    assert p._url == "https://example.test/v1/responses"
    assert p._api_format == "responses" and p._max_attempts == 1
    assert p._request_budget == 2
    monkeypatch.setenv("AI_API_FORMAT", "unknown")
    assert AIService().configured is False


def test_responses_consent_and_budget_never_bypass_transport_guard():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=responses_envelope())

    p = provider(handler, api_format="responses", max_attempts=1, request_budget=2)
    service = AIService(p)
    with pytest.raises(AIError) as exc:
        run(service.explain(ANALYSIS, request(consent=False)))
    assert exc.value.status_code == 403 and not calls
    for _ in range(2):
        run(service.explain(ANALYSIS, request()))
    with pytest.raises(AIError, match="预算"):
        run(service.explain(ANALYSIS, request()))
    assert service.http_attempts == len(calls) == 2


@pytest.mark.parametrize("failure", ["timeout", "network", "cancelled", 401, 429, 502, 503])
def test_responses_failure_contract_with_single_attempt(failure, caplog):
    def handler(req):
        if failure == "timeout":
            raise httpx.ReadTimeout("private failure", request=req)
        if failure == "network":
            raise httpx.ConnectError("private failure", request=req)
        if failure == "cancelled":
            raise asyncio.CancelledError
        return httpx.Response(failure, text="private failure")

    p = provider(handler, api_format="responses", max_attempts=1, request_budget=2)
    if failure == "cancelled":
        with pytest.raises(asyncio.CancelledError):
            run(p.complete({}))
    else:
        with pytest.raises(AIError) as exc:
            run(p.complete({}))
        assert "private failure" not in str(exc.value) + caplog.text
    assert p.http_attempts == 1


def test_responses_retry_uses_same_endpoint_and_counts_attempts():
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return (
            httpx.Response(503)
            if len(calls) == 1
            else httpx.Response(200, json=responses_envelope())
        )

    p = provider(handler, api_format="responses", request_budget=2)
    run(AIService(p).explain(ANALYSIS, request()))
    assert calls == ["https://example.test/v1/responses"] * 2
    assert p.http_attempts == 2


def test_responses_size_limit_and_streaming_mismatch():
    for body in (b"x" * (MAX_RESPONSE_BYTES + 1), b'data: {"type":"response.completed"}\n\n'):
        p = provider(lambda req: httpx.Response(200, content=body), api_format="responses")
        with pytest.raises(AIError):
            run(p.complete({}))
        assert p.http_attempts == 1
