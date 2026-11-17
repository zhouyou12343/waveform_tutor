import asyncio
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analyzer import analyze, markdown_report
from .models import AnalysisRequest, ExplainRequest, Source, Trace
from .parser import MAX_FILE_BYTES, ParseError, parse_vcd

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = {name: ROOT / "examples" / name for name in ("counter", "fifo", "handshake")}
ALLOWED_ORIGINS = {
    f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 8000)
}


class LocalRequestGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        origin = headers.get(b"origin", b"").decode("latin1")
        if origin and origin not in ALLOWED_ORIGINS:
            return await JSONResponse({"detail": "仅允许本地应用来源。"}, 403)(scope, receive, send)
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            limit = (
                MAX_FILE_BYTES + 65536
                if b"multipart/form-data" in headers.get(b"content-type", b"")
                else 32768
            )
            chunks, size = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > limit:
                    return await JSONResponse({"detail": "请求体超过大小限制。"}, 413)(
                        scope, receive, send
                    )
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            delivered = False

            async def limited_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            return await self.app(scope, limited_receive, send)
        return await self.app(scope, receive, send)


app = FastAPI(title="Waveform Tutor", version="0.1.0")
app.add_middleware(LocalRequestGuard)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
traces: OrderedDict[str, Trace] = OrderedDict()


def get_ai():
    from .ai_settings import load_configuration

    if not hasattr(app.state, "ai"):
        app.state.ai, app.state.ai_settings = load_configuration()
    return app.state.ai


def get_ai_settings():
    from .ai_settings import public_config

    service = get_ai()
    if not hasattr(app.state, "ai_settings"):
        app.state.ai_settings = public_config(service, "runtime")
    return app.state.ai_settings


def remember(trace: Trace) -> Trace:
    while len(traces) >= 4:
        traces.popitem(last=False)
    trace.warnings.append("本地进程最多保留最近 4 个波形；重启或超出容量后需重新加载。")
    traces[trace.id] = trace
    return trace


def get_trace(trace_id: str) -> Trace:
    if trace_id not in traces:
        raise HTTPException(404, "波形不存在或已过期，请重新加载。")
    return traces[trace_id]


def run_analysis(trace_id: str, body: AnalysisRequest) -> tuple[Trace, dict]:
    trace = get_trace(trace_id)
    try:
        return trace, analyze(trace, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def safe_name(filename: str | None, suffixes: set[str]) -> str:
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if (
        not name
        or len(name) > 128
        or any(ord(char) < 32 for char in name)
        or Path(name).suffix.lower() not in suffixes
    ):
        raise HTTPException(422, "文件名或扩展名不受支持。")
    return name


@app.exception_handler(ParseError)
async def parse_error_handler(request: Request, exc: ParseError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.get("/api/health")
def health():
    service = get_ai()
    return {
        "status": "ok",
        "ai_configured": service.configured,
        "requests": service.requests,
        "provider_http_attempts": service.http_attempts,
        "ai_config_revision": get_ai_settings()["revision"],
    }


@app.get("/api/ai/config")
async def ai_configuration():
    return JSONResponse(get_ai_settings(), headers={"Cache-Control": "no-store"})


@app.put("/api/ai/config")
async def save_ai_configuration(request: Request):
    from .ai import AIError, AIService
    from .ai_settings import make_provider, normalize_settings, persist_configuration, public_config

    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
        raise HTTPException(415, "请使用 JSON 提交模型配置。")
    try:
        settings = normalize_settings(await request.json())
        provider = make_provider(settings)
    except (ValueError, TypeError, KeyError, AIError):
        # Do not return Pydantic input/error details: they may contain the API key.
        raise HTTPException(
            422, "配置无效：请检查 API 地址、Key、模型 ID 和接口类型。远程地址须使用 HTTPS。"
        ) from None
    if getattr(app.state, "ai_busy", False):
        raise HTTPException(409, "AI 正在处理请求，请等待结束或取消后再修改配置。")
    try:
        persist_configuration(settings)
    except OSError:
        raise HTTPException(500, "保存失败：无法写入本机配置目录，请确认项目文件夹可写。") from None
    app.state.ai = AIService(provider)
    app.state.ai_settings = public_config(app.state.ai, "local")
    return JSONResponse(
        {
            **app.state.ai_settings,
            "message": "配置已保存。保存不验证密钥或模型；点击生成解释时才会调用服务。",
        },
        headers={"Cache-Control": "no-store"},
    )


@app.delete("/api/ai/config")
async def clear_ai_configuration():
    from .ai import AIService
    from .ai_settings import persist_configuration, public_config

    if getattr(app.state, "ai_busy", False):
        raise HTTPException(409, "AI 正在处理请求，请等待结束或取消后再清除配置。")
    try:
        persist_configuration({"disabled": True})
    except OSError:
        raise HTTPException(500, "清除失败：无法写入本机配置目录。") from None
    app.state.ai = AIService(load_environment=False)
    app.state.ai_settings = public_config(app.state.ai, "disabled")
    return JSONResponse(
        {**app.state.ai_settings, "message": "网页保存的密钥已清除，AI 已关闭；离线分析仍可使用。"},
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/traces", response_model=Trace)
async def upload_trace(request: Request, file: UploadFile = File(...)):
    try:
        name = safe_name(file.filename, {".vcd"})
        data = await file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, "VCD 超过 8 MiB 限制。")
        trace = await run_in_threadpool(parse_vcd, data, name)
        if await request.is_disconnected():
            raise HTTPException(499, "请求已取消。")
        return remember(trace)
    finally:
        await file.close()


@app.post("/api/demos/{name}", response_model=Trace)
async def demo(name: str):
    if name not in EXAMPLES:
        raise HTTPException(404, "示例不存在。")
    path = EXAMPLES[name]
    trace = await run_in_threadpool(parse_vcd, (path / "trace.vcd").read_bytes(), f"{name}.vcd")
    trace.sources = [
        Source(name=filename, content=(path / filename).read_text())
        for filename in ("design.sv", "tb.sv")
    ]
    return remember(trace)


@app.post("/api/traces/{trace_id}/sources", response_model=Source)
async def upload_source(trace_id: str, file: UploadFile = File(...)):
    try:
        trace = get_trace(trace_id)
        name = safe_name(file.filename, {".v", ".sv"})
        if len(trace.sources) >= 8:
            raise HTTPException(422, "每个波形最多 8 个源文件。")
        if any(source.name == name for source in trace.sources):
            raise HTTPException(409, "存在同名源文件，请重命名后上传。")
        data = await file.read(128 * 1024 + 1)
        if len(data) > 128 * 1024:
            raise HTTPException(413, "RTL 文件超过 128 KiB。")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(422, "RTL 文件须使用 UTF-8 编码。") from None
        if not text.strip() or "\x00" in text:
            raise HTTPException(422, "RTL 文件为空或包含二进制内容。")
        source = Source(name=name, content=text)
        trace.sources.append(source)
        return source
    finally:
        await file.close()


@app.post("/api/traces/{trace_id}/analysis")
def analysis(trace_id: str, body: AnalysisRequest):
    return run_analysis(trace_id, body)[1]


@app.post("/api/traces/{trace_id}/report")
def report(trace_id: str, body: AnalysisRequest):
    trace, result = run_analysis(trace_id, body)
    return Response(
        markdown_report(trace, result),
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="waveform-report.md"'},
    )


@app.post("/api/traces/{trace_id}/explain")
async def explain(trace_id: str, body: ExplainRequest, request: Request):
    from .ai import AIError

    if getattr(app.state, "ai_busy", False):
        raise HTTPException(429, "已有 AI 请求正在处理，请稍后重试。")

    def prepare():
        return jsonable_encoder(run_analysis(trace_id, body)[1])

    worker = None
    disconnect_lock = asyncio.Lock()

    async def require_connection():
        # Serialize reads from the ASGI receive channel between polling and dispatch.
        async with disconnect_lock:
            if await request.is_disconnected():
                raise HTTPException(499, "请求已取消。")

    async def process():
        nonlocal worker
        worker = asyncio.create_task(run_in_threadpool(prepare))
        result = await asyncio.shield(worker)
        # Analysis may finish between polls. Never dispatch after an observed disconnect.
        await require_connection()
        return await get_ai().explain(result, body)

    app.state.ai_busy = True
    task = None
    try:
        task = asyncio.create_task(process())
        while not task.done():
            await require_connection()
            await asyncio.wait({task}, timeout=0.1)
        return await task
    except AIError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    finally:
        try:
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            # A running CPU thread cannot be cancelled; retain admission until it exits.
            if worker is not None:
                await asyncio.shield(asyncio.gather(worker, return_exceptions=True))
        finally:
            app.state.ai_busy = False
