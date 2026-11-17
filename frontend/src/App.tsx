import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { Explorer } from "./Explorer";
import { Waveform } from "./Waveform";
import { RTLViewer } from "./RTLViewer";
import { ExplanationPanel } from "./ExplanationPanel";
import { ModelSettings } from "./ModelSettings";
import { downloadReport, formatValue } from "./utils";
import type { Analysis, AnalysisRequest, Trace } from "./types";
export default function App() {
  const [trace, setTrace] = useState<Trace | null>(null),
    [selected, setSelected] = useState<string[]>([]),
    [time, setTime] = useState(0),
    [view, setView] = useState<[number, number]>([0, 1]);
  const [clock, setClock] = useState(""),
    [reset, setReset] = useState(""),
    [edge, setEdge] = useState<AnalysisRequest["edge"]>("rising"),
    [active, setActive] = useState<"0" | "1">("1"),
    [mode, setMode] = useState<AnalysisRequest["reset_mode"]>("unknown");
  const [health, setHealth] = useState<{
      ai_configured: boolean;
      requests: number;
      ai_config_revision?: string;
    } | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [sourceBusy, setSourceBusy] = useState(false),
    [reportBusy, setReportBusy] = useState(false),
    [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisState, setAnalysis] = useState<{
      key: string;
      data: Analysis;
    } | null>(null),
    [analysisError, setAnalysisError] = useState("");
  const loadController = useRef<AbortController | null>(null),
    sourceController = useRef<AbortController | null>(null),
    reportController = useRef<AbortController | null>(null),
    analysisController = useRef<AbortController | null>(null);
  const request = useMemo<AnalysisRequest>(
    () => ({
      time,
      signals: selected,
      window: Math.max(1, view[1] - view[0]),
      clock: clock || null,
      edge,
      reset: reset || null,
      reset_active: active,
      reset_mode: mode,
    }),
    [time, selected, view, clock, edge, reset, active, mode],
  );
  const key = JSON.stringify([trace?.id, request, trace?.sources.length]);
  const analysis = analysisState?.key === key ? analysisState.data : null;
  useEffect(() => {
    const c = new AbortController();
    api
      .health(c.signal)
      .then((value) => setHealth((current) => current ?? value))
      .catch(() => {});
    return () => {
      c.abort();
      loadController.current?.abort();
      sourceController.current?.abort();
      reportController.current?.abort();
    };
  }, []);
  useEffect(() => {
    const c = new AbortController();
    analysisController.current = c;
    setAnalysis(null);
    setAnalysisError("");
    reportController.current?.abort();
    setReportBusy(false);
    if (!trace || !selected.length) {
      setAnalysisBusy(false);
      return () => c.abort();
    }
    setAnalysisBusy(true);
    const timer = setTimeout(() => {
      api
        .analysis(trace.id, request, c.signal)
        .then((data) => {
          if (!c.signal.aborted) setAnalysis({ key, data });
        })
        .catch((e) => {
          if (!c.signal.aborted) setAnalysisError(e.message);
        })
        .finally(() => {
          if (!c.signal.aborted) setAnalysisBusy(false);
        });
    }, 150);
    return () => {
      clearTimeout(timer);
      c.abort();
    };
  }, [key]);
  async function load(input: File | string) {
    loadController.current?.abort();
    sourceController.current?.abort();
    reportController.current?.abort();
    analysisController.current?.abort();
    const c = new AbortController();
    loadController.current = c;
    setBusy(true);
    setSourceBusy(false);
    setTrace(null);
    setAnalysis(null);
    setError("");
    try {
      const t =
        typeof input === "string"
          ? await api.demo(input, c.signal)
          : await api.trace(input, c.signal);
      if (c.signal.aborted) return;
      setTrace(t);
      setSelected(t.signals.slice(0, 8).map((s) => s.id));
      setTime(t.start);
      setView([t.start, t.end]);
      setClock("");
      setReset("");
      setMode("unknown");
      setEdge("rising");
      setActive("1");
    } catch (e) {
      if (!c.signal.aborted)
        setError(e instanceof Error ? e.message : "载入失败");
    } finally {
      if (!c.signal.aborted) setBusy(false);
    }
  }
  async function uploadSource(file: File) {
    if (!trace) return;
    sourceController.current?.abort();
    const c = new AbortController();
    sourceController.current = c;
    setSourceBusy(true);
    setError("");
    try {
      const source = await api.source(trace.id, file, c.signal);
      if (!c.signal.aborted)
        setTrace((t) =>
          t && t.id === trace.id
            ? {
                ...t,
                sources: [
                  ...t.sources.filter((s) => s.name !== source.name),
                  source,
                ],
              }
            : t,
        );
    } catch (e) {
      if (!c.signal.aborted)
        setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      if (!c.signal.aborted) setSourceBusy(false);
    }
  }
  async function report() {
    if (!trace || !selected.length) return;
    reportController.current?.abort();
    const c = new AbortController();
    reportController.current = c;
    setReportBusy(true);
    setError("");
    try {
      const text = await api.report(trace.id, request, c.signal);
      if (!c.signal.aborted) downloadReport(text, `waveform-${time}.md`);
    } catch (e) {
      if (!c.signal.aborted)
        setError(e instanceof Error ? e.message : "报告失败");
    } finally {
      if (!c.signal.aborted) setReportBusy(false);
    }
  }
  const signals = useMemo(
    () => trace?.signals.filter((s) => selected.includes(s.id)) ?? [],
    [trace?.signals, selected],
  );
  return (
    <>
      <header className="app-header">
        <a className="brand" href="/">
          ▥{" "}
          <span>
            WAVEFORM<span className="brand-light"> TUTOR</span>
          </span>
        </a>
        <span className="header-caption">DIGITAL LOGIC / EVIDENCE FIRST</span>
        <span className={`status ${health ? "connected" : ""}`}>
          {health
            ? health.ai_configured
              ? "AI configured · on demand"
              : "Offline analysis · no AI key"
            : "Backend not connected"}
        </span>
      </header>
      <main>
        <section className={`hero ${trace ? "compact" : ""}`}>
          <div>
            <div className="eyebrow">YOUR DIGITAL DESIGN WORKBENCH</div>
            <h1>
              Understand Digital Waveforms,
              <br />
              <span>Not Just View Them</span>
            </h1>
            <p>
              从真实事件出发，连接信号、RTL 与时序事实。让每一次跳变都有据可查。
            </p>
          </div>
          <div className="load-controls">
            <div className="demo-buttons">
              {(["counter", "fifo", "handshake"] as const).map((name, i) => (
                <button key={name} onClick={() => load(name)}>
                  <small>0{i + 1} / DEMO</small>
                  <strong>
                    {name === "counter"
                      ? "Counter"
                      : name === "fifo"
                        ? "FIFO"
                        : "Handshake"}
                  </strong>
                  <span>打开案例 ↗</span>
                </button>
              ))}
            </div>
            <label className="upload button">
              上传 VCD <span className="muted">本地文件 → 本地后端解析</span>
              <input
                hidden
                aria-label="上传 VCD"
                type="file"
                accept=".vcd"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) load(f);
                  e.target.value = "";
                }}
              />
            </label>
          </div>
        </section>
        <ModelSettings
          onChange={(value) =>
            setHealth({
              ai_configured: value.configured,
              requests: 0,
              ai_config_revision: value.revision,
            })
          }
        />
        {busy && (
          <div className="notice" role="status">
            正在解析波形…{" "}
            <button
              onClick={() => {
                loadController.current?.abort();
                setBusy(false);
              }}
            >
              取消
            </button>
          </div>
        )}
        {error && (
          <div role="alert" className="error notice">
            {error}
          </div>
        )}
        {!trace && !busy && (
          <section className="welcome-grid">
            <div>
              <b>01 / Inspect</b>
              <h2>精确到每个 tick</h2>
              <p>交互式波形、未知态保留、分层信号探索。</p>
            </div>
            <div>
              <b>02 / Connect</b>
              <h2>让源码与波形相遇</h2>
              <p>查看 RTL，与选中信号相关的名称匹配行。</p>
            </div>
            <div>
              <b>03 / Explain</b>
              <h2>事实优先，推测分开</h2>
              <p>无需 AI key 即可分析；发送数据前由你授权。</p>
            </div>
          </section>
        )}
        {trace && (
          <>
            <div className="trace-bar">
              <div>
                <strong>{trace.name}</strong>
                <span className="muted">
                  {trace.signals.length} signals · {trace.start}–{trace.end}{" "}
                  ticks · {trace.timescale}
                </span>
              </div>
              <button
                disabled={!selected.length || reportBusy}
                onClick={report}
              >
                {reportBusy ? "生成报告…" : "下载 Markdown 报告 ↓"}
              </button>
            </div>
            {trace.warnings.map((w, i) => (
              <p className="warning" key={i}>
                {w}
              </p>
            ))}
            <div className="workspace">
              <Explorer
                signals={trace.signals}
                selected={selected}
                onChange={setSelected}
              />
              <div className="center-column">
                <Waveform
                  trace={trace}
                  signals={signals}
                  time={time}
                  onTime={setTime}
                  view={view}
                  onView={setView}
                />
                <section className="panel configuration">
                  <div className="panel-heading">
                    <h2>Timing Context</h2>
                    <span className="muted small">
                      手动配置 · 不猜测 reset 类型
                    </span>
                  </div>
                  <div className="config-grid">
                    <label>
                      Clock
                      <select
                        aria-label="Clock"
                        value={clock}
                        onChange={(e) => setClock(e.target.value)}
                      >
                        <option value="">未指定</option>
                        {trace.signals
                          .filter((s) => s.width === 1)
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Edge
                      <select
                        value={edge}
                        onChange={(e) => setEdge(e.target.value as typeof edge)}
                      >
                        <option value="rising">Rising ↑</option>
                        <option value="falling">Falling ↓</option>
                      </select>
                    </label>
                    <label>
                      Reset
                      <select
                        value={reset}
                        onChange={(e) => setReset(e.target.value)}
                      >
                        <option value="">未指定</option>
                        {trace.signals
                          .filter((s) => s.width === 1)
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Active
                      <select
                        value={active}
                        onChange={(e) =>
                          setActive(e.target.value as typeof active)
                        }
                      >
                        <option>1</option>
                        <option>0</option>
                      </select>
                    </label>
                    <label>
                      Reset mode
                      <select
                        value={mode}
                        onChange={(e) => setMode(e.target.value as typeof mode)}
                      >
                        <option value="unknown">Unknown</option>
                        <option value="synchronous">Synchronous</option>
                        <option value="asynchronous">Asynchronous</option>
                      </select>
                    </label>
                  </div>
                </section>
                <RTLViewer
                  sources={trace.sources}
                  signals={signals}
                  onUpload={uploadSource}
                  busy={sourceBusy}
                />
              </div>
              <aside className="panel insights">
                <div className="panel-heading">
                  <h2>Evidence & Insights</h2>
                  <span className="badge">@ {time}</span>
                </div>
                <p className="muted small">
                  真实事件来自 VCD · 所有时间均为 ticks
                </p>
                {analysisBusy && <p role="status">更新观察事实…</p>}
                {analysisError && (
                  <p role="alert" className="error">
                    {analysisError}
                  </p>
                )}
                {!selected.length && (
                  <p className="empty">请选择信号；未发送分析请求。</p>
                )}
                {analysis && (
                  <>
                    <h3>观察事实</h3>
                    <ul className="facts">
                      {analysis.observed_facts.map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                    {analysis.clock && (
                      <p className="context">
                        Clock {analysis.clock.name} · {analysis.clock.edge}
                        <br />
                        前一边沿 {analysis.clock.previous ?? "—"} / 后一边沿{" "}
                        {analysis.clock.next ?? "—"}
                        {analysis.clock.at_time ? " · 当前是边沿" : ""}
                      </p>
                    )}
                    {analysis.reset && (
                      <p className="context">
                        Reset {analysis.reset.name} ={" "}
                        {analysis.reset.value ?? "尚无记录"} ·{" "}
                        {analysis.reset.active === null
                          ? "未知"
                          : analysis.reset.active
                            ? "有效"
                            : "无效"}{" "}
                        · {analysis.reset.mode}
                      </p>
                    )}
                    <h3>真实事件 / 当前值</h3>
                    {analysis.signals.map((s) => (
                      <details className="event-card" key={s.id}>
                        <summary>
                          <span>{s.name}</span>
                          <code>{formatValue(s.value, "hex")}</code>
                        </summary>
                        <p>
                          Previous:{" "}
                          {s.previous
                            ? `${s.previous.time} → ${s.previous.value}`
                            : "—"}
                          <br />
                          Next:{" "}
                          {s.next ? `${s.next.time} → ${s.next.value}` : "—"}
                        </p>
                        <div className="events">
                          {s.events.map((ev, i) => (
                            <div key={i}>
                              <button onClick={() => setTime(ev.time)}>
                                {ev.time}
                              </button>
                              <code>{ev.value}</code>
                            </div>
                          ))}
                        </div>
                        {s.truncated && (
                          <p className="warning">
                            事件列表已截断，请缩小窗口。
                          </p>
                        )}
                      </details>
                    ))}
                    {analysis.related_code.length > 0 && (
                      <details>
                        <summary>相关代码（仅名称匹配）</summary>
                        {analysis.related_code.map((r, i) => (
                          <p className="small" key={i}>
                            {r.file}:{r.line} · {r.signal}
                            <br />
                            <code>{r.text}</code>
                          </p>
                        ))}
                      </details>
                    )}
                    <ul className="limitations">
                      {analysis.limitations.map((l, i) => (
                        <li key={i}>{l}</li>
                      ))}
                    </ul>
                  </>
                )}
                <ExplanationPanel
                  key={`${trace.id}:${health?.ai_config_revision ?? "initial"}`}
                  trace={trace}
                  request={request}
                  analysis={analysis}
                  configured={health?.ai_configured ?? false}
                />
              </aside>
            </div>
          </>
        )}
        <footer className="page-footer">
          WAVEFORM TUTOR{" "}
          <span>
            Local-first workflow · No external fonts, assets or analytics
          </span>
        </footer>
      </main>
    </>
  );
}
