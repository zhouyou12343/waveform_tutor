#!/usr/bin/env python3
"""Bounded local HTTP benchmark; separate from correctness oracle, no application imports."""

import argparse
import hashlib
import json
import math
import subprocess
import threading
import time

from qa_correctness import ROOT, process_info, request, save, upload


def rss_kib(pid):
    p = subprocess.run(["ps", "-p", str(pid), "-o", "rss="], capture_output=True, text=True)
    return int(p.stdout.strip()) if p.stdout.strip() else None


def generate(path, ticks):
    # Exactly three value records per timestamp. No random seeds or wall-clock metadata.
    header = '$timescale 1ns $end\n$scope module bench $end\n$var reg 1 ! clk $end\n$var reg 1 " gate $end\n$var reg 208 # data $end\n$upscope $end\n$enddefinitions $end\n'
    with path.open("w") as f:
        f.write(header)
        for t in range(ticks):
            value = ((t + 1) * 0x9E3779B97F4A7C15) ^ ((t + 17) << 143)
            f.write(f'#{t}\n{t % 2}!\n{(t // 2) % 2}"\nb{value:0208b} #\n')
    count = ticks * 3
    if count > 100000 or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Fixture exceeds bounded workload")
    return {
        "events": count,
        "ticks": ticks,
        "vcd_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def percentiles(samples):
    ordered = sorted(samples)
    return {
        "n": len(samples),
        "p50_ms": ordered[math.ceil(0.50 * len(samples)) - 1],
        "p95_ms": ordered[math.ceil(0.95 * len(samples)) - 1],
        "method": "nearest-rank; n=5 p95 is maximum, not a stable tail estimate",
        "samples_ms": samples,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--samples", type=int, default=5)
    args = ap.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum() or not 3 <= args.samples <= 10:
        ap.error("safe label required; samples must be 3..10")
    out = ROOT / "docs/qa/evidence" / ("performance-" + args.label)
    out.mkdir(parents=True, exist_ok=True)
    process = process_info()
    pid = process["pid"]
    if not pid:
        raise RuntimeError("No local backend listening on port 8000")
    baseline = rss_kib(pid)
    sampled = []
    stop = threading.Event()
    began = time.perf_counter()

    def sample():
        while not stop.is_set():
            sampled.append({"elapsed_s": time.perf_counter() - began, "rss_kib": rss_kib(pid)})
            stop.wait(0.05)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    results = {
        "label": args.label,
        "process": process,
        "baseline_rss_kib": baseline,
        "datasets": [],
        "errors": [],
        "measurement": "Sequential HTTP localhost only; total HTTP includes request/response transfer, parsing JSON excluded. ps RSS approximately every 50ms plus subprocess overhead; sampled maximum is NOT exact peak. Existing process/cache not cleared. No AI or public requests.",
    }
    try:
        for name, ticks in [("small", 100), ("medium", 5000), ("near-limit", 33333)]:
            path = out / (name + ".vcd")
            dataset = {
                "name": name,
                **generate(path, ticks),
                "runs": [],
                "rss_before_kib": rss_kib(pid),
            }
            results["datasets"].append(dataset)
            for i in range(args.samples):
                current = rss_kib(pid)
                if current is None or current > 700 * 1024:
                    raise RuntimeError(
                        f"RSS safety guard (700MiB) reached or process missing: {current}"
                    )
                trace, upload_meta = upload(path)
                if upload_meta["status"] != 200:
                    save(out / (name + "-upload-error.json"), trace)
                    raise RuntimeError(f"Upload {name}: {upload_meta}")
                actual_events = sum(len(s["events"]) for s in trace["signals"])
                # Check workload actually reached the server; not a logic oracle.
                if actual_events != dataset["events"]:
                    raise RuntimeError(
                        f"Event count mismatch {actual_events} vs {dataset['events']}"
                    )
                clock = next(s["id"] for s in trace["signals"] if s["name"].split(".")[-1] == "clk")
                body = {
                    "time": ticks // 2,
                    "signals": [s["id"] for s in trace["signals"]],
                    "window": ticks,
                    "clock": clock,
                }
                result, analysis_meta = request(
                    "/api/traces/" + trace["id"] + "/analysis", json.dumps(body).encode()
                )
                save(
                    out / f"{name}-{i + 1}-analysis.json",
                    {"request": body, "response": result, "meta": analysis_meta},
                )
                if analysis_meta["status"] != 200:
                    raise RuntimeError(f"Analysis {name}: {analysis_meta}")
                dataset["runs"].append(
                    {
                        "iteration": i + 1,
                        "upload": upload_meta,
                        "analysis": analysis_meta,
                        "returned_events": actual_events,
                        "trace_id": trace["id"],
                        "rss_after_kib": rss_kib(pid),
                        "analysis_truncated": [s["truncated"] for s in result["signals"]],
                    }
                )
                del trace, result
            dataset["upload"] = percentiles([r["upload"]["http_ms"] for r in dataset["runs"]])
            dataset["analysis"] = percentiles([r["analysis"]["http_ms"] for r in dataset["runs"]])
            dataset["rss_after_kib"] = rss_kib(pid)
    except Exception as exc:
        results["errors"].append(str(exc))
    finally:
        stop.set()
        thread.join(timeout=3)
        results["ending_rss_kib"] = rss_kib(pid)
        results["sampled_max_rss_kib"] = max(
            (s["rss_kib"] for s in sampled if s["rss_kib"] is not None), default=None
        )
        results["rss_sample_count"] = len(sampled)
        results["process_end"] = process_info()
        if results["process_end"]["pid"] != pid:
            results["errors"].append("Backend PID changed during benchmark")
        save(out / "rss-samples.json", sampled)
        results["verdict"] = "COMPLETE" if not results["errors"] else "BLOCKED"
        save(out / "results.json", results)
    lines = [
        "# API 性能验收",
        "",
        f"测量状态: **{results['verdict']}**。无预设 SLA，因此完成测量不等于满足某延迟/内存承诺。",
        "",
        "## 方法与基线",
        "仅本地 127.0.0.1:8000 的 upload/analysis，顺序请求，未调用 AI/公网。每个尺寸进行多次完整上传及其一次 analysis，无预热剔除，无并发；HTTP 时间包含传输和读取响应，不包含客户端 JSON 解码。analysis 覆盖全时间窗并启用 clock，128 条窗口截断属于 API 行为。",
        f"每尺寸计划 n={args.samples}；p50/p95 使用 nearest-rank；少样本 p95 通常为最大样本，只作描述，不能视为可靠尾延迟。",
        "确定性 3 信号（两个单比特与 208-bit 总线），每 tick 3 records。near-limit 逼近事件上限，同时保持文件小于 8MiB；没有超限/OOM压力试验，700MiB RSS 时停止后续请求。",
        "```",
        process["ps"],
        "```",
        f"开始时间: {process['captured_at']}；label={args.label}。不清空缓存；先前请求可能影响缓存与 RSS。进程不自动 reload，修改应用后必须重启再测。",
        "",
        "## 结果",
        "|输入|events|VCD bytes|n|upload p50/p95 ms|analysis p50/p95 ms|upload response bytes|analysis response bytes|",
        "|---|---:|---:|---:|---|---|---|---|",
    ]
    for d in results["datasets"]:
        if "upload" not in d:
            continue
        u, a = d["upload"], d["analysis"]
        lines.append(
            f"|{d['name']}|{d['events']}|{d['vcd_bytes']}|{len(d['runs'])}|{u['p50_ms']:.2f}/{u['p95_ms']:.2f}|{a['p50_ms']:.2f}/{a['p95_ms']:.2f}|{[r['upload']['response_body_bytes'] for r in d['runs']]}|{[r['analysis']['response_body_bytes'] for r in d['runs']]}|"
        )
    lines += [
        "",
        "## 内存（RSS，不是准确峰值）",
        f"单位 KiB；baseline={baseline}；结束={results['ending_rss_kib']}；采样最大值={results['sampled_max_rss_kib']}；样本数={len(sampled)}。",
        "使用 ps -p PID -o rss=，约50ms间隔加 ps 开销，可能漏过短时峰值；只观察监听进程，不包含客户端/浏览器、不推断内存泄漏。缓存保留最近4个波形，使基线与结束值非同一缓存状态。",
        "",
        "## 复现与证据",
        f"`python3 {ROOT}/scripts/qa_performance.py --label {args.label} --samples {args.samples}`",
        f"`{out}/results.json` 包含每次 HTTP 时间、请求体/响应体 bytes、事件数、输入SHA256；`rss-samples.json` 为 RSS 时间序列；*.vcd 为完整可重现输入；*-analysis.json 为所有 analysis 请求和响应。上传响应为大型事件数组，记录返回事件数/bytes而不重复存储五份完整数组。",
        "浏览器性能由主代理另行测量，本报告不代替页面渲染/交互指标。",
        "",
        "## 错误",
        *results["errors"],
    ]
    (ROOT / "docs/qa/performance-report.md").write_text(
        "\n".join(lines).replace(str(ROOT), ".") + "\n"
    )
    print(
        json.dumps(
            {"status": results["verdict"], "evidence": str(out), "errors": results["errors"]},
            ensure_ascii=False,
        )
    )
    return int(bool(results["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
