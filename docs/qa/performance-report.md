# API 性能验收

测量状态: **COMPLETE**。无预设 SLA，因此完成测量不等于满足某延迟/内存承诺。

## 方法与基线
仅本地 127.0.0.1:8000 的 upload/analysis，顺序请求，未调用 AI/公网。每个尺寸进行多次完整上传及其一次 analysis，无预热剔除，无并发；HTTP 时间包含传输和读取响应，不包含客户端 JSON 解码。analysis 覆盖全时间窗并启用 clock，128 条窗口截断属于 API 行为。
每尺寸计划 n=5；p50/p95 使用 nearest-rank；少样本 p95 通常为最大样本，只作描述，不能视为可靠尾延迟。
确定性 3 信号（两个单比特与 208-bit 总线），每 tick 3 records。near-limit 逼近事件上限，同时保持文件小于 8MiB；没有超限/OOM压力试验，700MiB RSS 时停止后续请求。
```
12757 一 11/16 23:19:26 2026       34208 /opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --limit-concurrency 16
```
开始时间: 2026-11-16T23:23:35.488055+08:00。本次是修复后重启的 PID 12757，label=final；不清空缓存，先前正确性请求可能影响 RSS。环境：macOS / Python 3.14.3 / Node 24.15.0。

## 结果
|输入|events|VCD bytes|n|upload p50/p95 ms|analysis p50/p95 ms|upload response bytes|analysis response bytes|
|---|---:|---:|---:|---|---|---|---|
|small|300|22340|5|18.30/41.44|5.90/7.00|[28361, 28361, 28361, 28361, 28361]|[30132, 30132, 30132, 30132, 30132]|
|medium|15000|1119040|5|677.67/806.98|7.46/13.84|[1422164, 1422164, 1422164, 1422164, 1422164]|[38145, 38145, 38145, 38145, 38145]|
|near-limit|99999|7488965|5|4404.55/4632.01|19.49/21.92|[9567073, 9567073, 9567073, 9567073, 9567073]|[38159, 38159, 38159, 38159, 38159]|

## 内存（RSS，不是准确峰值）
单位 KiB；baseline=34208；结束=159616；采样最大值=322256；样本数=442。
使用 ps -p PID -o rss=，约50ms间隔加 ps 开销，可能漏过短时峰值；只观察监听进程，不包含客户端/浏览器、不推断内存泄漏。缓存保留最近4个波形，使基线与结束值非同一缓存状态。

## 复现与证据
`python3 ./scripts/qa_performance.py --label final --samples 5`
`./docs/qa/evidence/performance-final/results.json` 包含每次 HTTP 时间、请求体/响应体 bytes、事件数、输入SHA256；`rss-samples.json` 为 RSS 时间序列；*.vcd 为完整可重现输入；*-analysis.json 为所有 analysis 请求和响应。上传响应为大型事件数组，记录返回事件数/bytes而不重复存储五份完整数组。
浏览器性能由主代理另行测量，本报告不代替页面渲染/交互指标。

## Chromium 真实交互测量

Chromium 159.0.8154.6，1600×1100，真实上传同一组三档VCD；每档1次，数值包含Playwright操作、浏览器调度和网络，不是纯渲染CPU时间，也不是统计p95。上传计时止于可见事实，cursor计时包括150ms防抖。证据：`evidence/browser-boundaries-final.json`。

| 输入 | 上传到事实 ms | Zoom操作 ms | 信号搜索 ms | cursor到事实 ms | SVG path数（缩放后） |
| --- | ---: | ---: | ---: | ---: | ---: |
| small | 386.03 | 99.10 | 10.38 | 263.91 | 126 |
| medium | 1663.72 | 625.49 | 149.12 | 796.16 | 5251 |
| near-limit | 5650.40 | 613.34 | 167.29 | 743.31 | 6001 |

中/大输入出现明确2000段截断提示。近上限输入存在约0.6秒缩放、0.74秒光标反馈，不适合宣传流畅工业级查看器。small golden path适合教学；不要提高8MiB/100k上限，后续应以Canvas/分页数据和窗口索引解决，而不是隐藏截断。RSS采样最大约314.7MiB，不包含浏览器。

## 错误
