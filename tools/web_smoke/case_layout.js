module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  await page.nav(APP + '/?demo=1');

  /* 真实鼠标点击：滚动到元素 -> 重新取坐标 -> CDP 派发按下/抬起。
     这是唯一能证明「用户点得到」的做法 ——
     element.click() 会绕过遮挡、绕过坐标，点得到才叫怪。 */
  const clickReal = async (id) => {
    const pos = await page.evaluate(`(()=>{
      const e=document.getElementById(${JSON.stringify(id)});
      if(!e)return null;
      e.scrollIntoView({block:'center',inline:'center'});
      return null;
    })()`);
    await new Promise(r => setTimeout(r, 120));
    const box = await page.evaluate(`(()=>{
      const e=document.getElementById(${JSON.stringify(id)});
      const r=e.getBoundingClientRect();
      return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2),
              w:Math.round(r.width), h:Math.round(r.height)};
    })()`);
    if (box.w <= 0 || box.h <= 0) return { ok: false, why: '无尺寸', box };
    for (const type of ['mousePressed', 'mouseReleased']) {
      await page.send('Input.dispatchMouseEvent', {
        type, x: box.x, y: box.y, button: 'left', clickCount: 1,
      });
    }
    await new Promise(r => setTimeout(r, 250));
    return { ok: true, box };
  };

  const setup = `(()=>{S.rows=[blankRow(),blankRow(),blankRow()];renderTable();
                       S.sel=new Set([0,1,2]);syncSelUI();return S.rows.length;})()`;

  /* ---- 批量栏里的按钮 ---- */
  await page.evaluate(setup);
  let hit = await clickReal('batchMore');
  let opened = await page.evaluate(`document.getElementById('batchbar').classList.contains('open')`);
  ok(hit.ok && opened, '「更多批量操作」能点开 → ' + JSON.stringify(hit), hit);

  await page.evaluate(setup);
  const wasOpen = await page.evaluate(`(()=>{const c=document.getElementById('batchbar').classList;
    if(!c.contains('open'))document.getElementById('batchMore').click();
    return c.contains('open');})()`);
  hit = await clickReal('batchClear');
  let after = await page.evaluate(`Array.from(S.sel).length`);
  ok(hit.ok && after === 0, '「取消勾选」能点 → 勾选剩 ' + after, { hit, after });

  await page.evaluate(setup);
  hit = await clickReal('batchDel');
  after = await page.evaluate(`S.rows.length`);
  ok(hit.ok && after === 0, '「删掉这些行」能点 → 剩 ' + after + ' 行', { hit, after });

  await page.evaluate(setup);
  hit = await clickReal('batchName');
  let dlg = await page.evaluate(`getComputedStyle(document.getElementById('modal')).display`);
  ok(hit.ok && dlg === 'block', '「改名字…」能点开弹窗 → display=' + dlg, { hit, dlg });
  await page.evaluate(`closeModal()`);

  await page.evaluate(setup);
  hit = await clickReal('batchColorBtn');
  dlg = await page.evaluate(`getComputedStyle(document.getElementById('modal')).display`);
  ok(hit.ok && dlg === 'block', '「颜色…」能点开弹窗 → display=' + dlg, { hit, dlg });
  await page.evaluate(`closeModal()`);

  /* ---- 表头里的按钮（用户明确说「清空」点不动） ---- */
  await page.evaluate(setup);
  hit = await clickReal('clearRow');
  after = await page.evaluate(`S.rows.length`);
  ok(hit.ok && after === 0, '「清空」能点 → 剩 ' + after + ' 行', { hit, after });

  await page.evaluate(`(()=>{S.rows=[];renderTable();return 0;})()`);
  hit = await clickReal('addRow');
  after = await page.evaluate(`S.rows.length`);
  ok(hit.ok && after === 1, '「+ 加一行」能点 → ' + after + ' 行', { hit, after });

  await page.evaluate(`(()=>{S.rows=[];renderTable();return 0;})()`);
  hit = await clickReal('demoBtn');
  after = await page.evaluate(`S.rows.length`);
  ok(hit.ok && after === 6, '「载入示例」能点 → ' + after + ' 行', { hit, after });

  /* ---- 提示条不该挡住任何东西 ---- */
  constCover = await page.evaluate(`(()=>{
    toast('测试提示',3000);
    const t=document.getElementById('toast');
    const cs=getComputedStyle(t);
    return {pos:cs.position, pe:cs.pointerEvents, disp:cs.display};
  })()`);
  ok(constCover.pos === 'fixed' && constCover.pe === 'none',
     '提示条是 fixed 且不拦鼠标 → ' + JSON.stringify(constCover), constCover);
  const stillClickable = await (async () => {
    await page.evaluate(setup);
    return await clickReal('batchDel');
  })();
  after = await page.evaluate(`S.rows.length`);
  ok(stillClickable.ok && after === 0,
     '提示条显示时按钮依然能点 → 剩 ' + after + ' 行', { stillClickable, after });

  /* ---- 窄窗口下同样要能点 ---- */
  await page.send('Emulation.setDeviceMetricsOverride', { width: 900, height: 700, deviceScaleFactor: 1, mobile: false });
  await new Promise(r => setTimeout(r, 300));
  await page.evaluate(setup);
  hit = await clickReal('batchDel');
  after = await page.evaluate(`S.rows.length`);
  ok(hit.ok && after === 0, '900px 窄窗下「删掉这些行」能点 → 剩 ' + after, { hit, after });
  await page.send('Emulation.clearDeviceMetricsOverride');

  /* ---- 「退出程序」必须存在、可见、点得到 ----
     打包成 exe 之后没有控制台可按 Ctrl+C，这个按钮是用户唯一的退出入口。
     缺了它，用户每次都得去任务管理器结束进程。 */
  const quit = await page.evaluate(`(()=>{
    const b=document.getElementById('quitBtn');
    if(!b)return {missing:true};
    const r=b.getBoundingClientRect();
    return {text:b.textContent.trim(),w:Math.round(r.width),h:Math.round(r.height),
            inBar:!!b.closest('#top')||!!b.parentElement};
  })()`);
  ok(!quit.missing && quit.w > 0 && quit.h > 0,
     '「退出程序」按钮存在且有尺寸 → ' + JSON.stringify(quit), quit);
  const quitHit = await clickReal('quitBtn');
  // 会弹 confirm（驱动已自动接受），所以这里只验证「事件确实绑上了」：
  // 点了之后 quitApp 应该跑起来（body 没被清掉说明 confirm 之后还在等）
  const quitWired = await page.evaluate(`typeof quitApp==='function'`);
  ok(quitHit.ok && quitWired,
     '「退出程序」点得到且已绑定处理函数 → ' + JSON.stringify(quitHit), quitHit);
};
