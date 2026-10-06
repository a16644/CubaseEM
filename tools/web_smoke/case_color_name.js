module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  await page.nav(APP + '/?demo=1');

  /* ---------- 清空 & 批量删除 ---------- */
  const before = await page.evaluate('S.rows.length');
  ok(before === 6, '示例 6 行 → ' + before, before);

  // 1) 清空按钮
  const cleared = await page.evaluate(`(()=>{
    document.getElementById('clearRow').click();
    return {rows:S.rows.length, tbody:document.querySelectorAll('#tbody tr').length};
  })()`);
  ok(cleared.rows === 0 && cleared.tbody === 0, '「清空」应清掉全部 → ' + JSON.stringify(cleared), cleared);

  // 2) 批量删：先勾选再删
  const bd = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];renderTable();
    [0,2].forEach(i=>S.sel.add(i));syncSelUI();
    const shown=document.getElementById('batchbar').classList.contains('on');
    document.getElementById('batchDel').click();
    return {shown:shown, rows:S.rows.length};
  })()`);
  ok(bd.shown, '勾选后批量栏应出现', bd);
  ok(bd.rows === 1, '批量删 2 行后应剩 1 行 → ' + bd.rows, bd);

  // 3) 全选框
  const sa = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];renderTable();
    const all=document.getElementById('selAll');
    all.checked=true; all.dispatchEvent(new Event('change',{bubbles:true}));
    return {sel:Array.from(S.sel).length, cnt:document.getElementById('selCount').textContent};
  })()`);
  ok(sa.sel === 3 && sa.cnt === '3', '全选框应勾住全部 → ' + JSON.stringify(sa), sa);

  // 4) 复选列能不能真的点中（用 CDP 真实鼠标事件，不用 elementFromPoint）
  const checkReal = async () => {
    await page.evaluate(`(()=>{
      S.rows=[blankRow(),blankRow()];renderTable();
      const cb=document.querySelector('#tbody [data-si]');
      cb.scrollIntoView({block:'center'});
      return 0;})()`);
    await new Promise(r => setTimeout(r, 120));
    const box = await page.evaluate(`(()=>{
      const cb=document.querySelector('#tbody [data-si]');
      const r=cb.getBoundingClientRect();
      return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2),
              w:Math.round(r.width), h:Math.round(r.height)};})()`);
    for (const type of ['mousePressed', 'mouseReleased']) {
      await page.send('Input.dispatchMouseEvent',
        { type, x: box.x, y: box.y, button: 'left', clickCount: 1 });
    }
    await new Promise(r => setTimeout(r, 200));
    return { box, sel: await page.evaluate('Array.from(S.sel).length') };
  };
  const ck = await checkReal();
  ok(ck.box.w > 6 && ck.box.h > 6 && ck.sel === 1,
     '勾选框能真实点中 → ' + JSON.stringify(ck), ck);

  /* ---------- 颜色 ---------- */
  // 5) 加行默认跟随上一行颜色
  const col = await page.evaluate(`(()=>{
    S.rows=[];
    S.rows.push(Object.assign(blankRow(),{name:'a',color:5,note:24}));
    S.rows.push(Object.assign(blankRow(),{name:'b',color:9,note:25}));
    renderTable(); addRow();
    return {last:S.rows[1].color, neww:S.rows[2].color};
  })()`);
  ok(col.neww === col.last, '新行颜色应跟随上一行 → ' + JSON.stringify(col), col);

  // 6) 没有上一行时用默认色
  const col0 = await page.evaluate(`(()=>{
    S.rows=[];renderTable();addRow();
    return S.rows[0].color;
  })()`);
  ok(col0 === 1, '空表第一行用默认色 1 → ' + col0, col0);

  /* ---------- 默认技法名 ---------- */
  // 7) 不填默认名时也要有个能用的名字，不能空白
  const nm = await page.evaluate(`(()=>{
    document.getElementById('defname').value='';
    S.rows=[];renderTable();addRow();addRow();
    return S.rows.map(r=>r.name);
  })()`);
  ok(nm[0] && nm[0].trim() !== '' && nm[1] && nm[1].trim() !== '',
     '默认技法名为空时也要给出名字 → ' + JSON.stringify(nm), nm);

  // 8) 生成时也不能是空名
  const gen = await page.evaluate(`(async()=>{
    document.getElementById('defname').value='';
    S.rows=[];renderTable();addRow();addRow();
    S.rows.forEach((r,i)=>{r.note=24+i;});
    const res=await api('/api/generate','POST',{rows:S.rows,map_name:'默认名检查',
      brand:'kontakt',source:'smoke',start_key:24,out_dir:S.outDefault,overwrite:true});
    return {names:S.rows.map(r=>r.name), count:res.count};
  })()`);
  ok(gen.names.every(n => n && n.trim() !== ''),
     '生成前每行都得有名字 → ' + JSON.stringify(gen.names), gen);

  /* ---------- 颜色模块：按组配色 / 递增 / 递减 / 循环 ---------- */
  // 造一张多类别表：普通 Art.1 / 普通 Art.2 / 组合(1+2) / 组合(1+3)
  const mk = `(()=>{
    const a=Object.assign(blankRow(),{name:'g1',group:0,color:1});
    const b=Object.assign(blankRow(),{name:'g2',group:1,color:1});
    const c=Object.assign(blankRow(),{name:'c12',group:0,color:1,combo:true,
      conditions:[{group:0,description:'x',note:24},{group:1,description:'y',note:26}]});
    const d=Object.assign(blankRow(),{name:'c13',group:0,color:1,combo:true,
      conditions:[{group:0,description:'x',note:24},{group:2,description:'z',note:28}]});
    const e=Object.assign(blankRow(),{name:'g1b',group:0,color:1});
    S.rows=[a,b,c,d,e];renderTable();
    S.sel=new Set([0,1,2,3,4]);syncSelUI();return S.rows.length;})()`;
  await page.evaluate(mk);

  // 按组配色：同类别必须同色，不同类别必须不同色
  const grp = await page.evaluate(`(()=>{
    const idx=selArr().slice();
    const n=assignGroupColors(idx);
    return {n:n, colors:S.rows.map(r=>r.color),
            keys:S.rows.map(r=>rowClassKey(r))};
  })()`);
  ok(grp.colors[0] === grp.colors[4],
     '同类别（Art.1）拿同色 → ' + JSON.stringify(grp.colors), grp);
  ok(grp.colors[1] !== grp.colors[0], 'Art.2 与 Art.1 不同色 → ' + JSON.stringify(grp.colors), grp);
  ok(grp.colors[2] !== grp.colors[3],
     'Art.1+Art.2 与 Art.1+Art.3 不同色 → ' + JSON.stringify(grp.colors), grp);
  ok(grp.colors[2] !== grp.colors[0], '组合与普通行不同色', grp);
  ok(grp.n === 4, '一共 4 个类别 → ' + grp.n, grp);

  // 递增 / 递减 / 循环 —— 走真实的弹窗路径（cmGo），别在用例里自己重算
  const seq = await page.evaluate(`(()=>{
    const reset=(base)=>{
      S.rows=[blankRow(),blankRow(),blankRow(),blankRow()];
      S.rows.forEach(r=>{r.color=base;r.group=0;});renderTable();
      S.sel=new Set([0,1,2,3]);syncSelUI();
    };
    const run=(mode,base)=>{
      reset(base);
      document.getElementById('batchColorBtn').click();
      const m=document.getElementById('cmMode');
      m.value=mode;m.dispatchEvent(new Event('change',{bubbles:true}));
      cmGo();
      return S.rows.map(r=>r.color);
    };
    const inc=run('inc',3);
    const dec=run('inc2',3);
    const cyc=run('cycle',3);
    const inc2nd=run('inc',3);   // 再点一次必须得到同样的结果（幂等）
    const inc16=run('inc',15);   // 基准靠边要会绕回
    return {inc,dec,cyc,inc2nd,inc16};
  })()`);
  ok(JSON.stringify(seq.inc) === JSON.stringify([3,4,5,6]),
     '从色号 3 起递增 → ' + seq.inc, seq);
  ok(JSON.stringify(seq.dec) === JSON.stringify([3,2,1,16]),
     '从色号 3 起递减（到 1 绕回 16）→ ' + seq.dec, seq);
  ok(JSON.stringify(seq.cyc) === JSON.stringify([1,2,3,4]),
     '循环取色 → ' + seq.cyc, seq);
  ok(JSON.stringify(seq.inc2nd) === JSON.stringify(seq.inc),
     '连点两次结果一致（基准不跑偏）→ ' + seq.inc2nd, seq);
  ok(JSON.stringify(seq.inc16) === JSON.stringify([15,16,1,2]),
     '从色号 15 起递增会绕回 → ' + seq.inc16, seq);

  // 颜色模块弹窗：打开、切模式、预览能画出来
  await page.evaluate(`(()=>{S.rows=[blankRow(),blankRow()];renderTable();
    S.sel=new Set([0,1]);syncSelUI();document.getElementById('batchColorBtn').click();return 0;})()`);
  const modal = await page.evaluate(`(()=>{
    const m=document.getElementById('cmMode');
    return {disp:getComputedStyle(document.getElementById('modal')).display,
            modes:Array.from(m.options).map(o=>o.textContent),
            pickShown:getComputedStyle(document.getElementById('cmPick')).display};
  })()`);
  ok(modal.disp === 'block' && modal.modes.length === 6,
     '颜色弹窗打开且有 6 种改法 → ' + JSON.stringify(modal.modes), modal);
  ok(modal.pickShown === 'none', '默认模式不需要选色号（跟随规律）', modal);
  const prev = await page.evaluate(`(()=>{
    const m=document.getElementById('cmMode');
    m.value='group'; m.dispatchEvent(new Event('change',{bubbles:true}));
    const n1=document.querySelectorAll('#cmPrev .cmchip').length;
    m.value='fixed'; m.dispatchEvent(new Event('change',{bubbles:true}));
    const pick=document.getElementById('cmPick');
    const opts=Array.from(document.getElementById('cmColor').options).length;
    return {chips:n1, pick:getComputedStyle(pick).display, opts:opts,
            hint:document.getElementById('cmHint').textContent};
  })()`);
  ok(prev.chips === 2, '预览画出了 2 个色块 → ' + prev.chips, prev);
  ok(prev.pick !== 'none' && prev.opts >= 16,
     '「指定一个颜色号」会露出色号下拉，共 ' + prev.opts + ' 个', prev);
  ok(!!prev.hint, '每种改法有说明文字 → ' + prev.hint, prev);
  // 真的套用「指定色号」
  const applied = await page.evaluate(`(()=>{
    const m=document.getElementById('cmMode');
    m.value='fixed'; m.dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('cmColor').value='9';
    cmGo();
    return S.rows.map(r=>r.color);
  })()`);
  ok(JSON.stringify(applied) === JSON.stringify([9,9]),
     '套用「指定色号 9」→ ' + applied, applied);
  await page.evaluate(`closeModal()`);
};

