/* 编辑相关的几条规矩：
   ① 没写名字的行一律叫「插槽N」，且**所有插槽名字必须互不相同**
      （Cubase 里认条目全靠名字，重名 = 两条长得一模一样，回头分不出谁是谁）。
   ② 生成前先看目标文件夹有没有同名文件：有就只回报清单、不写，等界面问过再说。
   ③ 键盘能在表格里挪编辑位：方向键在整行里走，Tab 去下一行同一列，
      落到按钮上画虚框表示「选中」（不是编辑）。
   这里全走真实事件（真 dispatch 一个 keydown），不用函数级 mock。 */
module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  const TMP = (process.env.SMOKE_TMP || '').replace(/\\/g, '/');
  await page.nav(APP + '/?demo=1');
  const fs = require('fs');

  /* ================= ① 默认名 + 唯一化 ================= */
  const uniq = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.name='';r.switch='ks';r.note=24+i;});
    S.rows[2].name='滑音'; S.rows[3].name='滑音';   // 故意撞名
    const changed=uniqueRowNames();
    return {names:S.rows.map(r=>r.name), changed:changed};
  })()`);
  ok(uniq.names[0] === '插槽1' && uniq.names[1] === '插槽2',
     '空名 -> 插槽1 / 插槽2 → ' + JSON.stringify(uniq.names), uniq.names);
  ok(uniq.names[2] === '滑音' && uniq.names[3] === '滑音 (2)',
     '撞名的第二个自动加后缀 → ' + JSON.stringify(uniq.names), uniq.names);
  ok(new Set(uniq.names).size === uniq.names.length,
     '所有插槽名字互不相同（' + new Set(uniq.names).size + '/' + uniq.names.length + '）', uniq.names);

  /* ================= ② 生成 + 同名文件确认 ================= */
  const gen = await page.evaluate(`(async()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.name='';r.switch='ks';r.note=24+i;});
    S.rows[2].name='重名'; S.rows[0].name='重名';      // 后端也得能去重
    // 名字带时间戳：临时目录里可能留着上一轮跑出来的同名文件，
    // 那样"首次生成"也会被同名检查挡住，测的就不是想测的东西了。
    const body={rows:S.rows,map_name:'编辑规则检查'+Date.now(),brand:'kontakt',source:'smoke',
      start_key:24,octave_offset:0,out_dir:${JSON.stringify(TMP)}};
    const r1=await api('/api/generate','POST',body);
    // 同一个名字再生成一次 -> 应当被同名文件挡住，什么都不写
    const r2=await api('/api/generate','POST',body);
    // 带上 overwrite 才真的写
    const r3=await api('/api/generate','POST',Object.assign({},body,{overwrite:true}));
    return {r1:{ok:r1.ok,count:r1.count,csv:r1.csv,renamed:r1.renamed},
            r2:{need:r2.need_confirm,existing:r2.existing,ok:r2.ok},
            r3:{ok:r3.ok,count:r3.count}};
  })()`);
  ok(gen.r1.ok === true && gen.r1.count === 3,
     '首次生成成功（3 条）→ ' + JSON.stringify(gen.r1), gen.r1);
  ok(!!gen.r2.need && (gen.r2.existing || []).length >= 1,
     '第二次生成撞同名文件 -> 只回报清单不写盘 → ' + JSON.stringify(gen.r2.existing), gen.r2);
  ok(!gen.r2.ok, '撞同名文件时没有真的写文件', gen.r2);
  ok(gen.r3.ok === true, '带 overwrite 重发 -> 生成成功', gen.r3);

  const csv = fs.readFileSync(gen.r1.csv.replace(/\\/g, '/'), 'utf8');
  const names = csv.split(/\r?\n/).filter(Boolean).slice(1).map(l => l.split(',')[1]);
  ok(new Set(names).size === names.length && names.indexOf('重名 (2)') >= 0,
     '导出 CSV 里的名字互不重复 → ' + names.join('|'), names);

  /* ================= ③ 键盘导航 ================= */
  const nav = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.name='技法'+(i+1);r.switch='ks';r.note=24+i;});
    renderTable();
    const key=(el,k,alt)=>el.dispatchEvent(new KeyboardEvent('keydown',
      {key:k,altKey:!!alt,bubbles:true,cancelable:true}));
    const at=()=>{const a=document.activeElement;
      const tr=a&&a.closest?a.closest('tr'):null;
      return {r:tr?tr.dataset.r:null,k:a&&a.dataset?a.dataset.k:null,
              vf:!!(a&&a.classList&&a.classList.contains('kfocus'))};};
    const out={};
    const first=document.querySelector('#tbody tr[data-r="0"] [data-k="name"]');
    first.focus(); out.start=at();
    key(document.activeElement,'Tab');            out.afterTab=at();
    key(document.activeElement,'ArrowDown');      out.afterDown=at();
    key(document.activeElement,'ArrowRight');     out.afterRight=at();
    // 右一格落在「类型」下拉框上：下拉框的方向键是选值用的，
    // 所以这里必须按 Alt 才挪得动 —— 顺便把这条规则钉住。
    key(document.activeElement,'ArrowLeft');      out.leftOnSelect=at();
    key(document.activeElement,'ArrowLeft',true); out.afterLeft=at();
    // 走到按钮上：颜色 -> 保存，按钮要画虚框（vf=true）而不是进入编辑
    const col=document.querySelector('#tbody tr[data-r="0"] [data-k="color"]');
    col.focus(); key(col,'ArrowRight');           out.toButton=at();
    // 下拉框：方向键留给「选值」，只有 Alt+方向键才挪位置
    const sel=document.querySelector('#tbody tr[data-r="0"] [data-k="switch"]');
    sel.focus();
    key(sel,'ArrowDown');                         out.selPlain=at();
    key(sel,'ArrowDown',true);                    out.selAlt=at();
    return out;
  })()`);
  ok(nav.start.r === '0' && nav.start.k === 'name',
     '起点 = 第 1 行的技法名 → ' + JSON.stringify(nav.start), nav.start);
  ok(nav.afterTab.r === '1' && nav.afterTab.k === 'name',
     'Tab -> 下一行同一列（第 2 行技法名）→ ' + JSON.stringify(nav.afterTab), nav.afterTab);
  ok(nav.afterDown.r === '2' && nav.afterDown.k === 'name',
     'ArrowDown -> 再下一行同一列 → ' + JSON.stringify(nav.afterDown), nav.afterDown);
  ok(nav.afterRight.k === 'atype',
     'ArrowRight -> 本行右一格（类型）→ ' + JSON.stringify(nav.afterRight), nav.afterRight);
  ok(nav.leftOnSelect.k === 'atype',
     '停在下拉框上时方向键不挪位（留给选值）→ ' + JSON.stringify(nav.leftOnSelect), nav.leftOnSelect);
  ok(nav.afterLeft.r === '2' && nav.afterLeft.k === 'name',
     'Alt+ArrowLeft -> 回到技法名 → ' + JSON.stringify(nav.afterLeft), nav.afterLeft);
  ok(nav.toButton.k === 'save' && nav.toButton.vf === true,
     '走到按钮上 -> 加虚框选中态（不进编辑）→ ' + JSON.stringify(nav.toButton), nav.toButton);
  ok(nav.selPlain.r === '0' && nav.selPlain.k === 'switch',
     '下拉框上按方向键不挪位（留给选值）→ ' + JSON.stringify(nav.selPlain), nav.selPlain);
  ok(nav.selAlt.r === '1' && nav.selAlt.k === 'switch',
     '下拉框上 Alt+方向键才挪位 → ' + JSON.stringify(nav.selAlt), nav.selAlt);

  /* ================= MIDI 录键（无真设备，只验接线） ================= */
  const midi = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow()];
    S.rows.forEach(r=>{r.switch='ks';r.note=null;});
    renderTable();
    S.actIdx=0;
    midiToRow(60);                       // 假装琴键送进来一个 C3
    return {n0:S.rows[0].note, act:S.actIdx, nm:noteName(S.rows[0].note)};
  })()`);
  ok(midi.n0 === 60, 'MIDI 键位写进当前行 → note=' + midi.n0 + '（' + midi.nm + '）', midi);
  ok(midi.act === 1, '填完自动跳到下一行（方便连录）→ 当前行 ' + midi.act, midi);
};
