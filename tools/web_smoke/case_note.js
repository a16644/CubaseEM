/* 触发键的音名换算：界面里打什么，导出就该是什么，而且要和 **Cubase** 的叫法一致。
   Cubase 官方映射（中央 C = C3）：0=C-2、12=C-1、24=C0、36=C1、60=C3。
   曾经的 bug：工具按科学记法算（24 叫 C1），于是「软件里填 C0 →
   导出进 Cubase 显示 C-1」，整整差一个八度。
   这里从「真实输入框 change 事件」走到「生成的 CSV / 对照表」，两头一起钉住。 */
module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  const TMP = (process.env.SMOKE_TMP || '').replace(/\\/g, '/');
  await page.nav(APP + '/?demo=1');
  const fs = require('fs');
  const SEL = '#tbody tr:first-child [data-f="note"]';

  // 造一行空的键位行，然后像用户一样往输入框里打东西、触发 change
  const type = (txt) => page.evaluate(`(()=>{
    S.rows=[blankRow()];S.rows[0].switch='ks';S.rows[0].note=null;
    renderTable();
    const e=document.querySelector(${JSON.stringify(SEL)});
    e.focus();e.value=${JSON.stringify(txt)};
    e.dispatchEvent(new Event('change',{bubbles:true}));
    return {note:S.rows[0].note, shown:document.querySelector(${JSON.stringify(SEL)}).value};
  })()`);

  // Cubase 默认标准下的换算表：[输入, 内部号, 回显]
  const cases = [
    ['c0', 24, 'C0'],      // 小写也要认
    ['C0', 24, 'C0'],
    ['C1', 36, 'C1'],
    ['C3', 60, 'C3'],      // 中央 C = C3（Cubase 的叫法）
    ['C-1', 12, 'C-1'],
    ['C-2', 0, 'C-2'],     // MIDI 0 是 Cubase 的最低音
    ['24', 24, 'C0'],      // 数字直写
    ['C#0', 25, 'C#0'],
  ];
  for (const [txt, want, shown] of cases) {
    const r = await type(txt);
    ok(r.note === want, `输入框打 ${txt} → 内部 ${r.note}（应为 ${want}）`, r);
    ok(r.shown === shown, `输入框打 ${txt} → 回显 ${r.shown}（应为 ${shown}）`, r);
  }

  /* ---------- 全量互逆：所有 128 个音，名字 -> 号 -> 名字 必须回到原样 ---------- */
  const rt = await page.evaluate(`(()=>{
    const bad=[];
    for(let n=0;n<128;n++){ if(parseNote(noteName(n))!==n) bad.push(n); }
    return bad;
  })()`);
  ok(rt.length === 0, '128 个音全部「名字↔号码」互逆（差八度会在这里炸）', rt.slice(0, 5));

  /* ---------- 切到科学记法，两边要一起动 ---------- */
  const sci = await page.evaluate(`(()=>{
    setOctBase(-1);
    const a=[noteName(24),parseNote('C1')];
    setOctBase(0);
    const b=[noteName(24),parseNote('C0')];
    return {sci:a,cub:b};
  })()`);
  ok(sci.sci[0] === 'C1' && sci.sci[1] === 24,
     '科学记法：24 叫 C1、C1 就是 24 → ' + JSON.stringify(sci.sci), sci.sci);
  ok(sci.cub[0] === 'C0' && sci.cub[1] === 24,
     'Cubase 记法：24 叫 C0、C0 就是 24 → ' + JSON.stringify(sci.cub), sci.cub);

  /* ---------- 生成后，导出文件里的音名必须和输入一致 ---------- */
  const gen = await page.evaluate(`(async()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows[0].name='滑音';S.rows[0].switch='ks';S.rows[0].note=24;
    S.rows[1].name='断奏';S.rows[1].switch='ks';S.rows[1].note=36;
    S.rows[2].name='长音';S.rows[2].switch='ks';S.rows[2].note=12;
    renderTable();
    const res=await api('/api/generate','POST',{rows:S.rows,map_name:'音名换算检查',
      brand:'kontakt',source:'smoke',start_key:24,octave_offset:0,
      out_dir:${JSON.stringify(TMP)},overwrite:true});
    return {csv:res.csv,map:res.map,html:res.html,count:res.count};
  })()`);
  ok(gen.count === 3 && !!gen.csv, '生成成功 → ' + JSON.stringify(gen), gen);

  const csv = fs.readFileSync(gen.csv.replace(/\\/g, '/'), 'utf8');
  const lines = csv.split(/\r?\n/).filter(Boolean).slice(1);
  const notes = lines.map(l => l.split(',')[3]);      // 第 4 列 = note
  ok(notes.join('|') === '24|36|12', '导出 CSV 的 note 列 = ' + notes.join('|'), notes);

  // 对照表（HTML）里人看到的那串字
  const html = fs.readFileSync((gen.html || '').replace(/\\/g, '/'), 'utf8');
  const shown = [...html.matchAll(/(\d+) \(([A-G]#?-?\d+)\)/g)].map(m => m[2]);
  ok(shown.join('|') === 'C0|C1|C-1',
     '对照表音名 = ' + shown.join('|') + '（应 C0|C1|C-1）', shown);
  ok(shown.indexOf('C-2') < 0 && shown.filter(x => x === 'C0').length === 1,
     '不能出现「输入 C0 却显示成低八度」的错位 → ' + JSON.stringify(shown), shown);
};
