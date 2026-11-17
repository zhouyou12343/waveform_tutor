#!/usr/bin/env python3
"""Independent runtime API acceptance. Never imports application code or runs supplied RTL."""

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False).replace(str(ROOT), ".") + "\n")


def process_info():
    p = subprocess.run(["lsof", "-t", "-iTCP:8000", "-sTCP:LISTEN"], capture_output=True, text=True)
    pid = int(p.stdout.split()[0]) if p.stdout.strip() else None
    info = (
        subprocess.run(
            ["ps", "-p", str(pid), "-o", "pid=,lstart=,rss=,command="],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if pid
        else ""
    )
    return {"pid": pid, "ps": info, "captured_at": datetime.datetime.now().astimezone().isoformat()}


def request(route, data, content_type="application/json"):
    start = time.perf_counter()
    req = urllib.request.Request(
        BASE + route, data=data, headers={"Content-Type": content_type}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    elapsed = (time.perf_counter() - start) * 1000
    return json.loads(raw), {
        "status": status,
        "http_ms": elapsed,
        "request_body_bytes": len(data),
        "response_body_bytes": len(raw),
    }


def upload(path):
    boundary = "qa-fixed-boundary-928471"
    data = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return request("/api/traces", data, "multipart/form-data; boundary=" + boundary)


def signal(trace, leaf):
    matches = [
        s for s in trace["signals"] if s["name"].split(".")[-1].split("[")[0].strip() == leaf
    ]
    if not matches:
        raise ValueError(f"Missing {leaf}; names: {[s['name'] for s in trace['signals']]}")
    return min(matches, key=lambda s: len(s["name"]))


FIXTURE = """`timescale 1ns/1ps
module tb;
reg clk=0, reset=1;
reg [3:0] sync_count, async_count;
reg [3:0] bus=4'bxxxx;
reg marker=0;
always #5 clk=~clk;
always @(posedge clk) if(reset) sync_count<=0; else sync_count<=sync_count+4'd1;
always @(posedge clk or posedge reset) if(reset) async_count<=0; else async_count<=async_count+4'd1;
initial begin
  $dumpfile("trace.vcd"); $dumpvars(0,tb);
  #12 reset=0;
  #160; // 172 ns, 16 increments -> 0
  #10; // 182 ns, both counters = 1
  reset=1; // async clears off-edge, sync stays 1 until 185
  #1 bus=4'bzzzz;
  #1 bus=4'bx1z0;
  #2 reset=0;
  #1 marker=1; $dumpall; #0 marker=0; $dumpall; // same tick dump records
  #1 bus=4'b0011;
  #12 $finish;
end
endmodule
"""


def simulate(folder, sources):
    folder.mkdir(parents=True, exist_ok=True)
    commands = [
        ["iverilog", "-g2012", "-s", "tb", "-o", str(folder / "sim.out"), *map(str, sources)],
        ["vvp", str(folder / "sim.out")],
    ]
    logs = []
    for cmd in commands:
        p = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=20)
        logs.append(
            {"command": cmd, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
        )
        if p.returncode:
            save(folder / "simulation.json", logs)
            raise RuntimeError(p.stderr + p.stdout)
    save(folder / "simulation.json", logs)
    return folder / "trace.vcd"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline")
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be alphanumeric, hyphens or underscores")
    out = ROOT / "docs/qa/evidence" / ("correctness-" + args.label)
    # Never overwrite a previous run's sources, simulator logs or observations.
    out.mkdir(parents=True, exist_ok=False)
    results = {
        "process": process_info(),
        "label": args.label,
        "oracle": "Hand-derived integer state transitions from copied trusted RTL; fixed expected boundary tables. No app imports.",
        "checks": [],
        "uploads": [],
    }

    def load(name, path):
        trace, meta = upload(path)
        save(out / (name + "-upload.json"), {"meta": meta, "response": trace})
        results["uploads"].append(
            {
                "name": name,
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                **meta,
            }
        )
        if meta["status"] != 200:
            raise RuntimeError(str(trace))
        return trace

    def check(trace, category, ns, expected, note="", **options):
        selected = [signal(trace, name) for name in expected]
        body = {
            "time": int(ns * 1000),
            "signals": [s["id"] for s in selected],
            "window": 0,
            **options,
        }
        response, meta = request(
            "/api/traces/" + trace["id"] + "/analysis", json.dumps(body).encode()
        )
        actual = {
            name: next(
                (s["value"] for s in response.get("signals", []) if s["id"] == sig["id"]), None
            )
            for name, sig in zip(expected, selected)
        }
        want = {
            name: format(value, "0" + str(sig["width"]) + "b") if isinstance(value, int) else value
            for (name, value), sig in zip(expected.items(), selected)
        }
        item = {
            "category": category,
            "ns": ns,
            "expected": want,
            "actual": actual,
            "pass": meta["status"] == 200 and actual == want,
            "note": note,
            "request": body,
            "response": response,
            "http": meta,
        }
        if "clock" in options:
            item["expected_clock_at_time"] = ns % 10 == 5
            item["pass"] &= (
                response.get("clock", {}).get("at_time") == item["expected_clock_at_time"]
            )
        results["checks"].append(item)

    # Copy trusted built-ins so each run retains exact source provenance, then regenerate VCD with Icarus.
    examples = {}
    for name in ("counter", "fifo", "handshake"):
        folder = out / name
        folder.mkdir(exist_ok=True)
        for filename in ("design.sv", "tb.sv"):
            shutil.copyfile(ROOT / "examples" / name / filename, folder / filename)
        examples[name] = simulate(folder, [folder / "design.sv", folder / "tb.sv"])
    tr = load("counter", examples["counter"])
    count = 0
    for ns in range(5, 236, 10):
        reset = ns < 20 or 212 <= ns < 220 or ns >= 232
        enabled = 20 <= ns < 120 or ns >= 150
        count = 0 if reset else ((count + 1) % 16 if enabled else count)
        check(
            tr,
            "ordinary-counter",
            ns,
            {"count": count},
            "Post-edge model: reset priority; enable gates addition modulo 16",
        )
    for ns, val in [
        (120, 10),
        (149, 10),
        (195, 15),
        (205, 0),
        (225, 1),
        (232, 1),
        (233, 1),
        (235, 0),
    ]:
        check(
            tr,
            "overflow"
            if ns in (195, 205)
            else "synchronous-reset"
            if ns >= 225
            else "ordinary-counter",
            ns,
            {"count": val},
        )
    tr = load("fifo", examples["fifo"])
    table = [
        (25, 1, 0),
        (35, 2, 0),
        (45, 3, 0),
        (55, 4, 0),
        (65, 4, 0),
        (75, 3, 0x11),
        (85, 3, 0x22),
        (95, 2, 0x33),
        (105, 1, 0x44),
        (115, 0, 0x55),
        (125, 0, 0x55),
        (135, 1, 0x55),
        (145, 0, 0x66),
        (155, 1, 0x66),
        (165, 2, 0x66),
        (175, 3, 0x66),
        (185, 4, 0x66),
        (195, 3, 0x77),
        (205, 2, 0x88),
        (215, 1, 0x99),
        (225, 0, 0xAA),
    ]
    for ns, count, data in table:
        check(
            tr,
            "fifo-boundary",
            ns,
            {"count": count, "rd_data": data, "full": int(count == 4), "empty": int(count == 0)},
            "Depth 4; pre-edge full rejects push even with pop; empty rejects pop even with push; FIFO order 11,22,33,44,55,66,77,88,99,AA",
        )
    tr = load("handshake", examples["handshake"])
    for ns, data, valid, sent in [
        (35, 0xA1, 1, 0),
        (45, 0xA1, 1, 0),
        (54.999, 0xA1, 1, 0),
        (55, 0xA2, 1, 1),
        (65, 0xA2, 1, 1),
        (75, 0xA2, 1, 1),
        (85, 0xA2, 1, 1),
        (94.999, 0xA2, 1, 1),
        (95, 0xA3, 1, 2),
        (104.999, 0xA3, 1, 2),
        (105, 0xA3, 0, 3),
        (125, 0xA3, 0, 3),
    ]:
        check(
            tr,
            "ready-valid",
            ns,
            {"data": data, "valid": valid, "sent": sent, "ready": int(50 <= ns < 60 or ns >= 90)},
            "Transfers use PRE-edge A1@55,A2@95,A3@105; API cursor at edge reports POST-edge values, not transferred payload",
        )
    folder = out / "fixed-fixture"
    folder.mkdir(exist_ok=True)
    (folder / "tb.sv").write_text(FIXTURE)
    tr = load("fixed-fixture", simulate(folder, [folder / "tb.sv"]))
    clk, reset = signal(tr, "clk")["id"], signal(tr, "reset")["id"]
    for ns, sync, async_ in [
        (5, 0, 0),
        (15, 1, 1),
        (165, 0, 0),
        (175, 1, 1),
        (182, 1, 0),
        (184, 1, 0),
        (185, 0, 0),
        (195, 1, 1),
    ]:
        check(
            tr,
            "asynchronous-reset"
            if ns in (182, 184)
            else "overflow"
            if ns == 165
            else "synchronous-reset",
            ns,
            {"sync_count": sync, "async_count": async_},
            "At 182 ns no clock edge: asynchronous=0, synchronous=1 until 185 ns",
            clock=clk,
            reset=reset,
            reset_mode="asynchronous",
        )
    for ns, value in [(0, "xxxx"), (183, "zzzz"), (184, "x1z0"), (188, "0011")]:
        check(
            tr,
            "multi-bit-X-Z",
            ns,
            {"bus": value},
            "Literal four-state stimulus; x/z must extend to declared width",
        )
    check(
        tr,
        "same-tick",
        187,
        {"marker": 0},
        "Icarus #0 and $dumpall at 187ns: last record wins; no claim about complete delta-cycle reconstruction",
    )
    # Explicit legal same-timestamp ordering probe, independent of simulator dump coalescing.
    path = out / "same-tick.vcd"
    path.write_text(
        "$timescale 1ps $end\n$scope module tb $end\n$var reg 4 ! value $end\n$upscope $end\n$enddefinitions $end\n#0\nb0000 !\n#1000\nb0001 !\nb0010 !\nbx1z0 !\n#2000\nb0011 !\n"
    )
    tr = load("same-tick", path)
    check(
        tr,
        "same-tick",
        1,
        {"value": "x1z0"},
        "Explicit records at tick 1000: 0001,0010,x1z0; final record is x1z0",
    )
    sig = signal(tr, "value")
    actual = [e["value"] for e in sig["events"] if e["time"] == 1000]
    results["checks"].append(
        {
            "category": "same-tick-record-order",
            "expected": ["0001", "0010", "x1z0"],
            "actual": actual,
            "pass": actual == ["0001", "0010", "x1z0"],
        }
    )
    results["process_end"] = process_info()
    results["checks"].append(
        {
            "category": "baseline-process-identity",
            "expected": results["process"]["pid"],
            "actual": results["process_end"]["pid"],
            "pass": results["process"]["pid"] is not None
            and results["process"]["pid"] == results["process_end"]["pid"],
        }
    )
    results["passed"] = sum(c["pass"] for c in results["checks"])
    results["total"] = len(results["checks"])
    results["verdict"] = "PASS" if results["passed"] == results["total"] else "FAIL"
    save(out / "results.json", results)
    lines = [
        "# 独立数字正确性验收",
        "",
        f"Verdict: **{results['verdict']}** — {results['passed']}/{results['total']} checks",
        "检查中含1项进程PID一致性，其余为数字值/记录检查；不把进程检查计作数字正确性。",
        "",
        "## 方法与范围",
        "真实 HTTP POST /api/traces → /api/traces/{id}/analysis；不 import app、不调用 AI、不运行用户 RTL。仅编译固定自写 fixture 与复制的内置 examples。预期为人工推导的整数模型/常量表，不从 API 或 VCD 反推。Icarus 生成的 VCD 是输入，不作为唯一正确性 oracle。",
        "",
        "Counter: reset 优先，enable 门控，(count+1)%16；FIFO: 深度4、边沿前 full/empty 决定 admission；握手: pre-edge valid&&ready 传输 A1@55/A2@95/A3@105，光标在边沿上则显示 post-edge。X/Z 直接使用 SV 四态字面量。",
        "",
        "## 基线进程",
        "```",
        results["process"]["ps"],
        "```",
        f"采样时间: {results['process']['captured_at']}",
        f"运行标签：{args.label}。进程不自动 reload，修改应用后必须重启再测；进程信息用于区分基线与修复后执行。",
        "",
        "## 逐项 expected / actual",
        "|类别|ns|expected|actual|结果|",
        "|---|---:|---|---|---|",
    ]
    for c in results["checks"]:
        lines.append(
            f"|{c['category']}|{c.get('ns', '-')}|`{c['expected']}`|`{c['actual']}`|{'PASS' if c['pass'] else 'FAIL'}|"
        )
    lines += [
        "",
        "## 复现与证据",
        f"`python3 {ROOT}/scripts/qa_correctness.py --label {args.label}`",
        f"证据目录：`{out}`。results.json 含所有请求/响应和逐项判定；*-upload.json 为上传完整响应；子目录保存 SV、VCD、Icarus 命令和日志。same-tick.vcd 专门验证文件内同 tick 记录顺序。",
        "本报告按 label 保存，不覆盖历史汇总或同名证据；未测浏览器，由主代理另行完成。",
    ]
    (out / "report.md").write_text("\n".join(lines).replace(str(ROOT), ".") + "\n")
    print(
        json.dumps(
            {
                "verdict": results["verdict"],
                "passed": results["passed"],
                "total": results["total"],
                "evidence": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if results["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
