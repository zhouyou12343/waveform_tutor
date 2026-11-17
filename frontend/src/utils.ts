import type { Event, Format } from "./types";
export function upperBound(events: Event[], time: number) {
  let lo = 0,
    hi = events.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (events[mid].time <= time) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}
export function valueAt(events: Event[], time: number): string | null {
  return events[upperBound(events, time) - 1]?.value ?? null;
}
export function formatValue(value: string | null, format: Format) {
  if (value === null) return "—";
  if (format === "bin") return value;
  if (/[xz]/i.test(value)) return `${value} (bin)`;
  if (!/^[01]+$/.test(value)) return value;
  return format === "hex"
    ? `0x${BigInt("0b" + value)
        .toString(16)
        .toUpperCase()}`
    : BigInt("0b" + value).toString(10);
}
export function formatTime(tick: number, tickFs: number): string {
  const fs = BigInt(tick) * BigInt(tickFs);
  const units = [
    ["s", 15],
    ["ms", 12],
    ["us", 9],
    ["ns", 6],
    ["ps", 3],
    ["fs", 0],
  ] as const;
  const [unit, digits] =
    units.find(([, power]) => fs >= 10n ** BigInt(power)) ?? units[5];
  const scale = 10n ** BigInt(digits);
  const fraction = (fs % scale)
    .toString()
    .padStart(digits, "0")
    .replace(/0+$/, "");
  return `${fs / scale}${fraction ? "." + fraction : ""} ${unit}`;
}
export function parseTick(
  text: string,
  min: number,
  max: number,
): number | null {
  if (!/^\d+$/.test(text)) return null;
  const n = Number(text);
  return Number.isSafeInteger(n) && n >= min && n <= max ? n : null;
}
export function clipSegments(
  events: Event[],
  start: number,
  end: number,
  limit = 2000,
) {
  const segments: { start: number; end: number; value: string | null }[] = [];
  let i = upperBound(events, start);
  let time = start;
  let value = events[i - 1]?.value ?? null;
  while (i < events.length && events[i].time < end) {
    const next =
      events[i + 1]?.time === events[i].time
        ? upperBound(events, events[i].time)
        : i + 1;
    const e = events[next - 1];
    i = next;
    if (e.value === value) continue;
    if (e.time > time) {
      if (segments.length >= limit) return { segments, truncated: true };
      segments.push({ start: time, end: e.time, value });
    }
    time = e.time;
    value = e.value;
  }
  if (time < end) {
    if (segments.length >= limit) return { segments, truncated: true };
    segments.push({ start: time, end, value });
  }
  return { segments, truncated: false };
}
export function boundedWindow(
  start: number,
  end: number,
  min: number,
  max: number,
): [number, number] {
  if (max === min) return [min, max];
  const span = Math.min(Math.max(1, Math.round(end - start)), max - min);
  const left = Math.max(min, Math.min(Math.round(start), max - span));
  return [left, Math.min(max, left + span)];
}
export function zoomWindow(
  start: number,
  end: number,
  center: number,
  factor: number,
  min: number,
  max: number,
): [number, number] {
  const size = Math.min(
    max - min,
    Math.max(1, Math.round((end - start) * factor)),
  );
  const anchor = Math.min(end, Math.max(start, center));
  const left = Math.max(
    min,
    Math.min(anchor - Math.floor(size / 2), max - size),
  );
  return [left, left + size];
}
export function panWindow(
  start: number,
  end: number,
  direction: -1 | 1,
  min: number,
  max: number,
): [number, number] {
  const step = Math.max(1, Math.round((end - start) / 2));
  const delta =
    direction === 1 ? Math.min(step, max - end) : -Math.min(step, start - min);
  return [start + delta, end + delta];
}
export function downloadReport(text: string, name: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/markdown;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
