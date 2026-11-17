import { useState } from "react";
import type { Signal } from "./types";
export function Explorer({
  signals,
  selected,
  onChange,
}: {
  signals: Signal[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const [search, setSearch] = useState("");
  const scopes = new Map<string, Signal[]>();
  for (const s of signals.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()),
  )) {
    const scope = s.scope || "(root)";
    scopes.set(scope, [...(scopes.get(scope) ?? []), s]);
  }
  return (
    <aside className="panel explorer">
      <div className="panel-heading">
        <h2>Signal Explorer</h2>
        <span>{selected.length}/16</span>
      </div>
      <input
        aria-label="搜索信号"
        placeholder="搜索 hierarchy / signal…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <p className="muted small">最多选择 16 个信号 · 按层级分组</p>
      <div className="signal-tree">
        {[...scopes].map(([scope, items]) => (
          <details key={scope} open>
            <summary>{scope}</summary>
            {items.map((s) => (
              <label className="signal-option" key={s.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(s.id)}
                  disabled={!selected.includes(s.id) && selected.length >= 16}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...selected, s.id]
                        : selected.filter((id) => id !== s.id),
                    )
                  }
                />
                <span title={s.name}>{s.name.split(".").at(-1)}</span>
                <small>{s.width > 1 ? `${s.width} bits` : s.kind}</small>
              </label>
            ))}
          </details>
        ))}
        {!scopes.size && <p className="muted">没有匹配的信号</p>}
      </div>
    </aside>
  );
}
