module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  const TMP = (process.env.SMOKE_TMP || '').replace(/\\/g, '/');
  await page.nav(APP + '/?demo=1');
  const n = await page.evaluate('S.rows.length');
  ok(n >= 3, '示例载入行数 = ' + n, n);

  /* ---------- 1. UI 缩放 ---------- */
  await page.evaluate(`(async()=>{await api('/api/settings','POST',{patch:{zoom:100}});})()`);
  await page.evaluate('paintZoom(100)');
  const z0 = await page.evaluate('S.zoom');
  await page.click('#zoomIn');
  const z1 = await page.evaluate('S.zoom');
  const ztxt = await page.evaluate(`document.getElementById('zoomVal').textContent`);
  const bz = await page.evaluate(`document.body.style.zoom`);
  ok(z1 > z0, `放大一次 ${z0} → ${z1}`, [z0, z1]);
  ok(ztxt === z1 + '%', '顶栏显示 = ' + ztxt, ztxt);
  ok(bz === z1 + '%', 'body.zoom = ' + bz, bz);
  await page.click('#zoomOut');
  const z2 = await page.evaluate('S.zoom');
  ok(z2 === z0, `缩小回到 ${z2}`, [z0, z2]);
  // 存进去后重新拉状态，确认持久化
  const zNow = await page.evaluate(`(async()=>{await api('/api/settings','POST',{patch:{zoom:125}});
    const r=await api('/api/state');return r.zoom;})()`);
  ok(zNow === 125, '缩放已存盘 = ' + zNow, zNow);
  // 越界要被夹住
  const zClamp = await page.evaluate(`(async()=>{
    const a=await api('/api/settings','POST',{patch:{zoom:999}});
    const b=await api('/api/settings','POST',{patch:{zoom:1}});
    return [a.zoom,b.zoom];})()`);
  ok(zClamp[0] === 150 && zClamp[1] === 80, '缩放越界被夹到 150/80 → ' + zClamp, zClamp);
  await page.evaluate(`(async()=>{await api('/api/settings','POST',{patch:{zoom:100}});paintZoom(100);})()`);

  /* ---------- 2. 键位/通道递推预测 ---------- */
  // 造一段：24 空 空 27  → 中间应推 25 / 26
  const pred = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow(),blankRow()];
    S.rows[0].note=24; S.rows[3].note=27;
    renderTable();
    return {v:S.pred.note.values, d:S.pred.note.dirs};
  })()`);
  ok(pred.v[1] === 25 && pred.v[2] === 26, '24 空空 27 → 推 25/26', pred);
  // 递减方向
  const pred2 = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow(),blankRow()];
    S.rows[0].note=27; S.rows[3].note=24;
    renderTable(); return S.pred.note.values;
  })()`);
  ok(pred2[1] === 26 && pred2[2] === 25, '27 空空 24 → 推 26/25', pred2);
  // CC 行必须被跳过
  const pred3 = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    S.rows[0].switch='cc'; S.rows[0].cc_num=4; S.rows[0].cc_val=100;
    S.rows[2].note=36; renderTable();
    return {cc:S.pred.note.values[0], after:S.pred.note.values[1]};
  })()`);
  ok(pred3.cc === undefined, 'CC 行不参与推算（必须手填）', pred3);
  // 通道同理，且封顶 1..16
  const pred4 = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow(),blankRow()];
    S.rows.forEach(r=>r.switch='ch');
    S.rows[0].channel=1; S.rows[3].channel=4;
    renderTable(); return S.pred.channel.values;
  })()`);
  ok(pred4[1] === 2 && pred4[2] === 3, '通道 1 空空 4 → 推 2/3', pred4);
  // 页面上确实画出了暗色提示，且点一下能采用
  const tag = await page.evaluate(`(()=>{
    const t=document.querySelector('#tbody .predtag');
    return t?t.textContent.trim():null;})()`);
  ok(tag && tag.indexOf('通道 2') >= 0, '暗色提示渲染 = ' + tag, tag);
  await page.evaluate(`acceptPred(1)`);
  const got = await page.evaluate('S.rows[1].channel');
  ok(got === 2, '点提示采用 → channel=2', got);
  // 一键补齐
  const filled = await page.evaluate(`(()=>{fillAllPred();return S.rows.map(r=>r.channel);})()`);
  ok(JSON.stringify(filled) === JSON.stringify([1,2,3,4]), '补齐推出来的键位 → ' + JSON.stringify(filled), filled);

  /* ---------- 3. 加一行：默认名 + 键位/通道续排 ---------- */
  // 默认名要从「更多设置」的输入框与内存两份一起改，
  // 否则 addRow 读的是 S.defaultName（页面载入时从设置恢复的），不是输入框的临时值
  const add = await page.evaluate(`(()=>{
    document.getElementById('defname').value='技法 {n}';
    S.defaultName='技法 {n}';
    S.rows=[]; renderTable();
    S.rows.push(Object.assign(blankRow(),{name:'a',note:24}));
    S.rows.push(Object.assign(blankRow(),{name:'b',note:25}));
    renderTable(); addRow();
    const r=S.rows[2];
    return {name:r.name,note:r.note,color:r.color};
  })()`);
  ok(add.name === '技法 3', '新行名 = 默认名带编号 → ' + add.name, add);
  ok(add.note === 26, '新行键位接着 +1 → ' + add.note, add);
  // 触发方式继承自上一行；通道行才会排通道
  const add2 = await page.evaluate(`(()=>{
    S.rows=[];
    S.rows.push(Object.assign(blankRow(),{switch:'ch',channel:3}));
    S.rows.push(Object.assign(blankRow(),{switch:'ch',channel:4}));
    renderTable(); addRow();
    const r=S.rows[2]; return {sw:r.switch,ch:r.channel,note:r.note};
  })()`);
  ok(add2.sw === 'ch' && add2.ch === 5 && add2.note === null,
     '通道行续排：switch=ch / ch=5 / 不给键位', add2);
  await page.evaluate(`document.getElementById('defname').value='';`);

  /* ---------- 4. 批量：勾选 + 套用 ---------- */
  const batch = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow(),blankRow()];
    S.rows.forEach((r,i)=>{r.name='n'+(i+1);r.color=1;});
    renderTable();
    [0,1,3].forEach(i=>S.sel.add(i));
    syncSelUI();
    return {n:document.getElementById('selCount').textContent,
            on:document.getElementById('batchbar').classList.contains('on')};
  })()`);
  ok(batch.n === '3' && batch.on, '批量栏出现，勾选 3 行', batch);
  // 颜色现在走独立的「颜色…」模块（默认模式 = 全部设成同一个颜色）
  const bc = await page.evaluate(`(()=>{
    document.getElementById('batchColorBtn').click();
    document.getElementById('cmMode').value='fixed';
    document.getElementById('cmMode').dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('cmColor').value='7';
    cmGo();
    return S.rows.map(r=>r.color);
  })()`);
  ok(JSON.stringify(bc) === JSON.stringify([7,7,1,7]), '批量改颜色只动勾选行 → ' + bc, bc);
  // 改完勾选要留着，方便连着改第二项
  const keep = await page.evaluate('Array.from(S.sel).sort().join(",")');
  ok(keep === '0,1,3', '批量后仍保留勾选 → ' + keep, keep);
  // 按序号批量命名
  const bn = await page.evaluate(`(()=>{
    document.getElementById('batchName').click();
    document.getElementById('bnFmt').value='连奏 {n}';
    bnGo('fmt');
    return S.rows.map(r=>r.name);
  })()`);
  ok(JSON.stringify(bn) === JSON.stringify(['连奏 1','连奏 2','n3','连奏 4']),
     '批量按序号命名 → ' + bn, bn);
  // 批量设触发方式（组合行要跳过）
  const bs = await page.evaluate(`(()=>{
    S.rows[3].combo=true; renderTable();
    S.sel=new Set([0,3]); syncSelUI();
    document.getElementById('batchSwitch').value='cc';
    document.getElementById('applySwitch').click();
    return S.rows.map(r=>r.switch);
  })()`);
  ok(bs[0] === 'cc' && bs[3] !== 'cc', '组合行不会被批量改触发方式 → ' + bs, bs);
  // 删行
  const del = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()];
    renderTable(); S.sel=new Set([0,2]); syncSelUI();
    document.getElementById('batchDel').click();
    return S.rows.length;
  })()`);
  ok(del === 1, '批量删行 → 剩 ' + del, del);

  /* ---------- 5. 发音法「类型」 ---------- */
  const at = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow()]; renderTable();
    const sel=document.querySelector('#tbody [data-f="articulationtype"]');
    const opts=Array.from(sel.options).map(o=>o.textContent);
    sel.value='0'; sel.dispatchEvent(new Event('change',{bubbles:true}));
    return {opts:opts, v:S.rows[0].articulationtype, payload:rowPayload(0).articulationtype};
  })()`);
  ok(JSON.stringify(at.opts) === JSON.stringify(['属性','奏法指示']), '类型下拉两项 → ' + at.opts, at);
  ok(at.v === 0 && at.payload === 0, '选「属性」存进行里也会发给后端', at);
  // 从技法清单带入的行：改名后 conditions[0] 必须跟着变
  const syncDesc = await page.evaluate(`(()=>{
    S.rows=[rowFor({name:'Legato',group:0,switch:'ks',note:24,
                    description:'Legato',color:1})];
    renderTable();
    const inp=document.querySelector('#tbody [data-f="name"]');
    inp.value='连奏'; inp.dispatchEvent(new Event('change',{bubbles:true}));
    return {cond:S.rows[0].conditions[0].description, row:S.rows[0].description};
  })()`);
  ok(syncDesc.cond === '连奏' && syncDesc.row === '连奏',
     '改名后 conditions 跟着改 → ' + JSON.stringify(syncDesc), syncDesc);

  /* ---------- 6. 高级参数（转调/长度/力度/音高） ---------- */
  const adv = await page.evaluate(`(()=>{
    S.rows=[blankRow()]; renderTable(); openAdv(0);
    document.getElementById('advTrans').value='-5';
    document.getElementById('advTrans').dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('advLength').value='0.25';
    document.getElementById('advLength').dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('advMinVel').value='40';
    document.getElementById('advMinVel').dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('advMaxVel').value='90';
    document.getElementById('advMaxVel').dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('advMinPitch').value='C0';
    document.getElementById('advMinPitch').dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('advSymbol').value='3';
    document.getElementById('advSymbol').dispatchEvent(new Event('change',{bubbles:true}));
    const r=S.rows[0];
    return {transpose:r.transpose,length_fact:r.length_fact,min_velocity:r.min_velocity,
            max_velocity:r.max_velocity,min_pitch:r.min_pitch,symbol:r.symbol};
  })()`);
  ok(adv.transpose === -5, '转调 -5', adv);
  ok(adv.length_fact === 0.25, '长度 0.25', adv);
  ok(adv.min_velocity === 40 && adv.max_velocity === 90, '力度窗口 40–90', adv);
  ok(adv.min_pitch === 24, '最小音高 C0 → 24（Cubase 叫法）', adv);
  ok(adv.symbol === 3, '记谱符号 3', adv);
  // 面板值套用到勾选行
  const advAll = await page.evaluate(`(()=>{
    S.rows=[blankRow(),blankRow(),blankRow()]; renderTable();
    S.sel=new Set([0,2]); syncSelUI(); openAdv(0);
    document.getElementById('advTrans').value='7';
    document.getElementById('advTrans').dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('advApplyAll').click();
    return S.rows.map(r=>r.transpose);
  })()`);
  ok(JSON.stringify(advAll) === JSON.stringify([7,0,7]), '高级参数套用到勾选行 → ' + advAll, advAll);

  /* ---------- 7. 导出目录 ---------- */
  // 说明：输入框显示的是「settings 里存的 out_dir」。存过值就显示值 + 「（自定义）」，
  // 没存过才是空的 + 「（默认 out 文件夹）」。两种都合法，断言按实际状态来判断。
  const od = await page.evaluate(`(()=>{
    const el=document.getElementById('outdir');
    return {val:el.value, ph:el.placeholder, saved:S.settings.out_dir||'',
            st:document.getElementById('outdirState').textContent,
            resolved:S.outDir};
  })()`);
  ok(od.val === od.saved &&
     (od.saved ? od.st.indexOf('自定义') >= 0 : od.st.indexOf('默认') >= 0),
     '导出目录与设置一致（存了显示值，没存显示默认） → ' + JSON.stringify(od), od);
  // 「用回默认」之后必须是干净的默认态
  const odReset0 = await page.evaluate(`(async()=>{
    document.getElementById('resetOut').click();
    await new Promise(r=>setTimeout(r,400));
    return {val:document.getElementById('outdir').value,
            st:document.getElementById('outdirState').textContent};})()`);
  ok(odReset0.val === '' && odReset0.st.indexOf('默认') >= 0,
     '清空后 = 默认 out 文件夹 → ' + JSON.stringify(odReset0), odReset0);
  const od2 = await page.evaluate(`(async()=>{
    const el=document.getElementById('outdir');
    document.getElementById('outdir').value=${JSON.stringify(TMP)};
    document.getElementById('outdir').dispatchEvent(new Event('change',{bubbles:true}));
    await new Promise(r=>setTimeout(r,400));
    return {out:S.outDir, st:document.getElementById('outdirState').textContent};
  })()`);
  ok(od2.out.replace(/\\/g,'/') === TMP && od2.st.indexOf('自定义') >= 0,
     '改成自定义目录 → ' + JSON.stringify(od2), od2);
  // 「用回默认」
  const od3 = await page.evaluate(`(async()=>{
    document.getElementById('resetOut').click();
    await new Promise(r=>setTimeout(r,400));
    return {v:document.getElementById('outdir').value,
            st:document.getElementById('outdirState').textContent};
  })()`);
  ok(od3.v === '' && od3.st.indexOf('默认') >= 0, '用回默认 → ' + JSON.stringify(od3), od3);

  /* ---------- 8. 生成：确认写到了指定目录 ---------- */
  const gen = await page.evaluate(`(async()=>{
    S.rows=[Object.assign(blankRow(),{name:'Legato',note:24}),
            Object.assign(blankRow(),{name:'Staccato',note:25})];
    renderTable();
    document.getElementById('outdir').value=${JSON.stringify(TMP)};
    const res=await api('/api/generate','POST',{rows:S.rows,map_name:'冒烟测试',
      brand:'kontakt',source:'smoke',start_key:24,
      out_dir:document.getElementById('outdir').value,overwrite:true});
    return {ok:!res.error,dir:res.out_dir,map:res.map,count:res.count,readback:res.readback};
  })()`);
  ok(gen.ok && (gen.dir||'').replace(/\\/g,'/') === TMP && gen.count === 2,
     '生成到自定义目录 → ' + JSON.stringify(gen), gen);
};
