module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  const TMP = (process.env.SMOKE_TMP || '').replace(/\\/g, '/');
  await page.nav(APP + '/?demo=1');

  /* ---------- 「打开导出文件夹」真的能调起资源管理器 ---------- */
  const of = await page.evaluate(`(async()=>{
    const a=await api('/api/open_folder','POST',{dir:''});
    const b=await api('/api/open_folder','POST',{dir:${JSON.stringify(TMP)}});
    return {a:a,b:b};
  })()`);
  ok(of.a.ok === true, '默认目录能打开 → ' + JSON.stringify(of.a), of.a);
  ok(of.b.ok === true && (of.b.dir || '').replace(/\\/g, '/') === TMP,
     '自定义目录能打开 → ' + JSON.stringify(of.b), of.b);
  const bad = await page.evaluate(`(async()=>{
    return await api('/api/open_folder','POST',{dir:'Z:/不存在的盘/没有这个目录'});})()`);
  ok(bad.ok === false && !!bad.error, '不存在的目录要给错误而不是崩 → ' + JSON.stringify(bad), bad);

  /* ---------- 高级参数是否真的写进 expressionmap ---------- */
  const gen = await page.evaluate(`(async()=>{
    const row=Object.assign(blankRow(),{name:'Ping测试',note:36,transpose:-12,
      length_fact:0.25,velocity_fact:0.5,min_velocity:40,max_velocity:90,
      min_pitch:24,max_pitch:84,symbol:3,text:'短',remote:12,articulationtype:0});
    const res=await api('/api/generate','POST',{rows:[row],map_name:'高级字段检查',
      brand:'kontakt',source:'smoke',start_key:24,
      out_dir:${JSON.stringify(TMP)},overwrite:true});
    return {path:res.map,count:res.count,readback:res.readback};
  })()`);
  ok(gen.count === 1 && gen.readback, '生成 + 回读通过 → ' + JSON.stringify(gen), gen);
  const xml = require('fs').readFileSync(gen.path.replace(/\\/g, '/'), 'utf8');
  const grab = (k) => {
    const m = new RegExp('name="' + k + '" value="(-?[0-9.]+)"').exec(xml);
    return m ? m[1] : null;
  };
  ok(grab('transpose') === '-12', 'XML transpose=-12', grab('transpose'));
  ok(grab('velocityFact') === '0.5', 'XML velocityFact=0.5', grab('velocityFact'));
  ok(grab('lengthFact') === '0.25', 'XML lengthFact=0.25', grab('lengthFact'));
  ok(grab('minVelocity') === '40', 'XML minVelocity=40', grab('minVelocity'));
  ok(grab('maxVelocity') === '90', 'XML maxVelocity=90', grab('maxVelocity'));
  ok(grab('minPitch') === '24', 'XML minPitch=24', grab('minPitch'));
  ok(grab('maxPitch') === '84', 'XML maxPitch=84', grab('maxPitch'));
  ok(grab('symbol') === '3', 'XML symbol=3（行级也要带上）', grab('symbol'));
  ok(/短/.test(xml), '短标签写进 XML', true);
  // NoteOn 力度会被夹进力度窗口：默认 120 + 窗口 40–90 → 实际发 90
  const data2 = grab('data2');
  ok(data2 === '90', '力度被夹进窗口 40–90 → data2=' + data2, data2);
  ok(grab('articulationtype') === '0', 'XML articulationtype=0（属性）', grab('articulationtype'));

  /* ---------- 回归：路径不能拼进 onclick 属性 ----------
     曾经的 bug —— 生成完成弹窗里的按钮写成
       onclick="openFolderNow('${esc(res.out_dir)}')"
     esc() 不转反斜杠，属性文本又要过一遍 JS 解析，
     于是 `D:\...\out` 里的 `\缓` `\w` `\C` `\o` 被当转义吃掉，
     路径变成 `D缓存workbuddyCubaseEMout`，资源管理器跳到一个空文件夹。
     断言：点弹窗里那个按钮，实际发出去的 dir 必须和生成的 out_dir **逐字符相同**。 */
  const winPath = TMP + '/中文 目录/测试';        // 反斜杠 + 中文 + 空格，最容易漏
  const dirBug = await page.evaluate(`(async()=>{
    // 挂个探针，看按钮真正传了什么
    let seen='';
    const real=window.openFolderNow;
    window.openFolderNow=async(d)=>{
      seen=(d===undefined||d===null)?document.getElementById('genOutDir').textContent:d;
      return real(seen);
    };
    const row=Object.assign(blankRow(),{name:'路径检查',note:40});
    const res=await api('/api/generate','POST',{rows:[row],map_name:'路径检查',
      brand:'kontakt',source:'smoke',start_key:24,
      out_dir:${JSON.stringify(winPath)},overwrite:true});
    S.lastOutDir=res.out_dir||'';
    renderTable();
    // 走真实的弹窗路径
    openModal('<div class="mono" id="genOutDir">'+res.out_dir+'</div>'
      +'<button id="__probe" onclick="openFolderNow()">x</button>');
    seen='';
    window.openFolderNow();
    const got=seen;
    window.openFolderNow=real;closeModal();
    return {want:res.out_dir,got:got,last:S.lastOutDir};
  })()`);
  ok(dirBug.got === dirBug.want,
     '弹窗「打开这个文件夹」传出的路径要和生成的目录逐字一致',
     dirBug.got + '  ← 期望 ' + dirBug.want);
  ok(dirBug.got.indexOf('缓存workbuddy') < 0 && dirBug.got.indexOf('缓存workbuddyCubaseEMout') < 0,
     '路径里不能出现反斜杠被吃掉后的粘连（缓存workbuddy…）', dirBug.got);
  ok(/\\中文 目录\\测试$/.test(dirBug.got) || /\/中文 目录\/测试$/.test(dirBug.got),
     '中文与空格目录名完整保留', dirBug.got);

  /* ---------- 「设为默认」把当前输入存成默认 ---------- */
  const setDef = await page.evaluate(`(async()=>{
    document.getElementById('outdir').value=${JSON.stringify(winPath)};
    await saveOutDir(document.getElementById('outdir').value,true);
    const saved=S.settings.out_dir;
    const resolved=S.outDir;
    const r=await api('/api/state');
    // 生成时不再传 out_dir，应该落到刚存的默认目录
    const row=Object.assign(blankRow(),{name:'默认目录检查',note:41});
    const res=await api('/api/generate','POST',{rows:[row],map_name:'默认目录检查',
      brand:'kontakt',source:'smoke',start_key:24,overwrite:true});
    const stateResolved=r.out;
    // 收尾：改回默认，别污染后面的用例
    document.getElementById('outdir').value='';
    await saveOutDir('',true);
    return {saved:saved,resolved:resolved,stateResolved:stateResolved,
            genPath:res.map,back:S.settings.out_dir};
  })()`);
  ok(setDef.saved === winPath, '「设为默认」把输入存进了 settings → ' + setDef.saved, setDef.saved);
  ok(setDef.resolved.replace(/\\/g, '/') === winPath.replace(/\\/g, '/'),
     '存下来的默认目录解析正确 → ' + setDef.resolved, setDef.resolved);
  ok(setDef.genPath.replace(/\\/g, '/').indexOf(winPath.replace(/\\/g, '/')) === 0,
     '不指定 out_dir 时用存下来的默认目录 → ' + setDef.genPath, setDef.genPath);
  ok(setDef.back === '', '「用回默认」能清干净 → ' + JSON.stringify(setDef.back), setDef.back);
};
