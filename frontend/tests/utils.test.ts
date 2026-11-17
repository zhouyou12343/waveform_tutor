import { test } from "node:test";
import assert from "node:assert/strict";
import {
  boundedWindow,
  clipSegments,
  formatValue,
  formatTime,
  parseTick,
  valueAt,
  zoomWindow,
  panWindow,
} from "../src/utils.ts";
test("cursor uses the last event at a tick, including duplicate times", () => {
  const events = [
    { time: 2, value: "0" },
    { time: 4, value: "1" },
    { time: 4, value: "x" },
  ];
  assert.equal(valueAt(events, 1), null);
  assert.equal(valueAt(events, 4), "x");
  assert.equal(valueAt(events, 100), "x");
});
test("bus formats preserve unknown bits and support wide vectors", () => {
  assert.equal(formatValue("10xz", "hex"), "10xz (bin)");
  assert.equal(formatValue("zz", "dec"), "zz (bin)");
  assert.equal(formatValue("1111", "hex"), "0xF");
  assert.equal(formatValue("1".repeat(64), "dec"), "18446744073709551615");
  assert.equal(formatValue(null, "bin"), "—");
});
test("physical time formatting uses exact integer arithmetic", () => {
  assert.equal(formatTime(120000, 1000), "120 ns");
  assert.equal(formatTime(120001, 1000), "120.001 ns");
  assert.equal(formatTime(0, 1000), "0 fs");
  assert.equal(formatTime(Number.MAX_SAFE_INTEGER, 1), "9.007199254740991 s");
  assert.equal(
    formatTime(Number.MAX_SAFE_INTEGER, 100000000000000000),
    "900719925474099100 s",
  );
});
test("safe integer tick validation", () => {
  assert.equal(
    parseTick("9007199254740991", 0, Number.MAX_SAFE_INTEGER),
    Number.MAX_SAFE_INTEGER,
  );
  for (const s of ["1.2", "-1", "2e3", "9007199254740992", ""])
    assert.equal(parseTick(s, 0, Number.MAX_SAFE_INTEGER), null);
  assert.equal(parseTick("12", 0, 10), null);
});
test("segments are clipped to viewport and capped at 2000", () => {
  const events = Array.from({ length: 5000 }, (_, time) => ({
    time,
    value: String(time % 2),
  }));
  const result = clipSegments(events, 100, 4500);
  assert.equal(result.segments.length, 2000);
  assert.equal(result.truncated, true);
  assert.equal(result.segments[0].start, 100);
  const small = clipSegments(events, 100, 102);
  assert.equal(small.truncated, false);
  assert.deepEqual(small.segments, [
    { start: 100, end: 101, value: "0" },
    { start: 101, end: 102, value: "1" },
  ]);
});
test("empty and zero duration windows do not invent event values", () => {
  assert.deepEqual(clipSegments([], 0, 10).segments, [
    { start: 0, end: 10, value: null },
  ]);
  assert.deepEqual(clipSegments([], 1, 1).segments, []);
});
test("drawing coalesces redundant records without changing raw evidence", () => {
  const repeated = Array.from({ length: 10000 }, (_, time) => ({
    time,
    value: "1",
  }));
  assert.deepEqual(clipSegments(repeated, 0, 10000), {
    segments: [{ start: 0, end: 10000, value: "1" }],
    truncated: false,
  });
  const transient = [
    { time: 0, value: "0" },
    { time: 5, value: "1" },
    { time: 5, value: "0" },
    { time: 10, value: "1" },
  ];
  assert.deepEqual(clipSegments(transient, 0, 10).segments, [
    { start: 0, end: 10, value: "0" },
  ]);
  assert.equal(valueAt(transient, 10), "1");
  assert.equal(transient.length, 4);
});
test("one tick and maximum safe tick navigation stay exact", () => {
  assert.deepEqual(panWindow(10, 11, -1, 0, 100), [9, 10]);
  assert.deepEqual(panWindow(10, 11, 1, 0, 100), [11, 12]);
  const max = Number.MAX_SAFE_INTEGER;
  assert.deepEqual(zoomWindow(max - 4, max, max, 0.5, 0, max), [max - 2, max]);
  assert.deepEqual(zoomWindow(max - 2, max, max, 0.5, 0, max), [max - 1, max]);
  assert.deepEqual(panWindow(max - 1, max, -1, 0, max), [max - 2, max - 1]);
  assert.deepEqual(panWindow(max - 1, max, 1, 0, max), [max - 1, max]);
  assert.deepEqual(zoomWindow(0, 0, 0, 2, 0, 0), [0, 0]);
  assert.deepEqual(boundedWindow(0, 0, 0, 0), [0, 0]);
});
test("pan and zoom stay bounded", () => {
  assert.deepEqual(boundedWindow(-10, 10, 0, 100), [0, 20]);
  assert.deepEqual(boundedWindow(90, 110, 0, 100), [80, 100]);
  assert.deepEqual(boundedWindow(0, 200, 0, 100), [0, 100]);
});
