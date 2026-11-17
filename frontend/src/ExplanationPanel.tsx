import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Analysis, AnalysisRequest, Explanation, Trace } from "./types";
export function ExplanationPanel({
  trace,
  request,
  analysis,
  configured,
}: {
  trace: Trace;
  request: AnalysisRequest;
  analysis: Analysis | null;
  configured: boolean;
}) {
  const [consent, setConsent] = useState(false);
  const [rtl, setRtl] = useState(false);
  const [question, setQuestion] = useState(
    "解释当前时刻的信号变化，并区分事实和推测。",
  );
  const [resultState, setResult] = useState<{
    context: string;
    data: Explanation;
  } | null>(null);
  const [errorState, setError] = useState<{
    context: string;
    message: string;
  } | null>(null);
  const [busyContext, setBusy] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const context = JSON.stringify([
    trace.id,
    request,
    trace.sources.length,
    question,
    consent,
    rtl,
  ]);
  // Render-time ownership prevents even a frame of old output under new labels.
  const result = resultState?.context === context ? resultState.data : null;
  const error = errorState?.context === context ? errorState.message : "";
  const busy = busyContext === context;
  useEffect(() => {
    controller.current?.abort();
    setResult(null);
    setError(null);
    setBusy(null);
    return () => controller.current?.abort();
  }, [context]);
  async function explain() {
    if (
      !configured ||
      !consent ||
      !analysis ||
      !request.signals.length ||
      !question.trim() ||
      (controller.current && !controller.current.signal.aborted)
    )
      return;
    const c = new AbortController();
    controller.current = c;
    setBusy(context);
    setError(null);
    setResult(null);
    try {
      const data = await api.explain(
        trace.id,
        { ...request, question, consent, include_rtl: rtl },
        c.signal,
      );
      if (!c.signal.aborted) setResult({ context, data });
    } catch (e) {
      if (!c.signal.aborted)
        setError({
          context,
          message: e instanceof Error ? e.message : "AI 请求失败",
        });
    } finally {
      if (!c.signal.aborted) setBusy(null);
      if (controller.current === c) controller.current = null;
    }
  }
  return (
    <section className="ai-panel">
      <div className="panel-heading">
        <h2>AI Explanation</h2>
        <span className="badge">{configured ? "Optional" : "Offline"}</span>
      </div>
      <p className="muted small">
        无 API key 也能使用全部波形、事实分析、RTL 和报告功能。AI
        仅作辅助，不能替代仿真证据。
      </p>
      {!configured && (
        <p className="muted small">
          先在页面上方“模型配置”填写地址和 API Key
          并保存；上传波形与离线事实分析无需等待配置。
        </p>
      )}
      <textarea
        aria-label="向 AI 提问"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={3}
        maxLength={2000}
      />
      <p className="muted small">
        {question.length} / 2000 ·
        修改问题或授权会取消等待并清除旧结果；已发送的数据无法撤回。
      </p>
      <label className="consent">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        我确认将选中信号、分析窗口事件、光标相邻记录、手动配置的 Clock/Reset
        信息及问题发送给服务端配置的 AI 提供商。
      </label>
      <p className="muted small">
        {analysis
          ? `实际分析窗口：${analysis.window.start}–${analysis.window.end} ticks（1 tick = ${analysis.timescale}）。`
          : "分析就绪后显示实际发送窗口。"}
        窗口以光标为中心，不一定等于可见视口；相邻记录可能位于窗口外。每个信号最多
        128 条窗口记录。
      </p>
      <label className="consent">
        <input
          type="checkbox"
          checked={rtl}
          onChange={(e) => setRtl(e.target.checked)}
        />
        独立授权：同时发送名称匹配到的 RTL 片段（可不选）
      </label>
      <div className="toolbar">
        <button
          className="primary"
          disabled={
            !configured ||
            !consent ||
            !request.signals.length ||
            !analysis ||
            busy ||
            !question.trim()
          }
          onClick={explain}
        >
          生成解释
        </button>
        {busy && (
          <button
            onClick={() => {
              controller.current?.abort();
              setBusy(null);
              setError({
                context,
                message:
                  "请求已取消。已发送的数据无法撤回，第三方可能继续处理或计费。",
              });
            }}
          >
            取消请求
          </button>
        )}
      </div>
      {busy && <p role="status">正在请求解释…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {result && (
        <div className="explanation-result">
          <p className="context">
            所属 cursor：{request.time} ticks
            <br />
            信号：
            {request.signals
              .map((id) => trace.signals.find((s) => s.id === id)?.name ?? id)
              .join(", ")}
          </p>
          <p>{result.summary}</p>
          {(
            [
              ["observed_facts", "观察事实"],
              ["possible_explanations", "可能解释 · 非已证实因果"],
              ["related_signals", "相关信号"],
              ["related_code", "相关代码"],
              ["suggested_checks", "建议检查"],
              ["limitations", "局限"],
            ] as const
          ).map(([key, title]) => (
            <section key={key}>
              <h3>{title}</h3>
              <ul>
                {result[key].map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
