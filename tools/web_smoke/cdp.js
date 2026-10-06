// 极简 CDP 驱动：用 Node 22 内置 WebSocket，无需第三方包
// 用法: node cdp.js <jsFile>    jsFile 需 module.exports = async (page) => {...}
const PORT = process.env.CDP_PORT || 9222;

async function getWS() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const p = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (p) return p.webSocketDebuggerUrl;
    } catch (e) { /* 还没起来 */ }
    await new Promise(s => setTimeout(s, 250));
  }
  throw new Error(`CDP 端口 ${PORT} 上没找到页面`);
}

(async () => {
  const ws = new WebSocket(await getWS());
  await new Promise(res => ws.addEventListener('open', res));

  const map = new Map();
  let id = 0;
  const send = (method, params = {}) => new Promise((res, rej) => {
    const myId = ++id;
    map.set(myId, { res, rej });
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  // confirm() / alert() 在无头模式下会卡死 JS，一律自动点「确定」
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && map.has(m.id)) {
      const { res, rej } = map.get(m.id);
      map.delete(m.id);
      m.error ? rej(new Error(m.error.message)) : res(m.result);
      return;
    }
    if (m.method === 'Page.javascriptDialogOpening') {
      send('Page.handleJavaScriptDialog', { accept: true });
    }
  });

  const page = {
    send,
    async evaluate(expression) {
      const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
      if (r.exceptionDetails) {
        const d = r.exceptionDetails.exception?.description || r.exceptionDetails.text;
        throw new Error('页面 JS 异常: ' + d);
      }
      return r.result.value;
    },
    async nav(url) {
      await send('Page.enable');
      const done = new Promise(res => {
        const h = ev => {
          const m = JSON.parse(ev.data);
          if (m.method === 'Page.loadEventFired') { ws.removeEventListener('message', h); res(); }
        };
        ws.addEventListener('message', h);
      });
      await send('Page.navigate', { url });
      await Promise.race([done, new Promise(r => setTimeout(r, 6000))]);
      await new Promise(s => setTimeout(s, 1500));
    },
    async click(sel) {
      const ok = await page.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(sel)});if(!e)return false;e.click();return true;})()`);
      if (!ok) throw new Error('点不到 ' + sel);
      await new Promise(s => setTimeout(s, 250));
    }
  };

  await send('Runtime.enable');
  await send('Page.enable');
  const mod = require(process.argv[2]);
  let fail = 0;
  const ok = (cond, name, extra) => {
    console.log((cond ? '  ✔ ' : '  ✘ ') + name + (cond ? '' : '   → ' + JSON.stringify(extra)));
    if (!cond) fail++;
  };
  try {
    await mod(page, ok, send);
  } catch (e) {
    console.log('  ✘ 抛出异常: ' + e.message);
    fail++;
  }
  console.log(fail ? `\n有 ${fail} 项没过` : '\n全部通过');
  process.exitCode = fail ? 1 : 0;
  ws.close();
})();
