# 独立数字正确性验收

Verdict: **PASS** — 81/81 checks
检查中含1项进程PID一致性，其余为数字值/记录检查；不把进程检查计作数字正确性。

## 方法与范围
真实 HTTP POST /api/traces → /api/traces/{id}/analysis；不 import app、不调用 AI、不运行用户 RTL。仅编译固定自写 fixture 与复制的内置 examples。预期为人工推导的整数模型/常量表，不从 API 或 VCD 反推。Icarus 生成的 VCD 是输入，不作为唯一正确性 oracle。

Counter: reset 优先，enable 门控，(count+1)%16；FIFO: 深度4、边沿前 full/empty 决定 admission；握手: pre-edge valid&&ready 传输 A1@55/A2@95/A3@105，光标在边沿上则显示 post-edge。X/Z 直接使用 SV 四态字面量。

## 基线进程
```
4 Tue Nov 17 11:15:14 2026 47388 .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --limit-concurrency 16
```
采样时间: 2026-11-17T11:15:16.130189+08:00
运行标签：responses-20261117。进程不自动 reload，修改应用后必须重启再测；进程信息用于区分基线与修复后执行。

## 逐项 expected / actual
|类别|ns|expected|actual|结果|
|---|---:|---|---|---|
|ordinary-counter|5|`{'count': '0000'}`|`{'count': '0000'}`|PASS|
|ordinary-counter|15|`{'count': '0000'}`|`{'count': '0000'}`|PASS|
|ordinary-counter|25|`{'count': '0001'}`|`{'count': '0001'}`|PASS|
|ordinary-counter|35|`{'count': '0010'}`|`{'count': '0010'}`|PASS|
|ordinary-counter|45|`{'count': '0011'}`|`{'count': '0011'}`|PASS|
|ordinary-counter|55|`{'count': '0100'}`|`{'count': '0100'}`|PASS|
|ordinary-counter|65|`{'count': '0101'}`|`{'count': '0101'}`|PASS|
|ordinary-counter|75|`{'count': '0110'}`|`{'count': '0110'}`|PASS|
|ordinary-counter|85|`{'count': '0111'}`|`{'count': '0111'}`|PASS|
|ordinary-counter|95|`{'count': '1000'}`|`{'count': '1000'}`|PASS|
|ordinary-counter|105|`{'count': '1001'}`|`{'count': '1001'}`|PASS|
|ordinary-counter|115|`{'count': '1010'}`|`{'count': '1010'}`|PASS|
|ordinary-counter|125|`{'count': '1010'}`|`{'count': '1010'}`|PASS|
|ordinary-counter|135|`{'count': '1010'}`|`{'count': '1010'}`|PASS|
|ordinary-counter|145|`{'count': '1010'}`|`{'count': '1010'}`|PASS|
|ordinary-counter|155|`{'count': '1011'}`|`{'count': '1011'}`|PASS|
|ordinary-counter|165|`{'count': '1100'}`|`{'count': '1100'}`|PASS|
|ordinary-counter|175|`{'count': '1101'}`|`{'count': '1101'}`|PASS|
|ordinary-counter|185|`{'count': '1110'}`|`{'count': '1110'}`|PASS|
|ordinary-counter|195|`{'count': '1111'}`|`{'count': '1111'}`|PASS|
|ordinary-counter|205|`{'count': '0000'}`|`{'count': '0000'}`|PASS|
|ordinary-counter|215|`{'count': '0000'}`|`{'count': '0000'}`|PASS|
|ordinary-counter|225|`{'count': '0001'}`|`{'count': '0001'}`|PASS|
|ordinary-counter|235|`{'count': '0000'}`|`{'count': '0000'}`|PASS|
|ordinary-counter|120|`{'count': '1010'}`|`{'count': '1010'}`|PASS|
|ordinary-counter|149|`{'count': '1010'}`|`{'count': '1010'}`|PASS|
|overflow|195|`{'count': '1111'}`|`{'count': '1111'}`|PASS|
|overflow|205|`{'count': '0000'}`|`{'count': '0000'}`|PASS|
|synchronous-reset|225|`{'count': '0001'}`|`{'count': '0001'}`|PASS|
|synchronous-reset|232|`{'count': '0001'}`|`{'count': '0001'}`|PASS|
|synchronous-reset|233|`{'count': '0001'}`|`{'count': '0001'}`|PASS|
|synchronous-reset|235|`{'count': '0000'}`|`{'count': '0000'}`|PASS|
|fifo-boundary|25|`{'count': '001', 'rd_data': '00000000', 'full': '0', 'empty': '0'}`|`{'count': '001', 'rd_data': '00000000', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|35|`{'count': '010', 'rd_data': '00000000', 'full': '0', 'empty': '0'}`|`{'count': '010', 'rd_data': '00000000', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|45|`{'count': '011', 'rd_data': '00000000', 'full': '0', 'empty': '0'}`|`{'count': '011', 'rd_data': '00000000', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|55|`{'count': '100', 'rd_data': '00000000', 'full': '1', 'empty': '0'}`|`{'count': '100', 'rd_data': '00000000', 'full': '1', 'empty': '0'}`|PASS|
|fifo-boundary|65|`{'count': '100', 'rd_data': '00000000', 'full': '1', 'empty': '0'}`|`{'count': '100', 'rd_data': '00000000', 'full': '1', 'empty': '0'}`|PASS|
|fifo-boundary|75|`{'count': '011', 'rd_data': '00010001', 'full': '0', 'empty': '0'}`|`{'count': '011', 'rd_data': '00010001', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|85|`{'count': '011', 'rd_data': '00100010', 'full': '0', 'empty': '0'}`|`{'count': '011', 'rd_data': '00100010', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|95|`{'count': '010', 'rd_data': '00110011', 'full': '0', 'empty': '0'}`|`{'count': '010', 'rd_data': '00110011', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|105|`{'count': '001', 'rd_data': '01000100', 'full': '0', 'empty': '0'}`|`{'count': '001', 'rd_data': '01000100', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|115|`{'count': '000', 'rd_data': '01010101', 'full': '0', 'empty': '1'}`|`{'count': '000', 'rd_data': '01010101', 'full': '0', 'empty': '1'}`|PASS|
|fifo-boundary|125|`{'count': '000', 'rd_data': '01010101', 'full': '0', 'empty': '1'}`|`{'count': '000', 'rd_data': '01010101', 'full': '0', 'empty': '1'}`|PASS|
|fifo-boundary|135|`{'count': '001', 'rd_data': '01010101', 'full': '0', 'empty': '0'}`|`{'count': '001', 'rd_data': '01010101', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|145|`{'count': '000', 'rd_data': '01100110', 'full': '0', 'empty': '1'}`|`{'count': '000', 'rd_data': '01100110', 'full': '0', 'empty': '1'}`|PASS|
|fifo-boundary|155|`{'count': '001', 'rd_data': '01100110', 'full': '0', 'empty': '0'}`|`{'count': '001', 'rd_data': '01100110', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|165|`{'count': '010', 'rd_data': '01100110', 'full': '0', 'empty': '0'}`|`{'count': '010', 'rd_data': '01100110', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|175|`{'count': '011', 'rd_data': '01100110', 'full': '0', 'empty': '0'}`|`{'count': '011', 'rd_data': '01100110', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|185|`{'count': '100', 'rd_data': '01100110', 'full': '1', 'empty': '0'}`|`{'count': '100', 'rd_data': '01100110', 'full': '1', 'empty': '0'}`|PASS|
|fifo-boundary|195|`{'count': '011', 'rd_data': '01110111', 'full': '0', 'empty': '0'}`|`{'count': '011', 'rd_data': '01110111', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|205|`{'count': '010', 'rd_data': '10001000', 'full': '0', 'empty': '0'}`|`{'count': '010', 'rd_data': '10001000', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|215|`{'count': '001', 'rd_data': '10011001', 'full': '0', 'empty': '0'}`|`{'count': '001', 'rd_data': '10011001', 'full': '0', 'empty': '0'}`|PASS|
|fifo-boundary|225|`{'count': '000', 'rd_data': '10101010', 'full': '0', 'empty': '1'}`|`{'count': '000', 'rd_data': '10101010', 'full': '0', 'empty': '1'}`|PASS|
|ready-valid|35|`{'data': '10100001', 'valid': '1', 'sent': '00', 'ready': '0'}`|`{'data': '10100001', 'valid': '1', 'sent': '00', 'ready': '0'}`|PASS|
|ready-valid|45|`{'data': '10100001', 'valid': '1', 'sent': '00', 'ready': '0'}`|`{'data': '10100001', 'valid': '1', 'sent': '00', 'ready': '0'}`|PASS|
|ready-valid|54.999|`{'data': '10100001', 'valid': '1', 'sent': '00', 'ready': '1'}`|`{'data': '10100001', 'valid': '1', 'sent': '00', 'ready': '1'}`|PASS|
|ready-valid|55|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '1'}`|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '1'}`|PASS|
|ready-valid|65|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '0'}`|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '0'}`|PASS|
|ready-valid|75|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '0'}`|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '0'}`|PASS|
|ready-valid|85|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '0'}`|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '0'}`|PASS|
|ready-valid|94.999|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '1'}`|`{'data': '10100010', 'valid': '1', 'sent': '01', 'ready': '1'}`|PASS|
|ready-valid|95|`{'data': '10100011', 'valid': '1', 'sent': '10', 'ready': '1'}`|`{'data': '10100011', 'valid': '1', 'sent': '10', 'ready': '1'}`|PASS|
|ready-valid|104.999|`{'data': '10100011', 'valid': '1', 'sent': '10', 'ready': '1'}`|`{'data': '10100011', 'valid': '1', 'sent': '10', 'ready': '1'}`|PASS|
|ready-valid|105|`{'data': '10100011', 'valid': '0', 'sent': '11', 'ready': '1'}`|`{'data': '10100011', 'valid': '0', 'sent': '11', 'ready': '1'}`|PASS|
|ready-valid|125|`{'data': '10100011', 'valid': '0', 'sent': '11', 'ready': '1'}`|`{'data': '10100011', 'valid': '0', 'sent': '11', 'ready': '1'}`|PASS|
|synchronous-reset|5|`{'sync_count': '0000', 'async_count': '0000'}`|`{'sync_count': '0000', 'async_count': '0000'}`|PASS|
|synchronous-reset|15|`{'sync_count': '0001', 'async_count': '0001'}`|`{'sync_count': '0001', 'async_count': '0001'}`|PASS|
|overflow|165|`{'sync_count': '0000', 'async_count': '0000'}`|`{'sync_count': '0000', 'async_count': '0000'}`|PASS|
|synchronous-reset|175|`{'sync_count': '0001', 'async_count': '0001'}`|`{'sync_count': '0001', 'async_count': '0001'}`|PASS|
|asynchronous-reset|182|`{'sync_count': '0001', 'async_count': '0000'}`|`{'sync_count': '0001', 'async_count': '0000'}`|PASS|
|asynchronous-reset|184|`{'sync_count': '0001', 'async_count': '0000'}`|`{'sync_count': '0001', 'async_count': '0000'}`|PASS|
|synchronous-reset|185|`{'sync_count': '0000', 'async_count': '0000'}`|`{'sync_count': '0000', 'async_count': '0000'}`|PASS|
|synchronous-reset|195|`{'sync_count': '0001', 'async_count': '0001'}`|`{'sync_count': '0001', 'async_count': '0001'}`|PASS|
|multi-bit-X-Z|0|`{'bus': 'xxxx'}`|`{'bus': 'xxxx'}`|PASS|
|multi-bit-X-Z|183|`{'bus': 'zzzz'}`|`{'bus': 'zzzz'}`|PASS|
|multi-bit-X-Z|184|`{'bus': 'x1z0'}`|`{'bus': 'x1z0'}`|PASS|
|multi-bit-X-Z|188|`{'bus': '0011'}`|`{'bus': '0011'}`|PASS|
|same-tick|187|`{'marker': '0'}`|`{'marker': '0'}`|PASS|
|same-tick|1|`{'value': 'x1z0'}`|`{'value': 'x1z0'}`|PASS|
|same-tick-record-order|-|`['0001', '0010', 'x1z0']`|`['0001', '0010', 'x1z0']`|PASS|
|baseline-process-identity|-|`4`|`4`|PASS|

## 复现与证据
`python3 ./scripts/qa_correctness.py --label responses-20261117`
证据目录：`./docs/qa/evidence/correctness-responses-20261117`。results.json 含所有请求/响应和逐项判定；*-upload.json 为上传完整响应；子目录保存 SV、VCD、Icarus 命令和日志。same-tick.vcd 专门验证文件内同 tick 记录顺序。
本报告按 label 保存，不覆盖历史汇总或同名证据；未测浏览器，由主代理另行完成。
