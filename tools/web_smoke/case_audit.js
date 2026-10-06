/* 生成前审核：按「这一行实际带了哪些触发部件」判定，不是只看触发键。
   —— 用户报的 bug：拿通道当触发器用（通道填在「更多细则」里），
   类型栏还写着「按键切换」，导出审核却只喊「缺键」。
   实际后端行为（em/methods/base.py）：
     · 只有 ks / ks2 / ks+ch 才发 NoteOn；键位空 → key=-1
     · 键位空但通道有值 → key=-1 + 通道 + 空 midiMessages = 纯通道触发的形状
     · autofill 只负责**补**：补不补由「自动补触发键」开关决定（界面上默认关）。
       关着 → 空键位保持空（key=-1，纯通道触发）；打开 → 才从起始键往后补一个。
   所以：通道填了就不该再被骂「缺键」；文案还要跟着开关说对
   （关＝按通道触发不用按键 / 开＝会补一个键位）。 */
module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  const TMP = (process.env.SMOKE_TMP || '').replace(/\\/g, '/');
  // ⚠️ 别用 ?ac=1：那是「exe 打开的页面」标记，关页面会 sendBeacon('/api/shutdown')
  //    把服务退掉，后面几个用例就全是 "Failed to fetch"。冒烟统一用 ?demo=1。
  await page.nav(APP + '/?demo=1');

  // confirm 拦下来只记文字（返回 false → 不会真的去生成）
  await page.evaluate(`(()=>{
    window.__msgs=[];
    window.confirm=(m)=>{window.__msgs.push(m);return false;};
    window.__probe=function(rows,panel){
      S.rows=rows.map(o=>Object.assign(blankRow(),{name:'t',description:'t'},o));
      S.rows.forEach(r=>{r.conditions=[{group:r.group,description:r.name,note:r.note}];});
      renderTable();
      if(panel!=null)openAdv(panel);
      return true;
    };
    window.__gen=function(){window.__msgs=[];document.getElementById('genBtn').click();
      return window.__msgs.length?window.__msgs[0]:'';};
  })()`);

  /* ---------- 1. 用户那个 case：3 行「按键切换」+ 面板里填了通道 → 不该再拦 ---------- */
  const e = await page.evaluate(`(()=>{
    __probe([{switch:'ks'},{switch:'ks'},{switch:'ks'}],0);
    S.rows.forEach((r,i)=>{r.channel=i+1;});
    renderTable(true);
    return __gen();
  })()`);
  ok(e === '', '按键切换 + 只填了通道 → 不该再拦「缺键」', e);

  // 表格里要看得见「通道 N」，而不是一片空白
  const tags = await page.evaluate(`(()=>{
    const t=document.querySelectorAll('#tbody .chantag');
    return {n:t.length, txt:t.length?t[0].textContent.trim():''};
  })()`);
  ok(tags.n === 3 && /通道 1/.test(tags.txt),
     '触发键格里挂出「通道 N」蓝标 → ' + JSON.stringify(tags), tags);

  // 右侧技法清单也要说清楚（不能还写「缺键」），而且文案要跟着「自动补触发键」开关走：
  //   关着（默认）= 按通道触发，不多按一个键；打开 = 会补一个键位。
  const chips = await page.evaluate(`(()=>{
    const el=document.getElementById('autofill');
    const before=el.checked;
    el.checked=false; paintAutoFill(); renderTable();
    const off=document.getElementById('layers').textContent;
    el.checked=true;  paintAutoFill(); renderTable();
    const on=document.getElementById('layers').textContent;
    el.checked=before; paintAutoFill(); renderTable();   // 还原，别影响后面的步骤
    return {miss:/缺键/.test(off), ch:/通道 1/.test(off),
            offSoft:/按通道触发/.test(off), onSoft:/会补键位/.test(on),
            stateTxt:(document.getElementById('autofillState')||{}).textContent||''};
  })()`);
  ok(!chips.miss && chips.ch, '右侧清单：显示「通道 1」而不是「缺键」 → ' + JSON.stringify(chips), chips);
  ok(chips.offSoft, '开关关着 → 右侧说「按通道触发」（不用多按一个键）', chips);
  ok(chips.onSoft, '打开开关 → 右侧改成「会补键位」', chips);
  ok(/关：|开：/.test(chips.stateTxt), '开关旁边有状态提示 → ' + chips.stateTxt, chips.stateTxt);

  /* ---------- 2. 点那个蓝标 → 类型改成「按通道切换」 ---------- */
  const conv = await page.evaluate(`(()=>{
    window.__msgs=[];
    window.confirm=(m)=>{window.__msgs.push(m);return true;};   // 这一步要「同意」
    const r=channelToType(0);
    const out={ok:r, sw:S.rows[0].switch, m:window.__msgs[0]||'',
            tag:document.querySelectorAll('#tbody .chantag').length};
    window.confirm=(m)=>{window.__msgs.push(m);return false;};  // 其余步骤继续「取消」
    return out;
  })()`);
  ok(conv.ok === true && conv.sw === 'ch', '点「通道 N」标 → 触发方式改成按通道切换', conv);
  ok(/通道/.test(conv.m) && /键位/.test(conv.m), '改之前先问一句（说清会补键位） → ' + conv.m.slice(0, 40), conv);
  ok(conv.tag === 2, '改完那一行不再挂「通道」标 → ' + conv.tag, conv.tag);

  /* ---------- 3. 真什么都没填 → 还是要拦，并且点名缺什么 ---------- */
  const a = await page.evaluate(`(()=>{__probe([{switch:'ks'},{switch:'ks'},{switch:'ks'}]);return __gen();})()`);
  ok(/有 3 行还触发不了/.test(a) && /缺键/.test(a), '三行都没填 → 拦下来并点名「缺键」', a);
  ok(/触发不了/.test(a) && /键位 \/ 通道 \/ CC/.test(a), '说明是按部件说的（键位/通道/CC 一个都没有）', a);

  /* ---------- 4. 各类型按自己缺的部件说话 ---------- */
  const b = await page.evaluate(`(()=>{__probe([{switch:'ch'},{switch:'ch'}]);return __gen();})()`);
  ok(/缺通道/.test(b) && !/缺键/.test(b), '按通道切换缺通道 → 只报「缺通道」', b);
  const c = await page.evaluate(`(()=>{__probe([{switch:'cc',cc_num:4},{switch:'cc',cc_num:4}]);return __gen();})()`);
  ok(/CC 值没填/.test(c) && /CC4=0/.test(c), 'CC 行缺值 → 说清会发 CC4=0', c);
  const d = await page.evaluate(`(()=>{__probe([{switch:'none'},{switch:'none'}]);return __gen();})()`);
  ok(d === '', '常驻行不催（永远生效）', d);

  /* ---------- 5. 通道填了、类型也对 → 安静通过 ---------- */
  const f = await page.evaluate(`(()=>{__probe([{switch:'ch',channel:1},{switch:'ch',channel:2}]);
    return __gen();})()`);
  ok(f === '', '按通道切换且通道填好 → 不弹窗', f);

  /* ---------- 6. 提示不拦：只有提示时给 toast，不弹 confirm ---------- */
  const toastMsg = await page.evaluate(`(()=>{
    __probe([{switch:'ks',channel:2}]);           // 只有通道、键位空
    window.__msgs=[];
    const realToast=window.toast;let got='';
    window.toast=(m)=>{got=m;};
    document.getElementById('genBtn').click();
    return {confirmWin:window.__msgs.length, toast:got};
  })()`);
  ok(toastMsg.confirmWin === 0, '不弹 confirm（不拦）', toastMsg);
  ok(/只有通道|补一个键位/.test(toastMsg.toast || ''), '用 toast 说明情况 → ' + toastMsg.toast, toastMsg);

  /* ---------- 7. 产物核对：开关**关着**（默认）时空键位真的不补 ---------- */
  const mkRows = `
    const rows=[
      Object.assign(blankRow(),{name:'按键切换空键',switch:'ks',note:null,channel:3}),
      Object.assign(blankRow(),{name:'纯通道',switch:'ch',channel:3}),
      Object.assign(blankRow(),{name:'按键带键',switch:'ks',note:40,channel:3})];`;
  const gen = await page.evaluate(`(async()=>{
    ${mkRows}
    const res=await api('/api/generate','POST',{rows:rows,map_name:'审核口径检查',
      brand:'kontakt',source:'smoke',start_key:24,autofill:false,
      out_dir:${JSON.stringify(TMP)},overwrite:true});
    return {path:res.map,count:res.count};
  })()`);
  const xml = require('fs').readFileSync(gen.path.replace(/\\/g, '/'), 'utf8');
  const slots = xml.split('<obj class="PSoundSlot"').slice(1);
  ok(slots.length === 3, '生成 3 个槽位', slots.length);
  const slotOf = (nm) => slots.find(s => s.indexOf(nm) >= 0) || '';
  const one = (s, k) => {
    const m = new RegExp('name="' + k + '" value="(-?[0-9]+)"').exec(s);
    return m ? +m[1] : null;
  };
  const s1 = slotOf('按键切换空键'), s2 = slotOf('纯通道'), s3 = slotOf('按键带键');
  ok(one(s1, 'key') === -1 && !/POutputEvent/.test(s1),
     '开关关着 + 空键位 → 不补键：key=-1 且不发 NoteOn（通道说了算） → key=' + one(s1, 'key'), one(s1, 'key'));
  ok(one(s2, 'key') === -1 && !/POutputEvent/.test(s2),
     '按通道切换 + 通道 → key=-1 且不发 NoteOn（真正的纯通道触发）', one(s2, 'key'));
  ok(one(s3, 'key') === 40 && /POutputEvent/.test(s3),
     '按键切换 + 有键位 → key=40 + NoteOn（手填的永远不动）', one(s3, 'key'));
  ok(one(s1, 'channel') === 2 && one(s2, 'channel') === 2,
     '三种填法的通道都要写进去（3 → 0-based 2）', [one(s1, 'channel'), one(s2, 'channel')]);

  /* ---------- 8. 打开「自动补触发键」→ 只有空键位那行被补 ---------- */
  const gen2 = await page.evaluate(`(async()=>{
    ${mkRows}
    const res=await api('/api/generate','POST',{rows:rows,map_name:'审核口径检查补键',
      brand:'kontakt',source:'smoke',start_key:24,autofill:true,
      out_dir:${JSON.stringify(TMP)},overwrite:true});
    return {path:res.map,count:res.count,warn:(res.warnings||[]).join(' | ')};
  })()`);
  const xml2 = require('fs').readFileSync(gen2.path.replace(/\\/g, '/'), 'utf8');
  const slots2 = xml2.split('<obj class="PSoundSlot"').slice(1);
  const s2_1 = slots2.find(s => s.indexOf('按键切换空键') >= 0) || '';
  const s2_3 = slots2.find(s => s.indexOf('按键带键') >= 0) || '';
  ok(one(s2_1, 'key') === 24 && /POutputEvent/.test(s2_1),
     '打开开关 + 空键位 → 补成 key=24 并发 NoteOn（等于多按一个键） → key=' + one(s2_1, 'key'), one(s2_1, 'key'));
  ok(one(s2_3, 'key') === 40, '打开开关也不会动已经填好的键位（还是 40）', one(s2_3, 'key'));

  /* ---------- 9. 界面上那个开关真的接进了生成请求 ---------- */
  // 拦下 /api/generate 看它带没带 autofill（返回一个假错误就停下，不真写文件）
  const wire = await page.evaluate(`(async()=>{
    __probe([{switch:'ks',note:24},{switch:'ks',note:26}]);   // 都填好，不会弹 confirm
    const el=document.getElementById('autofill');
    const before=el.checked;
    const real=window.api, seen=[];
    window.api=async(p,m,b)=>{if(p==='/api/generate')seen.push(!!(b&&b.autofill));
                              return {error:'__stub__'};};
    el.checked=true;  paintAutoFill(); document.getElementById('genBtn').click();
    await new Promise(r=>setTimeout(r,60));
    el.checked=false; paintAutoFill(); document.getElementById('genBtn').click();
    await new Promise(r=>setTimeout(r,60));
    window.api=real;
    el.checked=before; paintAutoFill();
    return seen;
  })()`);
  ok(wire.length === 2 && wire[0] === true && wire[1] === false,
     '开关勾上 → 请求带 autofill=true；取消 → 带 false → ' + JSON.stringify(wire), wire);
};
