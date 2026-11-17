import { useId, useMemo, useState } from "react";
import type { Format, Signal, Trace } from "./types";
import {
  zoomWindow,
  panWindow,
  clipSegments,
  formatValue,
  formatTime,
  parseTick,
  valueAt,
} from "./utils";
const color = (value: string | null) =>
  value === null
    ? "#64748b"
    : /x/i.test(value)
      ? "#fb7185"
      : /z/i.test(value)
        ? "#c084fc"
        : value === "0"
          ? "#60a5fa"
          : "#34d399";
export function Waveform({
  trace,
  signals,
  time,
  onTime,
  view,
  onView,
}: {
  trace: Trace;
  signals: Signal[];
  time: number;
  onTime: (n: number) => void;
  view: [number, number];
  onView: (v: [number, number]) => void;
}) {
  const [format, setFormat] = useState<Format>("hex");
  const [invalid, setInvalid] = useState(false);
  const id = useId();
  const [start, end] = view;
  const span = Math.max(1, end - start);
  const x = (n: number) => ((n - start) / span) * 800;
  const rows = useMemo(
    () =>
      signals.map((s) => ({
        signal: s,
        ...clipSegments(s.events, start, end),
      })),
    [signals, start, end],
  );
  function zoom(factor: number) {
    onView(zoomWindow(start, end, time, factor, trace.start, trace.end));
  }
  return (
    <section className="panel waveform">
      <div className="panel-heading">
        <h2>Timing Diagram</h2>
        <span className="badge">{trace.timescale} / tick</span>
      </div>
      <div className="toolbar">
        <button onClick={() => zoom(0.5)} aria-label="放大">
          Zoom +
        </button>
        <button onClick={() => zoom(2)} aria-label="缩小">
          Zoom −
        </button>
        <button
          onClick={() =>
            onView(panWindow(start, end, -1, trace.start, trace.end))
          }
          aria-label="向前平移"
        >
          ←
        </button>
        <button
          onClick={() =>
            onView(panWindow(start, end, 1, trace.start, trace.end))
          }
          aria-label="向后平移"
        >
          →
        </button>
        <button onClick={() => onView([trace.start, trace.end])}>Fit</button>
        <select
          aria-label="总线显示格式"
          value={format}
          onChange={(e) => setFormat(e.target.value as Format)}
        >
          <option>bin</option>
          <option>hex</option>
          <option>dec</option>
        </select>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const n = parseTick(
              String(new FormData(e.currentTarget).get("tick") ?? ""),
              trace.start,
              trace.end,
            );
            setInvalid(n === null);
            if (n !== null) onTime(n);
          }}
        >
          <label>
            Cursor{" "}
            <input
              key={time}
              aria-label="整数 tick"
              type="text"
              inputMode="numeric"
              name="tick"
              defaultValue={time}
            />
          </label>
          <button>跳转</button>
        </form>
      </div>
      {invalid && (
        <p role="alert" className="error">
          请输入 {trace.start}–{trace.end} 之间的安全整数 tick。
        </p>
      )}
      <div className="legend">
        <span style={{ color: color("0") }}>● 0</span>
        <span style={{ color: color("1") }}>● 1 / Bus</span>
        <span style={{ color: color("x") }}>● X unknown</span>
        <span style={{ color: color("z") }}>● Z high impedance</span>
      </div>
      <div className="wave-body">
        <div className="wave-labels">
          <div className="axis-label">SIGNAL / VALUE</div>
          {signals.map((s) => (
            <div key={s.id} title={s.name}>
              <strong>{s.name.split(".").at(-1)}</strong>
              <code>{formatValue(valueAt(s.events, time), format)}</code>
            </div>
          ))}
        </div>
        <svg
          style={{ height: 40 + signals.length * 58 }}
          role="img"
          aria-label="交互式数字波形，点击设置 cursor"
          viewBox={`0 0 800 ${40 + signals.length * 58}`}
          preserveAspectRatio="none"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            onTime(
              Math.max(
                start,
                Math.min(
                  end,
                  Math.round(
                    start + ((e.clientX - rect.left) / rect.width) * span,
                  ),
                ),
              ),
            );
          }}
        >
          <defs>
            <clipPath id={id}>
              <rect width="800" height={40 + signals.length * 58} />
            </clipPath>
          </defs>
          <g clipPath={`url(#${id})`}>
            {Array.from({ length: 9 }, (_, i) => (
              <g key={i}>
                <line
                  x1={i * 100}
                  x2={i * 100}
                  y1={25}
                  y2={40 + signals.length * 58}
                  stroke="#263246"
                  strokeDasharray="3 5"
                />
                <text
                  x={i * 100 + (i === 8 ? -5 : 5)}
                  y="17"
                  textAnchor={i === 8 ? "end" : "start"}
                  fill="#8b9bb3"
                  fontSize="11"
                >
                  {start + Math.round(((end - start) * i) / 8)}
                </text>
              </g>
            ))}
            {rows.map(({ signal, segments }, row) => (
              <g key={signal.id} transform={`translate(0 ${40 + row * 58})`}>
                <line x2="800" y1="50" y2="50" stroke="#1a2434" />
                {segments.map((s, i) => {
                  const left = x(s.start),
                    right = x(s.end),
                    c = color(s.value);
                  const label = formatValue(s.value, format);
                  const capacity = Math.max(
                    1,
                    Math.floor((right - left - 12) / 8),
                  );
                  const display =
                    label.length > capacity
                      ? label.slice(0, capacity - 1) + "…"
                      : label;
                  if (signal.width > 1)
                    return (
                      <g key={i}>
                        <title>{`${signal.name} · ${s.start}–${s.end} ticks · ${label}`}</title>
                        <path
                          d={`M${left},25 L${Math.min(left + 4, right)},8 H${Math.max(left, right - 4)} L${right},25 L${Math.max(left, right - 4)},42 H${Math.min(left + 4, right)} Z`}
                          fill={c}
                          fillOpacity=".08"
                          stroke={c}
                        />
                        {right - left > 50 && (
                          <text
                            x={(left + right) / 2}
                            y="29"
                            textAnchor="middle"
                            fill={c}
                            fontSize="12"
                            textLength={Math.min(
                              display.length * 7,
                              right - left - 12,
                            )}
                            lengthAdjust="spacingAndGlyphs"
                          >
                            {display}
                          </text>
                        )}
                      </g>
                    );
                  const y = s.value === "1" ? 8 : s.value === "0" ? 42 : 25;
                  const prev = segments[i - 1]?.value;
                  const py = prev === "1" ? 8 : prev === "0" ? 42 : 25;
                  return (
                    <g key={i}>
                      <path
                        d={`M${left},${i ? py : y} V${y} H${right}`}
                        stroke={c}
                        strokeWidth="2"
                        fill="none"
                      />
                      {s.value !== "0" &&
                        s.value !== "1" &&
                        right - left > 20 && (
                          <text x={left + 5} y="18" fill={c} fontSize="11">
                            {s.value ?? "?"}
                          </text>
                        )}
                    </g>
                  );
                })}
              </g>
            ))}
            {time >= start && time <= end && (
              <g>
                <line
                  x1={x(time)}
                  x2={x(time)}
                  y1="25"
                  y2={40 + signals.length * 58}
                  stroke="#fbbf24"
                  strokeWidth="1.5"
                />
                <path d={`M${x(time) - 5},24 h10 l-5,7 z`} fill="#fbbf24" />
              </g>
            )}
          </g>
        </svg>
      </div>
      {rows.some((r) => r.truncated) && (
        <p className="warning" role="status">
          每信号最多绘制 2000 segments；部分波形已省略，请 Zoom +
          缩小窗口。空白不代表没有事件。
        </p>
      )}
      <p className="muted small">
        图形仅绘制持续区间；同 tick 瞬时变化和窗口右端记录请查“真实事件 /
        当前值”，不能据平线排除瞬时变化。总线完整值可悬停查看。
      </p>
      {!signals.length && <p className="empty">从左侧选择信号以查看波形。</p>}
      <footer className="muted small">
        窗口 {start}–{end} ticks · Cursor {time} (
        {formatTime(time, trace.tick_fs)}) · 点击波形定位，输入整数精确跳转
      </footer>
    </section>
  );
}
