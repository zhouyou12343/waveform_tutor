import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "./api";
import type { ModelConfiguration } from "./types";
import "./ModelSettings.css";

export function ModelSettings({
  onChange,
}: {
  onChange: (value: ModelConfiguration) => void;
}) {
  const [config, setConfig] = useState<ModelConfiguration | null>(null);
  const [url, setUrl] = useState("");
  const [key, setKey] = useState("");
  const [model, setModel] = useState("gpt-5.6-sol");
  const [format, setFormat] =
    useState<ModelConfiguration["api_format"]>("responses");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  const callback = useRef(onChange);
  callback.current = onChange;

  function apply(value: ModelConfiguration) {
    setConfig(value);
    setUrl(value.base_url);
    setModel(value.model);
    setFormat(value.api_format);
    setKey("");
    callback.current(value);
  }

  useEffect(() => {
    const controller = new AbortController();
    api
      .modelConfiguration(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        apply(value);
        setError(value.error);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "无法读取配置。请确认后端已启动；若后端仍是旧版本，请重启。离线功能不受此配置表单影响。",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
      active.current?.abort();
    };
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (active.current || loading || !url.trim() || !key.trim()) return;
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const value = await api.saveModelConfiguration(
        {
          url: url.trim(),
          api_key: key.trim(),
          model: model.trim(),
          api_format: format,
        },
        controller.signal,
      );
      if (!controller.signal.aborted) {
        apply(value);
        setMessage(value.message ?? "配置已保存，可上传 VCD 并生成解释。");
      }
    } catch (reason) {
      if (!controller.signal.aborted)
        setError(
          reason instanceof Error ? reason.message : "保存失败，请重试。",
        );
    } finally {
      setKey("");
      if (!controller.signal.aborted) setBusy(false);
      if (active.current === controller) active.current = null;
    }
  }

  async function clear() {
    if (
      active.current ||
      !window.confirm(
        "清除网页保存的 API Key 并关闭 AI？波形和离线分析会保留。",
      )
    )
      return;
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const value = await api.clearModelConfiguration(controller.signal);
      if (!controller.signal.aborted) {
        apply(value);
        setMessage(value.message ?? "配置已清除，已切换为离线模式。");
      }
    } catch (reason) {
      if (!controller.signal.aborted)
        setError(
          reason instanceof Error ? reason.message : "清除失败，请重试。",
        );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      if (active.current === controller) active.current = null;
    }
  }

  return (
    <section
      className="panel model-settings"
      aria-labelledby="model-settings-heading"
    >
      <div className="panel-heading">
        <h2 id="model-settings-heading">模型配置</h2>
        <span className="badge">
          {loading
            ? "读取中"
            : config?.configured
              ? "已配置 · 按需调用"
              : "离线模式"}
        </span>
      </div>
      <form className="model-settings-body" onSubmit={save}>
        <p className="muted">
          先保存你的模型服务，再上传 VCD、选中信号并生成解释。无需 AI
          也能查看波形和确定性事实。
        </p>
        <fieldset disabled={busy || loading} className="model-settings-fields">
          <label>
            模型 API 地址（必填）
            <input
              type="url"
              required
              maxLength={2048}
              aria-label="模型 API 地址"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://your-provider.example/v1"
            />
            <span className="muted small">
              可填 Base URL 或完整 /responses、/chat/completions 地址；远程必须
              HTTPS。
            </span>
          </label>
          <label>
            API Key（必填）
            <input
              type="password"
              required
              maxLength={4096}
              aria-label="模型 API Key"
              value={key}
              onChange={(event) => setKey(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder={
                config?.has_key
                  ? "已保存；修改配置时请重新输入，不回显旧密钥"
                  : "输入你自己的 API Key"
              }
            />
            <span className="muted small">
              提交后清空输入；不会保存到浏览器存储，也不自动读取其他客户端密钥。
            </span>
          </label>
          <label>
            模型 ID
            <input
              maxLength={200}
              aria-label="模型 ID"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="gpt-5.6-sol"
            />
            <span className="muted small">
              使用服务商的真实 model ID。留空采用
              gpt-5.6-sol；换服务商通常需要修改。
            </span>
          </label>
          <label>
            接口类型
            <select
              aria-label="模型接口类型"
              value={format}
              onChange={(event) =>
                setFormat(
                  event.target.value as ModelConfiguration["api_format"],
                )
              }
            >
              <option value="responses">OpenAI-compatible Responses</option>
              <option value="chat_completions">
                OpenAI-compatible Chat Completions
              </option>
            </select>
            <span className="muted small">
              完整端点URL优先决定类型；当前仅支持非流式文本响应。
            </span>
          </label>
        </fieldset>
        <div className="toolbar">
          <button className="primary" type="submit" disabled={busy || loading}>
            {busy ? "正在保存或清除…" : "保存模型配置"}
          </button>
          <button
            type="button"
            disabled={busy || loading || !config?.configured}
            onClick={clear}
          >
            清除配置并关闭 AI
          </button>
        </div>
        {message && (
          <p className="model-settings-success" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <p className="muted small">
          配置只保存在本机后端的 .waveform-tutor/ai-config.json（明文、Git
          已忽略），不提供多用户隔离。保存不调用模型、不验证余额或密钥有效性；生成解释才会发送已授权上下文并可能计费。不要将此无登录后端直接暴露公网。
        </p>
        {config?.source === "environment" && (
          <p className="muted small">
            当前使用启动后端时的环境配置；网页保存后优先使用网页配置。
          </p>
        )}
      </form>
    </section>
  );
}
