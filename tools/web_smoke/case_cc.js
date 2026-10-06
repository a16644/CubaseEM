/* CC 控制器 / 通道的**专用输入框** + 表格列宽可拖（这一轮改的规矩）：

   ① 触发器那一格按触发方式换控件：ks/ks2 → 音名框；ch → 通道号框；
      ks+ch → 键位 + 通道；cc → CC 号框 + CC 值框。**不再靠正则解析字符串**。
      （用户报障：CC 行要在触发键框里打「CC4=100」，少打一个 = 就静默丢掉 →
       界面上看就是「写不上 CC 控制器」）
   ② 落值规则：只写数字也算（CC 号 / 通道号），粘「CC7=8」自动拆成两格，
      通道夹在 1–16、CC 夹在 0–127。
   ③ 列宽能拖（表头右边缘），每列有最低宽度；蓝标 / 灰标换行而不是盖住输入框。
   ④ 列宽存进 settings.colw，刷新还在；「列宽复位」回到默认。
   全走真实键鼠事件。 */
module.exports = async (page, ok, send) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  await page.nav(APP + '/?demo=1');
  const wait = ms => new Promise(s => setTimeout(s, ms));
  // 窗口放大到能装下整张表：坐标点在视口外是点不到的（会被静默吞掉）
  await send('Emulation.setDeviceMetricsOverride',
    {width: 1500, height: 1000, deviceScaleFactor: 1, mobile: false});
  await wait(300);
  /* 取坐标前先滚到视野里，再重新量 —— 表格框自己有纵向滚动条，
     不滚动的话原点可能在可视区外面，鼠标事件就落空了。 */
  const box = async sel => {
    const has = await page.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(sel)});
      if(!e)return false;e.scrollIntoView({block:'center',inline:'center'});return true;})()`);
    if (!has) return null;
    await wait(120);
    return page.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(sel)});
      const r=e.getBoundingClientRect();
      return {x:r.left+r.width/2,y:r.top+r.height/2,l:r.left,r:r.right,t:r.top,b:r.bottom,
              w:r.width,h:r.height};})()`);
  };
  const mouse = async (x, y, type, buttons) => send('Input.dispatchMouseEvent',
    {type, x, y, button: 'left', clickCount: 1, buttons});
  const clickAt = async sel => {
    const c = await box(sel);
    if (!c) throw new Error('点不到 ' + sel);
    await mouse(c.x, c.y, 'mousePressed', 1);
    await mouse(c.x, c.y, 'mouseReleased', 0);
    await wait(150);
    return c;
  };
  const typeInto = async (sel, text) => {
    await clickAt(sel);
    await send('Input.insertText', {text});
    await wait(80);
  };
  /* 失焦 = 点表格外面一块空地方（真鼠标）。change 事件就是这么来的。 */
  const blur = async () => { await clickAt('#rowcount'); await wait(300); };
  const setSwitch = async (i, v) => page.evaluate(`(()=>{
    const s=document.querySelector('#tbody tr[data-r="${i}"] select[data-f="switch"]');
    s.value=${JSON.stringify(v)};s.dispatchEvent(new Event('change',{bubbles:true}));
    return S.rows[${i}].switch;})()`);
  const reset = async (n) => page.evaluate(`(()=>{
    S.rows=[];for(let i=0;i<${n};i++)S.rows.push(blankRow());
    S.rows.forEach((r,i)=>{r.name='r'+(i+1);});
    renderTable();return S.rows.length;})()`);

  /* ================= ① 按触发方式换控件 ================= */
  await reset(1);
  const forms = {};
  for (const sw of ['ks', 'ks2', 'ch', 'ks+ch', 'cc', 'none']) {
    await setSwitch(0, sw);
    forms[sw] = await page.evaluate(`(()=>{
      const cell=document.querySelector('#tbody tr[data-r="0"] td:nth-child(7)');
      return {fields:Array.from(cell.querySelectorAll('[data-f]')).map(e=>e.dataset.f),
              label:cell.textContent.trim()};})()`);
  }
  ok(JSON.stringify(forms.ks.fields) === JSON.stringify(['note']),
     '按键切换 → 只有一个音名框 → ' + JSON.stringify(forms.ks), forms.ks);
  ok(JSON.stringify(forms.ks2.fields) === JSON.stringify(['note', 'note2']),
     '双键齐按 → 键1 + 键2 两个框 → ' + JSON.stringify(forms.ks2), forms.ks2);
  ok(JSON.stringify(forms.ch.fields) === JSON.stringify(['channel']),
     '按通道切换 → 只有通道号框（不再借触发键那格）→ ' + JSON.stringify(forms.ch), forms.ch);
  ok(JSON.stringify(forms['ks+ch'].fields) === JSON.stringify(['note', 'channel']),
     '通道＋按键 → 键位框 + 通道框 → ' + JSON.stringify(forms['ks+ch']), forms['ks+ch']);
  ok(JSON.stringify(forms.cc.fields) === JSON.stringify(['cc_num', 'cc_val']),
     'CC 控制器 → CC 号框 + CC 值框（专用输入）→ ' + JSON.stringify(forms.cc), forms.cc);
  ok(forms.cc.label.indexOf('CC') >= 0 && forms.cc.label.indexOf('=') >= 0,
     'CC 那格看得出是「CC 号 = 值」→ ' + forms.cc.label, forms.cc.label);

  /* ================= ② 真打字：专用框收得住值 ================= */
  await reset(2);
  await setSwitch(0, 'cc');
  await typeInto('#tbody tr[data-r="0"] [data-f="cc_num"]', '4');
  await typeInto('#tbody tr[data-r="0"] [data-f="cc_val"]', '100');
  await blur();
  let cc = await page.evaluate('({num:S.rows[0].cc_num,val:S.rows[0].cc_val})');
  ok(cc.num === 4 && cc.val === 100, 'CC 号 / CC 值各填各的 → ' + JSON.stringify(cc), cc);
  const shown = await page.evaluate(`(()=>({
    num:document.querySelector('#tbody tr[data-r="0"] [data-f="cc_num"]').value,
    val:document.querySelector('#tbody tr[data-r="0"] [data-f="cc_val"]').value}))()`);
  ok(shown.num === '4' && shown.val === '100',
     '重画之后两个框里还看得见 → ' + JSON.stringify(shown), shown);

  // 只写号不写值：号要留住（以前整行都被丢掉）
  await reset(1);
  await setSwitch(0, 'cc');
  await typeInto('#tbody tr[data-r="0"] [data-f="cc_num"]', 'CC64');
  await blur();
  cc = await page.evaluate('S.rows[0].cc_num');
  ok(cc === 64, '只写「CC64」也认下 CC 号 → ' + cc, cc);

  // 粘字符串自动拆
  await reset(1);
  await setSwitch(0, 'cc');
  await typeInto('#tbody tr[data-r="0"] [data-f="cc_num"]', 'CC7=8');
  await blur();
  cc = await page.evaluate('({n:S.rows[0].cc_num,v:S.rows[0].cc_val})');
  ok(cc.n === 7 && cc.v === 8, '粘「CC7=8」自动拆成号 7 / 值 8 → ' + JSON.stringify(cc), cc);

  // 越界夹住
  await reset(1);
  await setSwitch(0, 'cc');
  await typeInto('#tbody tr[data-r="0"] [data-f="cc_val"]', '300');
  await blur();
  cc = await page.evaluate('S.rows[0].cc_val');
  ok(cc === 127, 'CC 值超 127 被夹到 127 → ' + cc, cc);

  // 通道：只收 1–16，且是**自己那格**
  await reset(2);
  await setSwitch(0, 'ch');
  await typeInto('#tbody tr[data-r="0"] [data-f="channel"]', '9');
  await blur();
  let ch = await page.evaluate('S.rows[0].channel');
  ok(ch === 9, '通道行填 9 → channel=9 → ' + ch, ch);
  await typeInto('#tbody tr[data-r="0"] [data-f="channel"]', '99');
  await blur();
  ch = await page.evaluate('S.rows[0].channel');
  ok(ch === 16, '通道超 16 被夹到 16 → ' + ch, ch);

  // 音名框照旧（没被这次改动弄坏）
  await reset(1);
  await setSwitch(0, 'ks');
  await typeInto('#tbody tr[data-r="0"] [data-f="note"]', 'C0');
  await blur();
  const n0 = await page.evaluate('S.rows[0].note');
  ok(n0 === 24, '按键行填 C0 → 24（Cubase 叫法）→ ' + n0, n0);

  // 双键齐按：两个键位框都要能填，方向键也能从键1走到键2
  await reset(1);
  await setSwitch(0, 'ks2');
  await typeInto('#tbody tr[data-r="0"] [data-f="note"]', 'C0');
  await typeInto('#tbody tr[data-r="0"] [data-f="note2"]', 'D0');
  await blur();
  const two = await page.evaluate('({a:S.rows[0].note,b:S.rows[0].note2})');
  ok(two.a === 24 && two.b === 26, '双键齐按：键1 / 键2 各填各的 → ' + JSON.stringify(two), two);
  const navN2 = await page.evaluate(`(()=>{
    const k1=document.querySelector('#tbody tr[data-r="0"] [data-f="note"]');
    k1.focus(); k1.select();      // 刚跳过来的格子是整段选中的，这时方向键才是「换格」
    k1.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
    const a=document.activeElement;
    return a?a.dataset.f:null;})()`);
  ok(navN2 === 'note2', '方向键能从键1走到键2（NAVK 里有 note2）→ ' + navN2, navN2);

  /* ================= ③ 标签不盖住输入框 ================= */
  await reset(1);
  const cover = await page.evaluate(`(()=>{
    S.rows[0].switch='ks'; S.rows[0].channel=3;      // 类型=按键、只填了通道 → 出蓝标
    renderTable();
    const inp=document.querySelector('#tbody tr[data-r="0"] [data-f="note"]');
    const tag=document.querySelector('#tbody tr[data-r="0"] .chantag');
    if(!tag)return {noTag:true};
    const a=inp.getBoundingClientRect(),b=tag.getBoundingClientRect();
    const overlap=!(b.left>=a.right-0.5||b.right<=a.left+0.5||b.top>=a.bottom-0.5||b.bottom<=a.top+0.5);
    return {w:Math.round(a.width),tagW:Math.round(b.width),overlap:overlap};})()`);
  ok(cover.w >= 40 && !cover.overlap,
     '蓝标「通道 3」不再盖住输入框（输入框宽 ' + cover.w + 'px）→ ' + JSON.stringify(cover), cover);

  /* ================= ④ 列宽：拖 / 最低宽度 / 复位 ================= */
  const colw0 = await page.evaluate(`(()=>{
    resetColw();
    return {store:S.colw.slice(),touched:S.colwTouched,
            px:Array.from(document.querySelectorAll('#colgroup col')).map(c=>c.style.width)};})()`);
  ok(colw0.store.length === 10 && colw0.px.length === 10,
     '10 列的列宽都在管 → ' + JSON.stringify(colw0.px), colw0);

  // 真拖第 7 列（触发器）的把手
  const grip = await box('#tbl thead th:nth-child(7) .colgrip');
  ok(grip && grip.w > 0, '表头右边缘有拖拽把手 → ' + JSON.stringify(grip), grip);
  await mouse(grip.x, grip.y, 'mousePressed', 1);
  await mouse(grip.x + 60, grip.y, 'mouseMoved', 1);
  await wait(80);
  await mouse(grip.x + 60, grip.y, 'mouseReleased', 0);
  await wait(350);
  const afterDrag = await page.evaluate(`(()=>({w:S.colw[6],px:document.querySelector(
    '#colgroup col:nth-child(7)').style.width}))()`);
  ok(afterDrag.w > colw0.store[6],
     '拖宽触发器列 ' + colw0.store[6] + ' → ' + afterDrag.w, afterDrag);

  // 往左拖过头：必须被最低宽度拦住（把手位置变了，要重新量）
  const grip2 = await box('#tbl thead th:nth-child(7) .colgrip');
  await mouse(grip2.x, grip2.y, 'mousePressed', 1);
  await mouse(grip2.x - 500, grip2.y, 'mouseMoved', 1);
  await wait(80);
  await mouse(grip2.x - 500, grip2.y, 'mouseReleased', 0);
  await wait(350);
  const minW = await page.evaluate(`(()=>({w:S.colw[6],min:COL_MIN[6]}))()`);
  ok(minW.w === minW.min, '拖过头被最低宽度拦在 ' + minW.min + 'px → ' + JSON.stringify(minW), minW);

  const stillVisible = await page.evaluate(`(()=>{
    const cell=document.querySelector('#tbody tr[data-r="0"] td:nth-child(7)');
    const inp=cell.querySelector('[data-f="note"]')||cell.querySelector('[data-f]');
    const r=inp.getBoundingClientRect();
    const box=cell.getBoundingClientRect();
    return {inpW:Math.round(r.width),cellW:Math.round(box.width),
            inside:r.left>=box.left-1&&r.right<=box.right+1};})()`);
  ok(stillVisible.inpW >= 40 && stillVisible.inside,
     '列拖到最窄时输入框依然完整可见 → ' + JSON.stringify(stillVisible), stillVisible);

  // 存盘 + 复位
  const saved = await page.evaluate(`(async()=>{const r=await api('/api/state');
    return r.settings.colw||'';})()`);
  ok(String(saved).split(',').length === 10,
     '列宽存进了 settings.colw → ' + saved, saved);
  const back = await page.evaluate(`(()=>{resetColw();return {w:S.colw[6],def:COL_DEF[6]};})()`);
  ok(back.w === back.def, '「列宽复位」把触发器列还原成 ' + back.def, back);
};
