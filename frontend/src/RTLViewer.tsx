import { useEffect, useMemo, useState } from "react";
import type { Signal, Source } from "./types";

const PAGE_SIZE = 200;
const NAME_BOUNDARY = "[A-Za-z0-9_$]";

function splitLines(content: string) {
  if (!content) return [];
  // Match Python str.splitlines(), including its trailing-newline behavior.
  const lines = content.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u{2028}\u{2029}]/u);
  if (/[\n\r\v\f\x1c-\x1e\x85\u{2028}\u{2029}]$/u.test(content)) lines.pop();
  return lines;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function syntax(line: string) {
  return line
    .split(
      /(\/\/.*$|\b(?:module|endmodule|input|output|wire|reg|logic|always|always_ff|begin|end|if|else|assign|posedge|negedge|parameter)\b|\b\d+(?:'[bhd][0-9a-fxz]+)?\b)/gi,
    )
    .map((part, i) => (
      <span
        key={i}
        className={
          part.startsWith("//")
            ? "syntax-comment"
            : /^(module|endmodule|input|output|wire|reg|logic|always|always_ff|begin|end|if|else|assign|posedge|negedge|parameter)$/.test(
                  part,
                )
              ? "syntax-keyword"
              : /^\d/.test(part)
                ? "syntax-number"
                : ""
        }
      >
        {part}
      </span>
    ));
}
export function RTLViewer({
  sources,
  signals,
  onUpload,
  busy,
}: {
  sources: Source[];
  signals: Signal[];
  onUpload: (file: File) => void;
  busy: boolean;
}) {
  const [file, setFile] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const source = sources.find((s) => s.name === file) ?? sources[0];
  const lines = useMemo(
    () => (source ? splitLines(source.content) : []),
    [source],
  );
  const relatedPatterns = useMemo(
    () =>
      signals
        .map((s) =>
          s.name
            .split(".")
            .at(-1)!
            .replace(/\[[^\]]*\]$/, ""),
        )
        .filter(Boolean)
        .map(
          (name) =>
            new RegExp(
              `(?<!${NAME_BOUNDARY})${escapeRegExp(name)}(?!${NAME_BOUNDARY})`,
            ),
        ),
    [signals],
  );
  const searchMatches = useMemo(() => {
    const normalizedQuery = query.toLowerCase();
    return lines
      .map((line, index) => ({ line, lineNumber: index + 1 }))
      .filter(
        ({ line }) =>
          !normalizedQuery || line.toLowerCase().includes(normalizedQuery),
      );
  }, [lines, query]);
  const pageCount = Math.max(1, Math.ceil(searchMatches.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleLines = searchMatches.slice(
    currentPage * PAGE_SIZE,
    (currentPage + 1) * PAGE_SIZE,
  );

  useEffect(() => {
    setPage(0);
  }, [source, query]);

  return (
    <section className="panel rtl">
      <div className="panel-heading">
        <h2>RTL Source</h2>
        <label className="button">
          上传 RTL
          <input
            hidden
            type="file"
            accept=".v,.sv"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload(f);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <div className="toolbar">
        <select
          aria-label="RTL 文件"
          value={source?.name ?? ""}
          onChange={(e) => setFile(e.target.value)}
        >
          {sources.map((s) => (
            <option key={s.name}>{s.name}</option>
          ))}
        </select>
        <input
          aria-label="搜索 RTL"
          placeholder="搜索代码…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <p className="muted small">
        Possible
        Association：相关行仅使用信号名称匹配（启发式），名字相同不代表因果关系。
      </p>
      {source ? (
        <>
          <div className="code-scroll">
            <pre>
              {visibleLines.map(({ line, lineNumber }) => {
                const related = relatedPatterns.some((pattern) =>
                  pattern.test(line),
                );
                return (
                  <div
                    key={lineNumber}
                    className={`code-line ${related ? "related" : ""} ${query ? "search-match" : ""}`}
                  >
                    <span className="line-number">{lineNumber}</span>
                    <code>{syntax(line) || " "}</code>
                  </div>
                );
              })}
            </pre>
          </div>
          <div className="toolbar">
            <button
              type="button"
              disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}
            >
              上一页
            </button>
            <span className="muted small">
              {searchMatches.length === 0
                ? "0 行"
                : `${currentPage * PAGE_SIZE + 1}-${Math.min((currentPage + 1) * PAGE_SIZE, searchMatches.length)} / ${searchMatches.length} 行`}
            </span>
            <button
              type="button"
              disabled={currentPage >= pageCount - 1}
              onClick={() => setPage(currentPage + 1)}
            >
              下一页
            </button>
          </div>
        </>
      ) : (
        <p className="empty">上传 Verilog / SystemVerilog，或打开内置案例。</p>
      )}
    </section>
  );
}
