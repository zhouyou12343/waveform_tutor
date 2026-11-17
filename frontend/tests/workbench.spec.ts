import { test, expect, type Page } from "@playwright/test";
import type { AnalysisRequest, Trace } from "../src/types";
const trace: Trace = {
  id: "demo",
  name: "counter.vcd",
  timescale: "1 ps",
  tick_fs: 1000,
  start: 0,
  end: 100,
  signals: [
    {
      id: "clk",
      name: "top.clk",
      scope: "top",
      kind: "wire",
      width: 1,
      events: [
        { time: 0, value: "0" },
        { time: 10, value: "1" },
      ],
    },
    {
      id: "count",
      name: "top.count",
      scope: "top",
      kind: "wire",
      width: 4,
      events: [
        { time: 0, value: "xxxx" },
        { time: 10, value: "0001" },
      ],
    },
  ],
  sources: [
    {
      name: "counter.sv",
      content: "module counter;\nlogic clk;\nlogic [3:0] count;\nendmodule",
    },
  ],
  warnings: [],
};
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/health"))
      return route.fulfill({ json: { ai_configured: false, requests: 0 } });
    if (path.includes("/demos/")) return route.fulfill({ json: trace });
    if (path.endsWith("/analysis")) {
      const body = route.request().postDataJSON() as AnalysisRequest;
      return route.fulfill({
        json: {
          time: body.time,
          timescale: "1 ps",
          window: { start: 0, end: 100 },
          signals: trace.signals
            .filter((s) => body.signals.includes(s.id))
            .map((s) => ({
              ...s,
              value: body.time < 10 ? s.events[0].value : s.events[1].value,
              previous: null,
              next: null,
              truncated: false,
            })),
          clock: null,
          reset: null,
          observed_facts: [`Observed at ${body.time}`],
          limitations: ["Name matches are heuristic."],
          related_code: [],
        },
      });
    }
    if (path.endsWith("/report"))
      return route.fulfill({
        body: "# Offline waveform report",
        contentType: "text/markdown",
      });
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });
});
test("AI requires consent, separates output and survives cancellation", async ({
  page,
}) => {
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { ai_configured: true, requests: 0 } }),
  );
  await page.route("**/explain", (route) => {
    const body = route.request().postDataJSON();
    expect(body.consent).toBe(true);
    expect(body.include_rtl).toBe(false);
    return route.fulfill({
      json: {
        summary: "推测：使能可能关闭",
        observed_facts: ["Observed at 0"],
        possible_explanations: ["推测：检查使能"],
        related_signals: ["top.count"],
        related_code: [],
        suggested_checks: ["核对 RTL 条件"],
        limitations: ["不是形式验证"],
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /01 \/ DEMO Counter/ }).click();
  await expect(page.getByText("Observed at 0", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "生成解释" })).toBeDisabled();
  await page.getByLabel(/我确认将选中信号/).check();
  await page.getByRole("button", { name: "生成解释" }).click();
  await expect(page.locator(".explanation-result")).toContainText(
    "推测：使能可能关闭",
  );
  await expect(page.locator(".explanation-result")).toContainText(
    "核对 RTL 条件",
  );
  await page.route("**/explain", (route) =>
    route.fulfill({ status: 503, json: { detail: "AI 服务暂时不可用" } }),
  );
  await page.getByRole("button", { name: "生成解释" }).click();
  await expect(page.getByRole("alert")).toContainText("AI 服务暂时不可用");
  await expect(
    page.getByRole("heading", { name: "Timing Diagram" }),
  ).toBeVisible();
  let release: (() => void) | undefined;
  await page.route("**/explain", async (route) => {
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    await route.abort().catch(() => {});
  });
  const sent = page.waitForRequest("**/explain");
  await page.getByRole("button", { name: "生成解释" }).click();
  await sent;
  await page.getByRole("button", { name: "取消请求" }).click();
  release?.();
  await expect(page.getByRole("alert")).toContainText("请求已取消");
  await page.getByLabel("整数 tick").fill("20");
  await page.getByRole("button", { name: "跳转" }).click();
  await expect(page.getByText("Observed at 20", { exact: true })).toBeVisible();
});

test("offline demo provides waveforms, integer cursor, RTL and report", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Understand Digital Waveforms",
  );
  await page.getByRole("button", { name: /01 \/ DEMO Counter/ }).click();
  await expect(
    page.getByRole("heading", { name: "Timing Diagram" }),
  ).toBeVisible();
  await expect(page.getByText("Observed at 0", { exact: true })).toBeVisible();
  await page.getByLabel("整数 tick").fill("10");
  await page.getByRole("button", { name: "跳转" }).click();
  await expect(page.getByText("Observed at 10", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "生成解释" })).toBeDisabled();
  await expect(page.getByLabel("RTL 文件")).toHaveValue("counter.sv");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /下载 Markdown/ }).click();
  expect((await download).suggestedFilename()).toBe("waveform-10.md");
});
test("zero selected signals sends no new analysis and unknown bus stays visible", async ({
  page,
}) => {
  let count = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/analysis")) count++;
  });
  await page.goto("/");
  await page.getByRole("button", { name: /01 \/ DEMO Counter/ }).click();
  await expect(page.locator(".wave-labels")).toContainText("xxxx (bin)");
  await expect(page.getByText("Observed at 0", { exact: true })).toBeVisible();
  await page.locator(".signal-option input").first().uncheck();
  await page.locator(".signal-option input").last().uncheck();
  await expect(page.getByText("请选择信号；未发送分析请求。")).toBeVisible();
  const before = count;
  await page.getByLabel("整数 tick").fill("20");
  await page.getByRole("button", { name: "跳转" }).click();
  await expect(page.getByText("请选择信号；未发送分析请求。")).toBeVisible();
  expect(count).toBe(before);
});

// Route mocks test browser state only; none of these are real Provider calls.
const answer = (summary: string) => ({
  summary,
  observed_facts: ["Observed at 0"],
  possible_explanations: [],
  related_signals: ["top.count"],
  related_code: [],
  suggested_checks: [],
  limitations: ["Mock only"],
});
async function openAI(page: Page) {
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { ai_configured: true, requests: 0 } }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: /01 \/ DEMO Counter/ }).click();
  await expect(page.getByText("Observed at 0", { exact: true })).toBeVisible();
  await page.getByLabel(/我确认将选中信号/).check();
}

test("Mock: duplicate clicks reserve one request and late old answer cannot replace new answer", async ({
  page,
}) => {
  let calls = 0;
  let releaseOld: (() => void) | undefined;
  let oldFinished: (() => void) | undefined;
  const oldDone = new Promise<void>((resolve) => {
    oldFinished = resolve;
  });
  await page.route("**/explain", async (route) => {
    calls++;
    if (calls === 1) {
      await new Promise<void>((resolve) => {
        releaseOld = resolve;
      });
      await route.fulfill({ json: answer("OLD ANSWER") }).catch(() => {});
      oldFinished?.();
    } else await route.fulfill({ json: answer("NEW ANSWER") });
  });
  await openAI(page);
  const sent = page.waitForRequest("**/explain");
  await page.getByRole("button", { name: "生成解释" }).evaluate((element) => {
    (element as HTMLButtonElement).click();
    (element as HTMLButtonElement).click();
  });
  await sent;
  expect(calls).toBe(1);
  await expect(page.getByText("正在请求解释…")).toBeVisible();
  await expect(page.getByRole("button", { name: "生成解释" })).toBeDisabled();
  await page.getByLabel("向 AI 提问").fill("新的问题，仍使用公开测试数据");
  await page.getByRole("button", { name: "生成解释" }).click();
  await expect(page.locator(".explanation-result")).toContainText("NEW ANSWER");
  releaseOld?.();
  await oldDone;
  await expect(page.locator(".explanation-result")).not.toContainText(
    "OLD ANSWER",
  );
  await expect(page.locator(".explanation-result")).toContainText("NEW ANSWER");
  expect(calls).toBe(2);
});

for (const change of [
  "question",
  "consent",
  "rtl",
  "cursor",
  "signals",
  "clock",
  "demo",
  "upload",
  "source",
] as const) {
  test(`Mock: ${change} invalidates an in-flight answer`, async ({ page }) => {
    let release: (() => void) | undefined;
    let finished: (() => void) | undefined;
    const done = new Promise<void>((resolve) => {
      finished = resolve;
    });
    await page.route("**/explain", async (route) => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      await route
        .fulfill({ json: answer("STALE CONTEXT ANSWER") })
        .catch(() => {});
      finished?.();
    });
    await openAI(page);
    await page.getByLabel(/独立授权/).check();
    const sent = page.waitForRequest("**/explain");
    await page.getByRole("button", { name: "生成解释" }).click();
    await sent;
    if (change === "question")
      await page.getByLabel("向 AI 提问").fill("改后的问题");
    if (change === "consent")
      await page.getByLabel(/我确认将选中信号/).uncheck();
    if (change === "rtl") await page.getByLabel(/独立授权/).uncheck();
    if (change === "cursor") {
      await page.getByLabel("整数 tick").fill("20");
      await page.getByRole("button", { name: "跳转" }).click();
    }
    if (change === "signals")
      await page.locator(".signal-option input").first().uncheck();
    if (change === "clock")
      await page.getByLabel("Clock", { exact: true }).selectOption("clk");
    if (change === "demo") {
      await page.route("**/api/demos/fifo", (route) =>
        route.fulfill({
          json: { ...trace, id: "next-demo", name: "fifo.vcd" },
        }),
      );
      await page.getByRole("button", { name: /02 \/ DEMO FIFO/ }).click();
      await expect(page.locator(".trace-bar")).toContainText("fifo.vcd");
    }
    if (change === "upload") {
      await page.route("**/api/traces", (route) =>
        route.fulfill({
          json: { ...trace, id: "upload", name: "uploaded.vcd" },
        }),
      );
      await page.getByLabel("上传 VCD", { exact: true }).setInputFiles({
        name: "uploaded.vcd",
        mimeType: "text/plain",
        buffer: Buffer.from("mock fixture"),
      });
      await expect(page.locator(".trace-bar")).toContainText("uploaded.vcd");
    }
    if (change === "source") {
      await page.route("**/sources", (route) =>
        route.fulfill({ json: { name: "extra.sv", content: "// count" } }),
      );
      const sourceResponse = page.waitForResponse("**/sources");
      await page.getByLabel("上传 RTL").setInputFiles({
        name: "extra.sv",
        mimeType: "text/plain",
        buffer: Buffer.from("// count"),
      });
      await sourceResponse;
      await expect(page.getByLabel("RTL 文件").locator("option")).toHaveCount(
        2,
      );
    }
    await expect(page.getByText("正在请求解释…")).toHaveCount(0);
    release?.();
    await done;
    await expect(page.locator(".explanation-result")).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "Timing Diagram" }),
    ).toBeVisible();
    if (change === "demo" || change === "upload" || change === "consent") {
      await expect(page.getByLabel(/我确认将选中信号/)).not.toBeChecked();
      await expect(
        page.getByRole("button", { name: "生成解释" }),
      ).toBeDisabled();
    }
  });
}

test("Mock: timeout and retry preserve offline facts and disclose actual analysis window", async ({
  page,
}, testInfo) => {
  await page.route("**/explain", (route) =>
    route.fulfill({ status: 504, json: { detail: "AI 服务请求超时" } }),
  );
  await openAI(page);
  await expect(page.locator(".ai-panel")).toContainText(
    "实际分析窗口：0–100 ticks",
  );
  await expect(page.locator(".ai-panel")).toContainText(
    "相邻记录可能位于窗口外",
  );
  await page.getByRole("button", { name: "生成解释" }).click();
  await expect(page.getByRole("alert")).toContainText("AI 服务请求超时");
  await expect(page.getByText("Observed at 0", { exact: true })).toBeVisible();
  await page.route("**/explain", (route) =>
    route.fulfill({ json: answer("RECOVERED MOCK ANSWER") }),
  );
  await page.getByRole("button", { name: "生成解释" }).click();
  await expect(page.locator(".explanation-result")).toContainText(
    "RECOVERED MOCK ANSWER",
  );
  await page.screenshot({
    path: testInfo.outputPath("ai-mock-recovery.png"),
    fullPage: true,
  });
});
