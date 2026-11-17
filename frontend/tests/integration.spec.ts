import { test, expect } from "@playwright/test";
import path from "node:path";

test.describe.configure({ mode: "serial" });

test("real Counter: cursor, clock, search, zoom, RTL and report", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("Offline analysis · no AI key")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("home.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: /01 \/ DEMO Counter/ }).click();
  await expect(
    page.getByRole("heading", { name: "Timing Diagram" }),
  ).toBeVisible();
  await page.getByLabel("整数 tick").fill("120000");
  await page.getByRole("button", { name: "跳转" }).click();
  await page
    .getByLabel("Clock", { exact: true })
    .selectOption({ label: "tb.clk" });
  await expect(page.locator(".facts")).toContainText("tb.count[3:0] = 1010");
  await expect(page.locator(".facts")).toContainText("tb.enable = 0");
  await expect(page.locator(".insights")).toContainText(
    "前一边沿 115000 / 后一边沿 125000",
  );
  await expect(page.locator(".wave-labels")).toContainText("0xA");
  await page.getByLabel("总线显示格式").selectOption("dec");
  await expect(
    page.locator(".wave-labels").getByText("10", { exact: true }),
  ).not.toHaveCount(0);
  await page.getByLabel("搜索信号").fill("count");
  await expect(page.locator(".signal-option")).toHaveCount(2);
  await page.locator(".signal-option input").last().check();
  await page.getByLabel("搜索信号").fill("");
  await page.getByLabel("放大", { exact: true }).click();
  await page.getByLabel("向后平移").click();
  await page.getByRole("button", { name: "Fit", exact: true }).click();
  const wave = page.getByRole("img", { name: /交互式数字波形/ });
  const box = await wave.boundingBox();
  if (!box) throw new Error("waveform not rendered");
  await wave.evaluate((element) =>
    element.addEventListener(
      "click",
      (event) => {
        element.setAttribute(
          "data-click-x",
          String((event as MouseEvent).clientX),
        );
      },
      { once: true },
    ),
  );
  await wave.click({ position: { x: box.width / 2, y: 70 } });
  const clickX = Number(await wave.getAttribute("data-click-x"));
  const expectedTick = Math.round(((clickX - box.x) / box.width) * 237000);
  await expect(page.getByLabel("整数 tick")).toHaveValue(String(expectedTick));
  await page.getByLabel("整数 tick").fill("120000");
  await page.getByRole("button", { name: "跳转" }).click();
  await expect(page.getByLabel("RTL 文件")).toHaveValue("design.sv");
  await expect(page.getByRole("button", { name: "生成解释" })).toBeDisabled();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /下载 Markdown/ }).click();
  expect((await download).suggestedFilename()).toBe("waveform-120000.md");
  await expect(page.locator(".facts")).toContainText("tb.count[3:0] = 1010");
  await page.screenshot({
    path: testInfo.outputPath("counter.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("real uploads: invalid VCD recovers, X/Z and no selection remain honest", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("上传 VCD", { exact: true }).setInputFiles({
    name: "bad.vcd",
    mimeType: "text/plain",
    buffer: Buffer.from("not a vcd"),
  });
  await expect(page.getByRole("alert")).toContainText("VCD");
  const content =
    "$timescale 10 ns $end\n$scope module tb $end\n$var wire 1 ! flag $end\n$var reg 4 # data $end\n$upscope $end\n$enddefinitions $end\n#0\nx!\nb10xz #\n#5\nz!\nbz #\n#10\n1!\nb11 #\n#15\n";
  await page.getByLabel("上传 VCD", { exact: true }).setInputFiles({
    name: "unknown.vcd",
    mimeType: "text/plain",
    buffer: Buffer.from(content),
  });
  await expect(page.locator(".wave-labels")).toContainText("10xz (bin)");
  await page.getByLabel("整数 tick").fill("5");
  await page.getByRole("button", { name: "跳转" }).click();
  await expect(page.locator(".wave-labels")).toContainText("zzzz (bin)");
  await page.getByLabel("整数 tick").fill("16");
  await page.getByRole("button", { name: "跳转" }).click();
  await expect(page.getByRole("alert")).toContainText("安全整数");
  await page.locator(".signal-option input").first().uncheck();
  await page.locator(".signal-option input").last().uncheck();
  await expect(page.getByText("请选择信号；未发送分析请求。")).toBeVisible();
});

test("real FIFO and handshake demos load, uploaded RTL stays local", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /02 \/ DEMO FIFO/ }).click();
  await expect(page.locator(".trace-bar")).toContainText("fifo.vcd");
  await expect(page.locator(".facts")).toContainText("tb.");
  await page.getByRole("button", { name: /03 \/ DEMO Handshake/ }).click();
  await expect(page.locator(".trace-bar")).toContainText("handshake.vcd");
  await page.getByLabel("整数 tick").fill("75000");
  await page.getByRole("button", { name: "跳转" }).click();
  await expect(page.locator(".facts")).toContainText("tb.data[7:0] = 10100010");
  await page.getByLabel("上传 RTL").setInputFiles({
    name: "extra.sv",
    mimeType: "text/plain",
    buffer: Buffer.from("module extra;\n wire valid;\nendmodule\n"),
  });
  await page.getByLabel("RTL 文件").selectOption("extra.sv");
  await expect(page.locator(".code-scroll")).toContainText("module extra");
});

test("real VCD file upload works at a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 760, height: 900 });
  await page.goto("/");
  await page
    .getByLabel("上传 VCD", { exact: true })
    .setInputFiles(path.resolve("../examples/counter/trace.vcd"));
  await expect(
    page.getByRole("heading", { name: "Timing Diagram" }),
  ).toBeVisible();
  await expect(page.locator(".facts")).toContainText("tb.count");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
