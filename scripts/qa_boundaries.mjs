import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { writeFile } from 'node:fs/promises';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const observations = [], errors = [];
page.on('pageerror', e => errors.push(e.message));
const check = (ok, why) => { if (!ok) throw Error(why); };
async function step(name, action) {
  try { observations.push({ name, status: 'PASS', evidence: await action() }); }
  catch (e) { const screenshot = `docs/screenshots/qa-boundary-failure-${observations.length}.png`; await page.screenshot({path:screenshot,fullPage:true}); observations.push({name,status:'FAIL',error:e.message,screenshot}); }
}
async function upload(text, name='boundary.vcd') {
  await page.getByLabel('上传 VCD', {exact:true}).setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from(text)});
}
async function jump(tick) {
  await page.getByLabel('整数 tick').fill(String(tick));
  await page.getByRole('button',{name:'跳转',exact:true}).click();
  await page.locator('.facts').getByText(`t=${tick} tick`,{exact:false}).first().waitFor();
}
const vcd = (body, width=1, ref='sig') => `$timescale 1 ns $end\n$var wire ${width} ! ${ref} $end\n$enddefinitions $end\n${body}\n`;
await page.goto('http://127.0.0.1:5173');
await step('Oversized identifier and unsupported dump gap reject safely', async () => {
  await upload(`$timescale 1 ns $end\n$scope module ${'s'.repeat(4096)} $end\n$var wire 1 ! sig $end\n$upscope $end\n$enddefinitions $end\n#0\n1!\n`);
  await page.getByRole('alert').filter({hasText:'256'}).waitFor();
  const identifierError=await page.getByRole('alert').innerText();
  await upload(vcd('#0\n1!\n#10\n$dumpoff\n$end\n#20'));
  await page.getByRole('alert').filter({hasText:'$dumpoff'}).waitFor();
  const dumpError=await page.getByRole('alert').innerText();
  await page.screenshot({path:'docs/screenshots/qa-dump-rejected.png',fullPage:true});
  return {identifierError,dumpError};
});
await step('One-tick bidirectional pan and maximum integer zoom', async () => {
  await upload(vcd('#0\n0!\n#10\n1!\n#100'));
  await page.locator('.facts').waitFor(); await jump(10);
  for(let i=0;i<7;i++) await page.getByLabel('放大',{exact:true}).click();
  check((await page.locator('.waveform footer').innerText()).includes('窗口 10–11 ticks'),'one tick window missing');
  await page.getByLabel('向前平移').click();
  check((await page.locator('.waveform footer').innerText()).includes('窗口 9–10 ticks'),'backward pan stuck');
  await page.getByLabel('向后平移').click();
  check((await page.locator('.waveform footer').innerText()).includes('窗口 10–11 ticks'),'forward pan failed');
  const max=Number.MAX_SAFE_INTEGER;
  await upload(vcd(`#0\n0!\n#${max-1}\n1!\n#${max}`));
  await page.locator('.facts').waitFor(); await jump(max);
  for(let i=0;i<54;i++) await page.getByLabel('放大',{exact:true}).click();
  const end=await page.locator('.waveform footer').innerText();
  check(end.includes(`窗口 ${max-1}–${max} ticks`),'unsafe integer zoom');
  await page.getByLabel('向前平移').click();
  const back=await page.locator('.waveform footer').innerText();
  check(back.includes(`窗口 ${max-2}–${max-1} ticks`),'unsafe integer pan');
  return {end,back};
});
await step('Zero-duration trace and raw same-tick evidence remain honest', async () => {
  await upload(vcd('#0\nx!'));
  await page.locator('.facts').waitFor();
  const labels=await page.locator('.wave-body svg text').allTextContents();
  check(labels.length===9 && labels.every(x=>x==='0'),'axis invented time');
  await upload(vcd('#0\n0!\n#5\n1!\n0!\n#10\n1!'));
  await page.locator('.facts').waitFor(); await jump(5);
  await page.locator('.event-card summary').click();
  const events=await page.locator('.event-card .events').innerText();
  check((await page.locator('.event-card .events button').allTextContents()).filter(x=>x==='5').length===2,'same tick records lost');
  await jump(10);
  check((await page.locator('.wave-labels').innerText()).includes('0x1'),'right endpoint value lost');
  return {labels,events,notice:await page.locator('.waveform').getByText(/图形仅绘制持续区间/).innerText()};
});
await step('Dense RTL is paged, global search retains original CR line numbers', async () => {
  await page.getByRole('button',{name:/01 \/ DEMO Counter/}).click(); await page.locator('.facts').waitFor();
  const text=Array.from({length:10001},(_,i)=> i===10000 ? 'wire count; // unique_target' : '// filler').join('\r');
  await page.getByLabel('上传 RTL',{exact:true}).setInputFiles({name:'dense.sv',mimeType:'text/plain',buffer:Buffer.from(text)});
  await page.getByLabel('RTL 文件').selectOption('dense.sv');
  check(await page.locator('.code-line').count()===200,'RTL DOM not bounded');
  await page.getByRole('button',{name:'下一页',exact:true}).click();
  check(await page.locator('.line-number').first().innerText()==='201','pagination line number wrong');
  await page.getByLabel('搜索 RTL').fill('unique_target');
  await page.locator('.code-line.search-match').waitFor();
  check(await page.locator('.code-line').count()===1,'search not across full file');
  check(await page.locator('.line-number').innerText()==='10001','CR line numbering wrong');
  check(await page.locator('.code-line.related').count()===1,'name association missing');
  await page.screenshot({path:'docs/screenshots/qa-rtl-paged.png',fullPage:true});
  return {sourceLines:10001,maxDomRows:200,searchLine:10001};
});
await step('Wide bus labels show ellipsis and full tooltip, unknowns preserved', async () => {
  const bits='1'.repeat(254)+'xz';
  await upload(vcd(`#0\nb${bits} !\n#100`,256,'wide'));
  await page.locator('.facts').waitFor();
  const labels=await page.locator('.wave-body svg text').allTextContents();
  check(labels.some(x=>x.endsWith('…')),'no explicit ellipsis');
  const title=await page.locator('.wave-body svg title').textContent();
  check(title.includes(bits),'tooltip missing full value');
  for(const format of ['bin','hex','dec']) { await page.getByLabel('总线显示格式').selectOption(format); check((await page.locator('.wave-labels code').innerText()).includes(bits),'unknown bits converted'); }
  await page.screenshot({path:'docs/screenshots/qa-wide-bus.png',fullPage:true});
  return {labels,title};
});
await step('Small, medium and near-limit browser rendering and interactions', async () => {
  const results=[];
  for(const name of ['small','medium','near-limit']) {
    const started=performance.now();
    await page.getByLabel('上传 VCD',{exact:true}).setInputFiles(`docs/qa/evidence/performance-final/${name}.vcd`);
    await page.locator('.facts').waitFor();
    const load=performance.now()-started;
    const before=await page.locator('.waveform footer').innerText();
    let t=performance.now(); await page.getByLabel('放大',{exact:true}).click();
    await page.waitForFunction(before=>document.querySelector('.waveform footer').textContent!==before,before);
    const zoom=performance.now()-t;
    t=performance.now(); await page.getByLabel('搜索信号').fill('data');
    check(await page.locator('.signal-option').count()===1,'signal search');
    const search=performance.now()-t; await page.getByLabel('搜索信号').fill('');
    t=performance.now(); await jump(12); const query=performance.now()-t;
    results.push({name,uploadToFactsMs:load,zoomMs:zoom,searchMs:search,cursorToFactsMs:query,svgPaths:await page.locator('.wave-body svg path').count(),warning:await page.locator('.waveform .warning').allTextContents(),samples:1});
  }
  return results;
});
await step('AI question and consent changes invalidate mocked results and requests', async () => {
  await page.route('**/api/health',r=>r.fulfill({json:{ai_configured:true,requests:0}}));
  await page.reload();
  await page.getByRole('button',{name:/01 \/ DEMO Counter/}).click(); await page.locator('.facts').waitFor();
  const output={summary:'推测：Mock result',observed_facts:[],possible_explanations:[],related_signals:[],related_code:[],suggested_checks:[],limitations:['Mock only']};
  await page.route('**/explain',r=>r.fulfill({json:output}));
  await page.getByLabel(/我确认将选中信号/).check();
  await page.getByRole('button',{name:'生成解释'}).click(); await page.locator('.explanation-result').waitFor();
  await page.getByLabel('向 AI 提问').fill('新问题');
  await page.locator('.explanation-result').waitFor({state:'detached'});
  let release;
  await page.route('**/explain',async r=> { await new Promise(resolve=>release=resolve); await r.fulfill({json:output}).catch(()=>{}); });
  const sent=page.waitForRequest('**/explain');
  await page.getByRole('button',{name:'生成解释'}).click(); await sent;
  await page.getByLabel(/我确认将选中信号/).uncheck(); release();
  await page.getByRole('button',{name:'取消请求'}).waitFor({state:'detached'});
  check(await page.locator('.explanation-result').count()===0,'stale AI result');
  check(await page.getByRole('button',{name:'生成解释'}).isDisabled(),'consent bypass');
  check(await page.getByLabel('向 AI 提问').getAttribute('maxlength')==='2000','question limit missing');
  return {transport:'browser route Mock, no provider request',staleResultCleared:true,consentRevocationAbortsWait:true};
});
await step('Narrow viewport remains navigable and no JavaScript exceptions', async () => {
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:/01 \/ DEMO Counter/}).click(); await page.locator('.facts').waitFor();
  await page.screenshot({path:'docs/screenshots/qa-mobile.png',fullPage:true});
  const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
  check(width.document<=width.viewport,'page horizontal overflow');
  check(errors.length===0,errors.join('; ')); return {width,errors};
});
await writeFile('docs/qa/evidence/browser-boundaries-final.json',JSON.stringify({browser:browser.version(),observations,errors},null,2));
await browser.close();
console.log(JSON.stringify(observations,null,2));
if(observations.some(x=>x.status==='FAIL'))process.exitCode=1;
