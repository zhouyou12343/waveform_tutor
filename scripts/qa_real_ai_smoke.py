"""Bounded first-round AI acceptance; default is offline, never a batch runner.

Only --stage A/B plus --live-authorized can send, using the recorded two-call
consent and exactly .env.4router.local in this script's project. Never prints a key.
There is no CLI override for the project, credential path or budget ledger.
Each stage is single-use; reservation files count even an interrupted attempt.
"""

import argparse
import asyncio
import fcntl
import hashlib
import json
import logging
import os
import re
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = "https://4router.net/v1"
ENDPOINT = BASE + "/responses"
MODEL = "gpt-5.6-sol"
LIMIT = 2
TOKEN_LIMIT = 2048
EVIDENCE_NAME = "ai-live-smoke-20261117"
AUTH_PATH = "docs/qa/evidence/ai-responses-20261117/first-round-authorization.json"
QUESTION_A = "这是最小连通性检查，不含波形数据。请按规定JSON格式简短回答，summary包含CONNECTIVITY_OK，明确没有波形可分析，信号与代码引用数组为空。"
QUESTION_B = "仅依据实际波形记录回答：120000 tick时enable和4位count是多少？125000、135000、145000 tick的count保持还是增加？155000 tick时是多少？请按给定timescale换算ns；未提供RTL，不要断言内部实现。"


def now():
    return datetime.now(timezone.utc).isoformat()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ensure_directory(path):
    if not path.exists():
        ensure_directory(path.parent)
        path.mkdir()
        sync_directory(path.parent)


def save_new(path, data):
    ensure_directory(path.parent)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(path.parent)


def load_key(root, retry=False):
    """Read only the named file, no shell sourcing, environment dump or repr."""
    path = root / (".env.4router.retry.local" if retry else ".env.4router.local")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or not 0 < info.st_size <= 16384:
            raise ValueError("Secret file must be a bounded regular file with owner-only access")
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = None
            lines = [
                line.strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
        if len(lines) != 1 or not lines[0].startswith("AI_API_KEY="):
            raise ValueError("Secret file must contain only one AI_API_KEY assignment")
        key = lines[0].partition("=")[2]
        if (
            not 10 <= len(key) <= 4096
            or not key.isascii()
            or any(ord(c) < 33 or ord(c) > 126 for c in key)
            or "*" in key
        ):
            raise ValueError("Secret file has invalid key format")
        return key
    finally:
        if fd is not None:
            os.close(fd)


def scrub(value, key):
    if isinstance(value, str):
        # Normalize JSON-escaped credential echoes before exact matching.
        for _ in range(2):
            value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value)
        value = value.replace(key, "[REDACTED]") if key else value
        value = re.sub(r"(?i)bearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
        value = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED_TOKEN]", value)
        return "".join(c for c in value if ord(c) >= 32 or c in "\n\t")
    if isinstance(value, list):
        return [scrub(item, key) for item in value]
    if isinstance(value, dict):
        return {scrub(str(k), key): scrub(v, key) for k, v in value.items()}
    return value


def check_authorization(root):
    auth = json.loads((root / AUTH_PATH).read_text())
    if (
        auth.get("authorized_http_attempts") != LIMIT
        or auth.get("endpoint") != ENDPOINT
        or auth.get("model_id") != MODEL
        or auth.get("actual_http_attempts") != 0
    ):
        raise ValueError("Authorization snapshot does not match this fixed first round")
    scope = auth["scope"]
    if (
        scope.get("automatic_retries") is not False
        or scope.get("rtl_permitted") is not False
        or scope.get("max_output_tokens_per_attempt") != TOKEN_LIMIT
    ):
        raise ValueError("Authorization scope mismatch")
    return auth


def prior_reservations(output):
    return list(output.glob("reservation-*.json"))


def validate_stage(output, stage):
    if stage not in {"A", "B", "A-retry"}:
        raise ValueError("Only explicitly authorized first-round stages can dispatch")
    if len(prior_reservations(output)) >= LIMIT or (output / f"reservation-{stage}.json").exists():
        raise ValueError("Stage already reserved or first-round budget exhausted")
    if stage == "A-retry":
        auth = json.loads((output / "retry-authorization.json").read_text())
        first = json.loads((output / "result-A.json").read_text())
        if (
            first.get("http_status") != 401
            or auth.get("stage") != stage
            or auth.get("endpoint") != ENDPOINT
            or auth.get("model_id") != MODEL
            or auth.get("authorized_remaining_attempts") != 1
            or auth.get("automatic_retries") is not False
            or auth.get("max_output_tokens") != TOKEN_LIMIT
            or len(prior_reservations(output)) != 1
        ):
            raise ValueError("Retry requires explicit remaining-attempt authorization after 401")
    if stage == "B":
        first = output / "result-A.json"
        if not first.exists() or json.loads(first.read_text()).get("outcome") != "SUCCESS":
            raise ValueError("B requires recorded successful A; no retry or bypass")


def reserve(output, stage):
    validate_stage(output, stage)
    save_new(
        output / f"reservation-{stage}.json",
        {
            "stage": stage,
            "reserved_at": now(),
            "endpoint": ENDPOINT,
            "model": MODEL,
            "attempt_number": len(prior_reservations(output)) + 1,
            "status": "RESERVED_BEFORE_HTTP_IO",
            "failed_or_interrupted_attempt_consumes_budget": True,
        },
    )


def describe_response(body, record, key):
    """Store only useful protocol metadata and assistant text, never reasoning."""
    try:
        data = json.loads(body)
    except (ValueError, TypeError, RecursionError):
        record["response_json_parseable"] = False
        return
    record["response_json_parseable"] = True
    if not isinstance(data, dict):
        record["response_shape"] = type(data).__name__
        return
    record["response_shape"] = "object"
    for name in ("model", "status"):
        if isinstance(data.get(name), str):
            record["response_" + name] = scrub(data[name], key)[:200]
    usage = data.get("usage")
    if isinstance(usage, dict):
        record["usage"] = {
            k: usage[k]
            for k in ("input_tokens", "output_tokens", "total_tokens")
            if type(usage.get(k)) is int
        }
    for name in ("error", "incomplete_details"):
        part = data.get(name)
        if isinstance(part, dict):
            record[name] = {
                k: scrub(str(part[k]), key)[:1000]
                for k in ("type", "code", "message", "reason")
                if k in part
            }
    output = data.get("output")
    if isinstance(output, list):
        record["output_types"] = [
            scrub(str(item.get("type", "missing")), key)[:60]
            for item in output
            if isinstance(item, dict)
        ]
        texts = []
        for item in output:
            if (
                not isinstance(item, dict)
                or item.get("type") != "message"
                or item.get("role") != "assistant"
            ):
                continue
            if isinstance(item.get("content"), list):
                texts.extend(
                    part["text"]
                    for part in item["content"]
                    if isinstance(part, dict)
                    and part.get("type") == "output_text"
                    and isinstance(part.get("text"), str)
                )
        if texts:
            try:
                from backend.app.ai import _unique_object
                from backend.app.models import Explanation

                answer = Explanation.model_validate(
                    json.loads("".join(texts), object_pairs_hook=_unique_object), strict=True
                )
                record["provider_explanation_untrusted"] = scrub(answer.model_dump(), key)
                record["provider_explanation_valid_json"] = True
            except (ValueError, TypeError, RecursionError):
                # Raw unparseable strings can contain escaped/partial credential echoes.
                record["provider_explanation_valid_json"] = False


class AuditTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner, output, stage, expected_payload, record, key):
        self.inner, self.output, self.stage = inner, output, stage
        self.expected_payload, self.record, self.key = expected_payload, record, key

    async def handle_async_request(self, request):
        if (
            str(request.url) != ENDPOINT
            or request.method != "POST"
            or json.loads(request.content) != self.expected_payload
        ):
            raise ValueError("Dispatch did not match the reviewed fixed request")
        if self.key.encode() in request.content:
            raise ValueError("Secret unexpectedly present in request body")
        reserve(self.output, self.stage)
        self.record["http_attempt_reserved"] = True
        started = time.monotonic()
        try:
            response = await self.inner.handle_async_request(request)
            self.record["headers_elapsed_seconds"] = round(time.monotonic() - started, 3)
            self.record["http_status"] = response.status_code
            self.record["content_type"] = scrub(response.headers.get("content-type", ""), self.key)[
                :120
            ]
            if not 200 <= response.status_code < 300:
                body = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    body.extend(chunk[: max(0, 32768 - len(body))])
                    if len(body) >= 32768:
                        break
                await response.aclose()
                describe_response(body, self.record, self.key)
            return response
        except httpx.RequestError as exc:
            self.record["transport_error_class"] = type(exc).__name__
            raise

    async def aclose(self):
        await self.inner.aclose()


def minimal_analysis():
    return {
        "time": 0,
        "timescale": "1 ns",
        "window": {"start": 0, "end": 0},
        "signals": [],
        "clock": None,
        "reset": None,
        "observed_facts": [],
        "limitations": ["本连通性请求不包含波形数据，不能得出波形行为结论。"],
    }


async def execute_stage(root, output, stage, key, inner):
    from backend.app import main as application
    from backend.app.ai import AIError, AIService, OpenAICompatibleProvider, build_context
    from backend.app.analyzer import value_at
    from backend.app.models import ExplainRequest

    validate_stage(output, stage)
    record = {
        "stage": stage,
        "started_at": now(),
        "provider": "4router",
        "model_requested": MODEL,
        "endpoint": ENDPOINT,
        "api_format": "responses",
        "max_attempts": 1,
        "max_output_tokens": TOKEN_LIMIT,
        "http_attempt_reserved": False,
        "real_provider": not isinstance(inner, httpx.MockTransport),
        "rtl_sent": False,
        "private_data_sent": False,
        "outcome": "NOT_DISPATCHED",
    }
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application.app), base_url="http://testserver"
    )
    try:
        if stage in {"A", "A-retry"}:
            analysis = minimal_analysis()
            body = ExplainRequest(
                time=0,
                signals=["connectivity-placeholder"],
                question=QUESTION_A,
                consent=True,
                include_rtl=False,
            )
        else:
            demo = await client.post("/api/demos/counter")
            demo.raise_for_status()
            trace = demo.json()
            names = {item["name"]: item["id"] for item in trace["signals"]}
            body = ExplainRequest(
                time=120000,
                window=40000,
                signals=[names[n] for n in ("tb.count[3:0]", "tb.enable", "tb.clk", "tb.reset")],
                clock=names["tb.clk"],
                question=QUESTION_B,
                consent=True,
                include_rtl=False,
            )
            response = await client.post(
                f"/api/traces/{trace['id']}/analysis",
                json=body.model_dump(exclude={"question", "consent", "include_rtl"}),
            )
            response.raise_for_status()
            analysis = response.json()
            by_name = {s.name: s for s in application.traces[trace["id"]].signals}
            checks = [
                ("tb.enable", 120000, "0"),
                ("tb.count[3:0]", 120000, "1010"),
                ("tb.count[3:0]", 125000, "1010"),
                ("tb.count[3:0]", 135000, "1010"),
                ("tb.count[3:0]", 145000, "1010"),
                ("tb.count[3:0]", 155000, "1011"),
            ]
            assert analysis["timescale"] == "1 ps"
            assert all(value_at(by_name[name], tick) == expected for name, tick, expected in checks)
            record["independent_expected_values"] = checks
            record["waveform_sha256"] = hashlib.sha256(
                (root / "examples/counter/trace.vcd").read_bytes()
            ).hexdigest()
            record["backend_path"] = (
                "Actual FastAPI demo/analysis/explain via in-process ASGI; external provider uses real HTTP; not browser E2E"
            )

        context = build_context(analysis, body)
        assert "related_code" not in context["analysis"]
        preview = OpenAICompatibleProvider(
            BASE, key, MODEL, api_format="responses", max_attempts=1, request_budget=1
        )
        payload = preview._payload(context)
        assert len(json.dumps(payload, ensure_ascii=False).encode()) < 24576
        if key in json.dumps(payload, ensure_ascii=False):
            raise ValueError("Secret unexpectedly present in payload")
        save_new(output / f"request-{stage}.json", payload)
        audit = AuditTransport(inner, output, stage, payload, record, key)

        class RecordedProvider(OpenAICompatibleProvider):
            def _response_text(self, response_body):
                describe_response(response_body, record, key)
                return super()._response_text(response_body)

        provider = RecordedProvider(
            BASE,
            key,
            MODEL,
            timeout_seconds=30,
            max_output_tokens=TOKEN_LIMIT,
            api_format="responses",
            max_attempts=1,
            request_budget=1,
            transport=audit,
        )
        application.app.state.ai = AIService(provider)
        started = time.monotonic()
        try:
            if stage in {"A", "A-retry"}:
                answer = await application.app.state.ai.explain(analysis, body)
                record["application_response"] = scrub(answer.model_dump(), key)
                record["connectivity_marker_present"] = "CONNECTIVITY_OK" in answer.summary
                record["outcome"] = (
                    "SUCCESS" if record["connectivity_marker_present"] else "FAILED_CONTENT_CHECK"
                )
            else:
                response = await client.post(
                    f"/api/traces/{trace['id']}/explain", json=body.model_dump()
                )
                record["local_api_status"] = response.status_code
                record["application_response"] = scrub(response.json(), key)
                record["outcome"] = (
                    "SUCCESS" if response.status_code == 200 else "FAILED_APPLICATION_OR_PROVIDER"
                )
            record["http_attempts_in_provider"] = provider.http_attempts
        except AIError as exc:
            record["outcome"] = "FAILED_PROVIDER_OR_VALIDATION"
            record["application_error"] = {
                "status": exc.status_code,
                "message": scrub(exc.message, key),
            }
        except Exception as exc:
            record["outcome"] = "FAILED_UNEXPECTED"
            record["error_class"] = type(exc).__name__
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            record["finished_at"] = now()
            record["reserved_attempts_total"] = len(prior_reservations(output))
            record["remaining_authorized_attempts"] = LIMIT - record["reserved_attempts_total"]
            save_new(output / f"result-{stage}.json", scrub(record, key))
        return record
    finally:
        await client.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["preflight", "A", "B", "A-retry"], default="preflight")
    parser.add_argument("--live-authorized", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    logging.disable(logging.CRITICAL)
    check_authorization(root)
    if args.stage == "preflight":
        print(
            json.dumps({"mode": "OFFLINE_PREFLIGHT", "real_requests": 0, "credential_read": False})
        )
        return
    if not args.live_authorized:
        raise ValueError("Live stage requires explicit authorization flag and user consent")
    output = root / "docs/qa/evidence" / EVIDENCE_NAME
    ensure_directory(output)
    with (output / ".execution.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate_stage(output, args.stage)
        key = load_key(root, retry=args.stage == "A-retry")
        record = asyncio.run(
            execute_stage(
                root, output, args.stage, key, httpx.AsyncHTTPTransport(retries=0, trust_env=False)
            )
        )
        print(
            json.dumps(
                {
                    k: record.get(k)
                    for k in (
                        "stage",
                        "outcome",
                        "http_status",
                        "elapsed_seconds",
                        "reserved_attempts_total",
                        "remaining_authorized_attempts",
                    )
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No traceback, repr, environment, HTTP headers or credential values.
        print(
            json.dumps(
                {
                    "status": "STOPPED",
                    "error_class": type(exc).__name__,
                    "detail": "No automatic retry; inspect sanitized evidence or preflight constraints.",
                }
            )
        )
        raise SystemExit(1) from None
