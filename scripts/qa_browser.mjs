import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { writeFile, mkdir, readFile } from 'node:fs/promises';

const phase = process.argv[2] ?? 'baseline';
if (!/^[a-zA-Z0-9_-]+$/.test(phase)) throw new Error('Invalid phase');
const output = `docs/qa/evidence/browser-${phase}.json`;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const observations = [], errors = [], failedRequests = [], badResponses = [];
page.on('pageerror', error => errors.push(error.message));
page.on('requestfailed', request => {
  if (!request.failure()?.errorText.includes('ABORTED')) failedRequests.push({ url: new URL(request.url()).pathname, error: request.failure()?.errorText });
});
page.on('response', response => {
  if (response.status() >= 400) badResponses.push({ path: new URL(response.url()).pathname, status: response.status() });
});
const check = (condition, message) => { if (!condition) throw new Error(message); };
async function step(name, action) {
  const start = performance.now();
  try { const evidence = await action(); observations.push({ name, status: 'PASS', milliseconds: Math.round(performance.now() - start), evidence }); }
  catch (error) { const screenshot = `docs/screenshots/qa-${phase}-failure-${observations.length}.png`; await page.screenshot({ path: screenshot, fullPage: true }); observations.push({ name, status: 'FAIL', error: error.message, screenshot }); }
}
async function cursor(tick, expected) {
  await page.getByLabel('整数 tick').fill(String(tick));
  const response = page.waitForResponse(r => r.url().endsWith('/analysis') && r.request().postDataJSON()?.time === tick);
  await page.getByRole('button', { name: '跳转' }).click();
  const data = await (await response).json();
  for (const [name, value] of Object.entries(expected)) {
    check(data.signals.some(s => s.name === name && s.value === value), `${name}@${tick} expected ${value}`);
    await page.locator('.facts').getByText(`${name} = ${value}。`, { exact: false }).first().waitFor();
  }
  return { tick, values: data.signals.map(s => ({ name: s.name, value: s.value })), clock: data.clock };
}
await mkdir('docs/qa/evidence', { recursive: true });
await step('Home loads without an AI key', async () => {
  await page.goto('http://127.0.0.1:5173');
  await page.getByText('Offline analysis · no AI key', { exact: true }).waitFor();
  await page.screenshot({ path: 'docs/screenshots/qa-home.png', fullPage: true });
  return { heading: await page.locator('h1').innerText() };
});
await step('Counter hierarchy, real values and report content', async () => {
  const response = page.waitForResponse('**/api/demos/counter');
  await page.getByRole('button', { name: /01 \/ DEMO Counter/ }).click();
  const trace = await (await response).json();
  check(trace.timescale === '1 ps' && trace.signals.some(s => s.scope === 'tb.dut'), 'incorrect hierarchy/timescale');
  await page.locator('.facts').waitFor();
  await page.getByLabel('Clock', { exact: true }).selectOption({ label: 'tb.clk' });
  const evidence = [];
  evidence.push(await cursor(120000, { 'tb.count[3:0]': '1010', 'tb.enable': '0' }));
  evidence.push(await cursor(125000, { 'tb.count[3:0]': '1010' }));
  evidence.push(await cursor(205000, { 'tb.count[3:0]': '0000' }));
  evidence.push(await cursor(232000, { 'tb.count[3:0]': '0001', 'tb.reset': '1' }));
  evidence.push(await cursor(235000, { 'tb.count[3:0]': '0000' }));
  await cursor(120000, { 'tb.count[3:0]': '1010' });
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: /下载 Markdown/ }).click();
  const file = await download;
  const text = await readFile(await file.path(), 'utf8');
  check(text.includes('1010') && text.includes('120000') && text.includes('Limitations'), 'report content does not reflect analysis');
  await page.screenshot({ path: 'docs/screenshots/qa-counter.png', fullPage: true });
  return { timescale: trace.timescale, observations: evidence, report: { filename: file.suggestedFilename(), bytes: Buffer.byteLength(text) } };
});
await step('Zoom, pan, search and RTL matching change the interface', async () => {
  const before = await page.locator('.waveform footer').innerText();
  await page.getByLabel('放大', { exact: true }).click();
  const zoom = await page.locator('.waveform footer').innerText();
  check(before !== zoom, 'zoom did not change viewport');
  await page.getByLabel('向后平移').click();
  const pan = await page.locator('.waveform footer').innerText();
  check(pan !== zoom, 'pan did not change viewport');
  await page.getByLabel('缩小', { exact: true }).click();
  await page.getByRole('button', { name: 'Fit', exact: true }).click();
  await page.getByLabel('搜索信号').fill('count');
  check(await page.locator('.signal-option').count() === 2, 'search result mismatch');
  await page.getByLabel('搜索信号').fill('');
  await page.getByLabel('RTL 文件').selectOption('design.sv');
  await page.getByLabel('搜索 RTL').fill('enable');
  check(await page.locator('.code-line.search-match').count() === 2, 'RTL search mismatch');
  await page.locator('.rtl').screenshot({ path: 'docs/screenshots/qa-rtl.png' });
  await page.getByLabel('搜索 RTL').fill('');
  await page.locator('.insights').screenshot({ path: 'docs/screenshots/qa-analysis.png' });
  return { before, zoom, pan, countMatches: 2, rtlMatches: 2 };
});
await step('FIFO full, rejected write and empty boundary', async () => {
  await page.getByRole('button', { name: /02 \/ DEMO FIFO/ }).click();
  await page.locator('.trace-bar').getByText('fifo.vcd', { exact: true }).waitFor();
  await page.locator('.facts').waitFor();
  const observations = [];
  observations.push(await cursor(55000, { 'tb.full': '1', 'tb.empty': '0', 'tb.count[2:0]': '100' }));
  observations.push(await cursor(65000, { 'tb.count[2:0]': '100' }));
  observations.push(await cursor(115000, { 'tb.empty': '1', 'tb.rd_data[7:0]': '01010101' }));
  await page.screenshot({ path: 'docs/screenshots/qa-fifo.png', fullPage: true });
  return observations;
});
await step('Handshake before/after transfer and data held under backpressure', async () => {
  await page.getByRole('button', { name: /03 \/ DEMO Handshake/ }).click();
  await page.locator('.trace-bar').getByText('handshake.vcd', { exact: true }).waitFor();
  await page.locator('.facts').waitFor();
  const observations = [];
  observations.push(await cursor(54999, { 'tb.valid': '1', 'tb.ready': '1', 'tb.data[7:0]': '10100001', 'tb.sent[1:0]': '00' }));
  observations.push(await cursor(55000, { 'tb.sent[1:0]': '01' }));
  observations.push(await cursor(75000, { 'tb.valid': '1', 'tb.ready': '0', 'tb.data[7:0]': '10100010', 'tb.sent[1:0]': '01' }));
  observations.push(await cursor(95000, { 'tb.sent[1:0]': '10' }));
  observations.push(await cursor(105000, { 'tb.sent[1:0]': '11', 'tb.valid': '0' }));
  await page.screenshot({ path: 'docs/screenshots/qa-handshake.png', fullPage: true });
  return observations;
});
await step('Malformed upload shows error and next valid demo recovers', async () => {
  await page.getByLabel('上传 VCD', { exact: true }).setInputFiles({ name: 'invalid.vcd', mimeType: 'text/plain', buffer: Buffer.from('$timescale 1 ns $end\n$comment truncated') });
  await page.getByRole('alert').waitFor();
  const message = await page.getByRole('alert').innerText();
  await page.screenshot({ path: 'docs/screenshots/qa-upload-error.png', fullPage: true });
  await page.getByRole('button', { name: /01 \/ DEMO Counter/ }).click();
  await page.locator('.facts').waitFor();
  check(await page.getByRole('alert').count() === 0, 'error did not clear');
  return { expectedStatus: 422, message };
});
await step('Console and network audit', async () => {
  check(errors.length === 0, `JS errors: ${errors.join('; ')}`);
  check(failedRequests.length === 0, 'unexpected failed requests');
  check(badResponses.every(r => r.path === '/api/traces' && r.status === 422), 'unexpected HTTP errors');
  return { errors, failedRequests, badResponses };
});
await writeFile(output, JSON.stringify({ phase, browser: browser.version(), observations, errors, failedRequests, badResponses }, null, 2));
await browser.close();
console.log(JSON.stringify(observations.map(({ name, status, error }) => ({ name, status, error })), null, 2));
if (observations.some(s => s.status === 'FAIL')) process.exitCode = 1;
