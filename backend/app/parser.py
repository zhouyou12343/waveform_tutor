import io
from uuid import uuid4

from vcd.reader import TokenKind as K
from vcd.reader import VCDParseError, tokenize

from .models import MAX_TICK, Event, Signal, Trace

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 100_000
MAX_SIGNALS = 512
MAX_WIDTH = 256
MAX_IDENTIFIER_CHARS = 256
MAX_NAME_CHARS = 1024
MAX_SIGNAL_NAME_CHARS = 128 * 1024
UNITS_FS = {"s": 10**15, "ms": 10**12, "us": 10**9, "ns": 10**6, "ps": 1000, "fs": 1}
DIGITAL_TYPES = {
    "wire",
    "reg",
    "integer",
    "parameter",
    "supply0",
    "supply1",
    "time",
    "tri",
    "triand",
    "trior",
    "trireg",
    "tri0",
    "tri1",
    "wand",
    "wor",
}


class ParseError(ValueError):
    pass


def parse_vcd(data: bytes, name: str) -> Trace:
    if not data.strip():
        raise ParseError("VCD 文件为空。")
    if len(data) > MAX_FILE_BYTES:
        raise ParseError("VCD 超过 8 MiB 限制。")
    scopes: list[str] = []
    signals: list[Signal] = []
    aliases: dict[str, list[Signal]] = {}
    names: set[str] = set()
    name_chars = 0
    time = 0
    count = 0
    timescale = None
    definitions = False
    dumping = False
    last = None
    warnings = []
    try:
        # Sentinel detects truncated directives that the tokenizer otherwise ends at EOF.
        for token in tokenize(io.BytesIO(data + b"\n$comment __WFT_EOF__ $end\n")):
            last = token
            kind = token.kind
            if kind in {K.COMMENT, K.DATE, K.VERSION}:
                continue
            if kind in {K.ATTRBEGIN, K.ATTREND, K.CHANGE_REAL, K.CHANGE_STRING}:
                raise ParseError(f"暂不支持 VCD 特性：{kind.name}。")
            if kind in {K.SCOPE, K.UPSCOPE, K.VAR, K.TIMESCALE, K.ENDDEFINITIONS}:
                if definitions:
                    raise ParseError("定义区结束后出现新的声明。")
                if kind == K.SCOPE:
                    if len(token.scope.ident) > MAX_IDENTIFIER_CHARS:
                        raise ParseError("scope 标识符超过 256 字符。")
                    scopes.append(token.scope.ident)
                    if len(scopes) > 32:
                        raise ParseError("层级深度超过 32。")
                elif kind == K.UPSCOPE:
                    if not scopes:
                        raise ParseError("不匹配的 $upscope。")
                    scopes.pop()
                elif kind == K.TIMESCALE:
                    if timescale is not None:
                        raise ParseError("重复 timescale。")
                    timescale = token.timescale
                    if timescale.magnitude not in (1, 10, 100):
                        raise ParseError("timescale 倍率必须为 1、10 或 100。")
                elif kind == K.ENDDEFINITIONS:
                    if scopes:
                        raise ParseError("模块层级未闭合。")
                    definitions = True
                else:
                    var = token.var
                    if var.type_.value not in DIGITAL_TYPES:
                        raise ParseError(f"暂不支持信号类型：{var.type_.value}。")
                    if not 1 <= var.size <= MAX_WIDTH:
                        raise ParseError("信号位宽须为 1–256。")
                    if len(signals) >= MAX_SIGNALS:
                        raise ParseError("信号数超过 512。")
                    if (
                        len(var.reference) > MAX_IDENTIFIER_CHARS
                        or len(var.id_code) > MAX_IDENTIFIER_CHARS
                    ):
                        raise ParseError("ref/id_code 标识符超过 256 字符。")
                    ref = var.ref_str
                    if len(ref) > MAX_IDENTIFIER_CHARS:
                        raise ParseError("ref 标识符超过 256 字符。")
                    scope_chars = sum(map(len, scopes)) + max(0, len(scopes) - 1)
                    full_chars = scope_chars + bool(scopes) + len(ref)
                    if full_chars > MAX_NAME_CHARS:
                        raise ParseError("完整信号名称超过 1024 字符。")
                    name_chars += full_chars + scope_chars
                    if name_chars > MAX_SIGNAL_NAME_CHARS:
                        raise ParseError("累计 signal name+scope 超过 128 Ki 字符预算。")
                    full_name = ".".join([*scopes, ref])
                    if full_name in names:
                        raise ParseError("重复信号名称。")
                    names.add(full_name)
                    signal = Signal(
                        id=f"s{len(signals)}",
                        name=full_name,
                        scope=".".join(scopes),
                        width=var.size,
                        kind=var.type_.value,
                        events=[],
                    )
                    if var.id_code in aliases and aliases[var.id_code][0].width != var.size:
                        raise ParseError("同一 VCD 标识符的别名位宽不一致。")
                    aliases.setdefault(var.id_code, []).append(signal)
                    signals.append(signal)
                continue
            if not definitions:
                raise ParseError("值变化必须在 $enddefinitions 之后。")
            if kind == K.DUMPOFF:
                raise ParseError("暂不支持 $dumpoff 停录区间，无法确定期间的信号状态。")
            if kind in {K.DUMPVARS, K.DUMPALL, K.DUMPON}:
                if dumping:
                    raise ParseError("嵌套的 dump 指令。")
                dumping = True
            elif kind == K.END:
                if not dumping:
                    raise ParseError("多余的 $end。")
                dumping = False
            elif kind == K.CHANGE_TIME:
                if dumping:
                    raise ParseError("dump 指令未闭合。")
                if not time <= token.time_change <= MAX_TICK:
                    raise ParseError("时间须单调递增且不超过 2^53−1 tick。")
                time = token.time_change
            elif kind in {K.CHANGE_SCALAR, K.CHANGE_VECTOR}:
                change = token.data
                if change.id_code not in aliases:
                    raise ParseError("值变化引用了未声明的信号。")
                targets = aliases[change.id_code]
                width = targets[0].width
                if kind == K.CHANGE_SCALAR and width != 1:
                    raise ParseError("多位信号必须使用 vector 变化记录。")
                raw = (
                    format(change.value, "b")
                    if isinstance(change.value, int)
                    else change.value.lower()
                )
                if not raw or len(raw) > width or set(raw) - set("01xz"):
                    raise ParseError("信号值与声明位宽不匹配。")
                value = raw.rjust(width, raw[0] if raw[0] in "xz" else "0")
                count += len(targets)
                if count > MAX_EVENTS:
                    raise ParseError("展开别名后的事件数超过 100,000。")
                for target in targets:
                    target.events.append(Event(time=time, value=value))
        if last is None or last.kind != K.COMMENT or last.data != "__WFT_EOF__" or dumping:
            raise ParseError("VCD 文件不完整。")
    except (VCDParseError, ValueError, UnicodeError, AssertionError) as exc:
        if isinstance(exc, ParseError):
            raise
        raise ParseError(f"VCD 格式错误：{str(exc)[:200]}") from None
    if not definitions or timescale is None or not signals:
        raise ParseError("缺少 timescale、信号声明或 $enddefinitions。")
    return Trace(
        id=uuid4().hex,
        name=name,
        timescale=f"{timescale.magnitude} {timescale.unit.value}",
        tick_fs=timescale.magnitude * UNITS_FS[timescale.unit.value],
        start=0,
        end=time,
        signals=signals,
        warnings=list(dict.fromkeys(warnings)),
    )
