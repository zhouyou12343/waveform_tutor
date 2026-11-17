import type {
  Analysis,
  AnalysisRequest,
  Explanation,
  ModelConfiguration,
  ModelConfigurationInput,
  Source,
  Trace,
} from "./types";
async function request<T>(
  path: string,
  init: RequestInit = {},
  text = false,
): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const error = await response.json();
      if (typeof error.detail === "string") message = error.detail;
      else if (Array.isArray(error.detail)) {
        message =
          error.detail
            .filter((item: { msg?: unknown }) => typeof item.msg === "string")
            .slice(0, 5)
            .map(
              (item: { loc?: unknown[]; msg: string }) =>
                `${Array.isArray(item.loc) ? item.loc.join(".") : "输入"}: ${item.msg}`,
            )
            .join("; ") || message;
      }
    } catch {
      /* Keep HTTP status for non-JSON errors. */
    }
    throw new Error(message);
  }
  return (text ? await response.text() : await response.json()) as T;
}
const post = (body: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
  signal,
});
const upload = (file: File, signal?: AbortSignal): RequestInit => {
  const body = new FormData();
  body.append("file", file);
  return { method: "POST", body, signal };
};
export const api = {
  modelConfiguration: (signal?: AbortSignal) =>
    request<ModelConfiguration>("/ai/config", { signal, cache: "no-store" }),
  saveModelConfiguration: (body: ModelConfigurationInput, signal?: AbortSignal) =>
    request<ModelConfiguration>("/ai/config", { ...post(body, signal), method: "PUT" }),
  clearModelConfiguration: (signal?: AbortSignal) =>
    request<ModelConfiguration>("/ai/config", { method: "DELETE", signal }),
  health: (signal?: AbortSignal) =>
    request<{ ai_configured: boolean; requests: number; ai_config_revision?: string }>("/health", {
      signal,
    }),
  demo: (name: string, signal?: AbortSignal) =>
    request<Trace>(`/demos/${name}`, { method: "POST", signal }),
  trace: (file: File, signal?: AbortSignal) =>
    request<Trace>("/traces", upload(file, signal)),
  source: (id: string, file: File, signal?: AbortSignal) =>
    request<Source>(
      `/traces/${encodeURIComponent(id)}/sources`,
      upload(file, signal),
    ),
  analysis: (id: string, body: AnalysisRequest, signal?: AbortSignal) =>
    request<Analysis>(
      `/traces/${encodeURIComponent(id)}/analysis`,
      post(body, signal),
    ),
  explain: (
    id: string,
    body: AnalysisRequest & {
      question: string;
      consent: boolean;
      include_rtl: boolean;
    },
    signal?: AbortSignal,
  ) =>
    request<Explanation>(
      `/traces/${encodeURIComponent(id)}/explain`,
      post(body, signal),
    ),
  report: (id: string, body: AnalysisRequest, signal?: AbortSignal) =>
    request<string>(
      `/traces/${encodeURIComponent(id)}/report`,
      post(body, signal),
      true,
    ),
};
