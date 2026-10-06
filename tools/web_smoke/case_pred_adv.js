/* 分字段推算 + 「更多细则」面板跟随（这一轮改的规矩）：

   ① 触发一条技法的不止是按键 —— 通道 / CC 号 / CC 值也各自成串、各自给提示
      （以前只有触发键和通道有提示，CC 行还一律被喊成「缺键」）
   ② 细则参数（长度 / 转调 / 力度窗口…）同样成串：**改哪个框就提示哪个框**，
      空框里画出灰色的 ≈ 值，点一下就采用；一键补齐也覆盖它们
   ③ 「更多细则」面板和表格共用同一行：表格换行面板跟着换；
      面板里 ↑↓ 换行（焦点留在同一个框）、Tab 换到下一行同一个框并进编辑模式
   ④ 右侧「每层现在有哪些技法」按**每行自己的触发方式**报缺什么，
      不再一律喊「缺键」——CC 号 / 通道 缺了要说清楚缺的是哪个
   这里全走真实事件（真 dispatch 一个 keydown），不用函数级 mock。 */
module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  await page.nav(APP + '/?demo=1');

  /* ================= ① CC 行各自成串 ================= */
  const cc = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows.forEach(r=>{r.switch='cc';});
    S.rows[0].cc_num=4; S.rows[2].cc_num=4;          // CC 号整串一样
    S.rows[0].cc_val=1; S.rows[2].cc_val=3;          // CC 值 1,_,3
    renderTable();
    return {num:S.pred.cc_num.values[1], val:S.pred.cc_val.values[1],
            note:S.pred.note.values[1]};
  })()`);
  ok(cc.num === 4, 'CC 号整串一样 → 空的那格也推 4 → ' + cc.num, cc);
  ok(cc.val === 2, 'CC 值 1 空空 3 → 推 2 → ' + cc.val, cc);
  ok(cc.note === undefined, 'CC 行不参与「按键」的串（按键行 / CC 行互不干扰）', cc);

  /* CC 行的灰提示要**各自挂在各自的框後面**（CC 号那格推号、CC 值那格推值），
     点某一个只填那一个 —— 以前是拼成一个「CC4=2」挂在触发键那个框上。 */
  const cctag = await page.evaluate(`(()=>{
    const cell=document.querySelector('#tbody tr[data-r="1"] td:nth-child(7)');
    const at=f=>{const t=cell.querySelector('.predtag[data-pf="'+f+'"]');
      return t?t.textContent.trim():null;};
    return {num:at('cc_num'),val:at('cc_val'),
            fields:Array.from(cell.querySelectorAll('[data-f]')).map(e=>e.dataset.f)};})()`);
  ok(JSON.stringify(cctag.fields) === JSON.stringify(['cc_num', 'cc_val']),
     'CC 行给的是两个专用框 → ' + JSON.stringify(cctag.fields), cctag);
  ok(cctag.num === '≈4' && cctag.val === '≈2',
     'CC 号 / CC 值各自的灰提示 → ' + JSON.stringify(cctag), cctag);
  const cctake = await page.evaluate(`(()=>{
    const cell=document.querySelector('#tbody tr[data-r="1"] td:nth-child(7)');
    cell.querySelector('.predtag[data-pf="cc_val"]').click();
    return {num:S.rows[1].cc_num,val:S.rows[1].cc_val};})()`);
  ok(cctake.val === 2 && cctake.num == null,
     '点 CC 值那格的灰提示 → 只填值、不碰 CC 号 → ' + JSON.stringify(cctake), cctake);

  /* ================= ② 细则参数成串 + 面板里的灰提示 ================= */
  const adv = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.switch='ks';r.note=24+i;r.name='t'+(i+1);});
    S.rows[0].length_fact=0.2; S.rows[2].length_fact=0.6;
    renderTable();
    openAdv(1);
    const el=document.getElementById('advLength');
    const tag=el.parentNode.querySelector('.predtag');
    const cell=document.querySelector('#tbody tr[data-r="1"] .predtag');
    return {v:S.pred.length_fact.values[1], val:el.value,
            ph:el.placeholder, tag:tag?tag.textContent.trim():null,
            cell:cell?cell.textContent.trim():null};
  })()`);
  ok(Math.abs(adv.v - 0.4) < 1e-9, '长度 0.2 空空 0.6 → 推 0.4（小数也要能插值）', adv);
  ok(adv.val === '' && adv.ph.indexOf('0.4') >= 0 && adv.tag && adv.tag.indexOf('0.4') >= 0,
     '细则里的空框画出灰提示 → ' + adv.tag, adv);
  ok(adv.cell === null,
     '触发键都填好了，触发键那格就不再出提示（改的是哪个框就提示哪个框）→ ' + adv.cell, adv);

  const advTake = await page.evaluate(`(()=>{
    const el=document.getElementById('advLength');
    el.parentNode.querySelector('.predtag').click();
    return {v:S.rows[1].length_fact, ph:document.getElementById('advLength').placeholder};
  })()`);
  ok(Math.abs(advTake.v - 0.4) < 1e-9, '点一下面板上的灰提示就填进去 → ' + advTake.v, advTake);
  ok(advTake.ph.indexOf('0.4') < 0, '采用之后提示消失', advTake);

  /* 一键补齐也要管细则参数，不是只管触发键 */
  const fill = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.switch='ks';r.note=24+i;});
    S.rows[0].length_fact=0.2; S.rows[2].length_fact=0.6;
    renderTable(); fillAllPred();
    return S.rows.map(r=>r.length_fact);
  })()`);
  ok(JSON.stringify(fill) === JSON.stringify([0.2,0.4,0.6]),
     '「补齐推算出来的值」连细则参数一起补 → ' + JSON.stringify(fill), fill);

  /* ================= ③ 面板跟表格共用同一行 ================= */
  const nav = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.name='t'+(i+1);r.switch='ks';r.note=24+i;});
    renderTable(); openAdv(0);
    const key=(el,k,shift)=>el.dispatchEvent(new KeyboardEvent('keydown',
      {key:k,shiftKey:!!shift,bubbles:true,cancelable:true}));
    const st=()=>({adv:S.advIdx,act:S.actIdx,focus:document.activeElement.id,
      cur:(document.querySelector('#tbody tr.currow')||{dataset:{}}).dataset.r});
    const out={start:st()};
    document.getElementById('advLength').focus();
    key(document.activeElement,'ArrowDown'); out.down=st();
    key(document.activeElement,'Tab');       out.tab=st();
    key(document.activeElement,'Tab',true);  out.shiftTab=st();
    return out;
  })()`);
  ok(nav.start.adv === 0 && nav.start.act === 0,
     '打开细则时表格和面板指着同一行 → ' + JSON.stringify(nav.start), nav.start);
  ok(nav.down.adv === 1 && nav.down.act === 1 && nav.down.cur === '1'
     && nav.down.focus === 'advLength',
     '面板里 ↓ 换到下一行，且焦点还留在同一个框 → ' + JSON.stringify(nav.down), nav.down);
  ok(nav.tab.adv === 2 && nav.tab.act === 2 && nav.tab.focus === 'advLength',
     '面板里 Tab 换到下一行的同一个框 → ' + JSON.stringify(nav.tab), nav.tab);
  ok(nav.shiftTab.adv === 1, 'Shift+Tab 往回走 → ' + nav.shiftTab.adv, nav.shiftTab);

  /* 表格里换行（方向键 / Tab），面板内容必须跟着切 —— 以前面板会停在旧行 */
  const fol = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.name='x'+(i+1);r.switch='ks';r.note=24+i;});
    renderTable(); openAdv(0);
    const c=document.querySelector('#tbody tr[data-r="0"] [data-k="name"]');
    c.focus();
    c.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));
    const a={adv:S.advIdx,act:S.actIdx,who:document.getElementById('advWho').textContent};
    const c2=document.querySelector('#tbody tr[data-r="1"] [data-k="name"]');
    c2.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));
    a.tab={adv:S.advIdx,act:S.actIdx,who:document.getElementById('advWho').textContent};
    return a;
  })()`);
  ok(fol.adv === 1 && fol.act === 1 && fol.who.indexOf('第 2 行') >= 0,
     '表格里 ↓ 换行 → 细则切到第 2 行 → ' + fol.who, fol);
  ok(fol.tab.adv === 2 && fol.tab.who.indexOf('第 3 行') >= 0,
     '表格里 Tab 换行 → 细则切到第 3 行 → ' + fol.tab.who, fol);

  /* ================= ④ 右侧自检：按每行的触发方式说话 ================= */
  const chips = await page.evaluate(`(()=>{
    S.rows=[];
    S.rows.push(Object.assign(blankRow(),{name:'按键技法',switch:'ks',note:24}));
    S.rows.push(Object.assign(blankRow(),{name:'CC技法',switch:'cc',cc_num:4,cc_val:100}));
    S.rows.push(Object.assign(blankRow(),{name:'通道技法',switch:'ch',channel:2}));
    S.rows.push(Object.assign(blankRow(),{name:'没填键的按键技法',switch:'ks',note:null}));
    S.rows.push(Object.assign(blankRow(),{name:'缺CC号的',switch:'cc',cc_num:null}));
    renderTable();
    return document.getElementById('layers').textContent;
  })()`);
  ok(chips.indexOf('CC技法 · CC4=100') >= 0,
     'CC 触发的技法照实显示 CC4=100，不再误报「缺键」', chips);
  ok(chips.indexOf('通道技法 · 通道 2') >= 0, '通道触发的技法显示「通道 2」', chips);
  ok(chips.indexOf('没填键的按键技法 · 缺键') >= 0, '真的缺按键的才报「缺键」', chips);
  ok(chips.indexOf('缺CC号的 · 缺CC 号') >= 0, 'CC 行缺 CC 号要说清缺的是 CC 号', chips);

  const tm = await page.evaluate(`(()=>([
    triggerMissing({switch:'ks',note:null}),
    triggerMissing({switch:'cc',cc_num:4,cc_val:null}),
    triggerMissing({switch:'ch',channel:null}),
    triggerMissing({switch:'none'}),
    triggerMissing({switch:'ks',note:24})
  ]))()`);
  ok(JSON.stringify(tm[0]) === JSON.stringify(['note']), '按键行缺 note', tm);
  ok(JSON.stringify(tm[1]) === JSON.stringify(['cc_val']), 'CC 号填了但没填值 → 缺 cc_val', tm);
  ok(JSON.stringify(tm[2]) === JSON.stringify(['channel']), '通道行缺 channel', tm);
  ok(JSON.stringify(tm[3]) === JSON.stringify([]), '「常驻，不切换」不缺任何东西', tm);
  ok(JSON.stringify(tm[4]) === JSON.stringify([]), '填好的行不报缺', tm);

  /* ================= ⑤ 加一行的续排：CC 与细则参数 ================= */
  const arow = await page.evaluate(`(()=>{
    S.rows=[];
    S.rows.push(Object.assign(blankRow(),{switch:'cc',cc_num:4,cc_val:1,length_fact:0.2}));
    S.rows.push(Object.assign(blankRow(),{switch:'cc',cc_num:4,cc_val:2,length_fact:0.2}));
    renderTable(); addRow();
    const r=S.rows[2];
    return {sw:r.switch,num:r.cc_num,val:r.cc_val,len:r.length_fact,note:r.note};
  })()`);
  ok(arow.sw === 'cc' && arow.num === 4 && arow.val === 3,
     'CC 行加一行：CC 号照旧 4、CC 值接着排 3 → ' + JSON.stringify(arow), arow);
  ok(Math.abs(arow.len - 0.2) < 1e-9 && arow.note === null,
     '细则参数「前面几行都一样」就跟着填同一个值，按键行才排键位 → ' + JSON.stringify(arow), arow);
};
