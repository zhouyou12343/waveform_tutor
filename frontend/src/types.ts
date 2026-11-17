export type Event = { time: number; value: string };
export type Signal = {
  id: string;
  name: string;
  scope: string;
  width: number;
  kind: string;
  events: Event[];
};
export type Source = { name: string; content: string };
export type Trace = {
  id: string;
  name: string;
  timescale: string;
  tick_fs: number;
  start: number;
  end: number;
  signals: Signal[];
  sources: Source[];
  warnings: string[];
};
export type AnalysisRequest = {
  time: number;
  signals: string[];
  window: number;
  clock?: string | null;
  edge: "rising" | "falling";
  reset?: string | null;
  reset_active: "0" | "1";
  reset_mode: "unknown" | "synchronous" | "asynchronous";
};
export type Analysis = {
  time: number;
  timescale: string;
  window: { start: number; end: number };
  signals: {
    id: string;
    name: string;
    width: number;
    value: string | null;
    previous: Event | null;
    next: Event | null;
    events: Event[];
    truncated: boolean;
  }[];
  clock: {
    name: string;
    edge: string;
    previous: number | null;
    next: number | null;
    at_time: boolean;
  } | null;
  reset: {
    name: string;
    value: string | null;
    active: boolean | null;
    mode: string;
  } | null;
  observed_facts: string[];
  limitations: string[];
  related_code: {
    file: string;
    line: number;
    text: string;
    signal: string;
    match: "name-only";
  }[];
};
export type Explanation = {
  summary: string;
  observed_facts: string[];
  possible_explanations: string[];
  related_signals: string[];
  related_code: string[];
  suggested_checks: string[];
  limitations: string[];
};
export type ModelConfiguration = {
  configured: boolean;
  base_url: string;
  model: string;
  api_format: "chat_completions" | "responses";
  has_key: boolean;
  source: "local" | "environment" | "none" | "disabled" | "runtime";
  saved_locally: boolean;
  revision: string;
  error: string;
  message?: string;
};
export type ModelConfigurationInput = {
  url: string;
  api_key: string;
  model: string;
  api_format: ModelConfiguration["api_format"];
};
export type Format = "bin" | "hex" | "dec";
