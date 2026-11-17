import re
from bisect import bisect_left, bisect_right

from .models import AnalysisRequest, Event, Signal, Trace


def value_at(signal: Signal, time: int) -> str | None:
    index = bisect_right(signal.events, time, key=lambda event: event.time) - 1
    return signal.events[index].value if index >= 0 else None


def edges(signal: Signal, edge: str) -> list[int]:
    pair = ("0", "1") if edge == "rising" else ("1", "0")
    return [
        after.time
        for before, after in zip(signal.events, signal.events[1:])
        if (before.value, after.value) == pair
    ]


def source_matches(trace: Trace, selected: list[Signal]) -> list[dict]:
    matches = []
    source_lines = [(source, source.content.splitlines()) for source in trace.sources]
    for signal in selected:
        leaf = re.sub(r"\[[^\]]*\]$", "", signal.name.rsplit(".", 1)[-1])
        if not leaf:
            continue
        pattern = re.compile(r"(?<![A-Za-z0-9_$])" + re.escape(leaf) + r"(?![A-Za-z0-9_$])")
        for source, lines in source_lines:
            for number, line in enumerate(lines, 1):
                if pattern.search(line):
                    matches.append(
                        {
                            "file": source.name,
                            "line": number,
                            "text": line[:300],
                            "signal": signal.name,
                            "match": "name-only",
                        }
                    )
                    if len(matches) >= 32:
                        return matches
    return matches


def analyze(trace: Trace, request: AnalysisRequest) -> dict:
    if not trace.start <= request.time <= trace.end:
        raise ValueError("所选时间超出波形范围。")
    by_id = {signal.id: signal for signal in trace.signals}
    ids = list(dict.fromkeys(request.signals))
    for id_ in [*ids, request.clock, request.reset]:
        if id_ is not None and id_ not in by_id:
            raise ValueError("未知信号 ID。")
    selected = [by_id[id_] for id_ in ids]
    start, end = (
        max(0, request.time - request.window),
        min(trace.end, request.time + request.window),
    )
    facts, results = [], []
    for signal in selected:
        before = bisect_left(signal.events, request.time, key=lambda event: event.time) - 1
        after = bisect_right(signal.events, request.time, key=lambda event: event.time)
        left = bisect_left(signal.events, start, key=lambda event: event.time)
        right = bisect_right(signal.events, end, key=lambda event: event.time)
        value = value_at(signal, request.time)
        previous = signal.events[before] if before >= 0 else None
        next_ = signal.events[after] if after < len(signal.events) else None
        results.append(
            {
                "id": signal.id,
                "name": signal.name,
                "width": signal.width,
                "value": value,
                "previous": previous,
                "next": next_,
                "events": signal.events[left : min(right, left + 128)],
                "truncated": right - left > 128,
            }
        )
        facts.append(
            f"t={request.time} tick（1 tick = {trace.timescale}），{signal.name} = {value if value is not None else '尚无记录'}。"
        )
        if previous and previous.value == value:
            facts.append(
                f"{signal.name} 在所选时间的值与之前最近记录 t={previous.time} tick 相同；这不排除期间同时间戳内的跳变。"
            )
    clock = None
    if request.clock:
        signal = by_id[request.clock]
        if signal.width != 1:
            raise ValueError("时钟必须为单比特信号。")
        times = edges(signal, request.edge)
        before = bisect_left(times, request.time) - 1
        after = bisect_right(times, request.time)
        clock = {
            "name": signal.name,
            "edge": request.edge,
            "previous": times[before] if before >= 0 else None,
            "next": times[after] if after < len(times) else None,
            "at_time": request.time in times,
        }
        facts.append(
            f"用户指定时钟 {signal.name} 在 t={request.time} tick {'存在' if clock['at_time'] else '没有记录到'}确定的 {request.edge} 边沿。"
        )
    reset = None
    if request.reset:
        signal = by_id[request.reset]
        if signal.width != 1:
            raise ValueError("复位必须为单比特信号。")
        value = value_at(signal, request.time)
        active = value == request.reset_active if value in ("0", "1") else None
        reset = {"name": signal.name, "value": value, "active": active, "mode": request.reset_mode}
        facts.append(
            f"用户配置的复位 {signal.name} 值为 {value}，有效电平为 {request.reset_active}；复位类型配置为 {request.reset_mode}（非波形推断）。"
        )
    limitations = [
        "时间单位为整数 tick；光标值取该时间戳最后一条记录。",
        "同时间戳保留文件记录顺序，但 VCD 不包含完整 delta-cycle/RTL 执行语义。",
        "仅检测确定的 0→1 / 1→0 边沿，不把 X/Z 过渡当作确定边沿。",
        "时间相关性不等于因果关系；未配置时无法确定复位类型。",
        "RTL 关联仅为名称匹配，可能包括注释、同名变量，不是 HDL 语义解析。",
    ]
    if any(result["truncated"] for result in results):
        limitations.append("每个信号的窗口最多返回前 128 条记录；已标注截断，请缩小窗口。")
    return {
        "time": request.time,
        "timescale": trace.timescale,
        "window": {"start": start, "end": end},
        "signals": results,
        "clock": clock,
        "reset": reset,
        "observed_facts": facts,
        "limitations": [*limitations, *trace.warnings],
        "related_code": source_matches(trace, selected),
    }


def markdown_report(trace: Trace, analysis: dict) -> str:
    lines = [
        "# Waveform Tutor — Offline report",
        "",
        f"Trace: {trace.name}",
        f"Time: {analysis['time']} tick; 1 tick = {trace.timescale}",
        "",
        "## Observed facts",
        *[f"- {fact}" for fact in analysis["observed_facts"]],
        "",
        "## Window events",
    ]
    for signal in analysis["signals"]:
        lines.append(f"\n### {signal['name']}")
        for event in signal["events"]:
            if isinstance(event, Event):
                lines.append(f"- {event.time}: {event.value}")
    lines.extend(["", "## Limitations", *[f"- {text}" for text in analysis["limitations"]]])
    return "\n".join(lines)
