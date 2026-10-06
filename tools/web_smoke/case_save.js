/* 保存按钮：只校验重复键位，绝不自动替你填一个键。
   —— 用户要求：把「保存时自动补快捷键」去掉，但撞键的检验要留着。
   ⚠️ 这里用桩顶掉 api()，不去真写技法清单，免得污染用户自己的库。 */
module.exports = async (page, ok) => {
  const APP = 'http://127.0.0.1:' + (process.env.APP_PORT || 8777);
  await page.nav(APP + '/?demo=1');

  const res = await page.evaluate(`(async()=>{
    const realApi=window.api, realAlert=window.alert;
    let alerted='';
    window.alert=(m)=>{alerted=m;};
    window.api=async()=>({status:'conflict',free_key:25,
      conflict:{name:'早就占位的技法',group:0,switch:'ks',
                note:24,channel:null,cc_num:null,cc_val:null}});
    S.rows=[Object.assign(blankRow(),{name:'我要保存的',switch:'ks',note:24})];
    S.rows[0].conditions=[{group:0,description:'我要保存的',note:24}];
    renderTable();
    await saveRow(0);
    const out={note:S.rows[0].note,
               cond:S.rows[0].conditions[0].note,
               saved:!!S.rows[0]._saved,
               alerted:alerted};
    window.api=realApi; window.alert=realAlert;
    return out;
  })()`);

  ok(res.note === 24 && res.cond === 24,
     '撞键时**不自动改键位**（原来会被换成空闲键 25）', res);
  ok(res.saved === false, '撞键时**不写进清单**（没标成「已存」）', res);
  ok(/没保存/.test(res.alerted) && /重复/.test(res.alerted),
     '弹窗说明是重复导致的没保存 → ' + String(res.alerted).slice(0, 30), res);
  // 24 = C0（Cubase 记法），空闲键 25 = C#0
  ok(/这一行：C0/.test(res.alerted) && /清单里：C0/.test(res.alerted),
     '把双方键位都报出来（都是 C0 才叫重复） → ' + String(res.alerted).replace(/\n/g, ' | '), res);
  ok(/空着的：C#0 \/ 25/.test(res.alerted),
     '顺带说一句目前空着哪个键（只提示，不代填）', res);

  /* 不撞键时照常保存 */
  const okSave = await page.evaluate(`(async()=>{
    const realApi=window.api;
    window.api=async()=>({status:'added'});
    S.rows=[Object.assign(blankRow(),{name:'没撞的',switch:'ks',note:30})];
    renderTable();
    await saveRow(0);
    window.api=realApi;
    return {saved:!!S.rows[0]._saved, note:S.rows[0].note};
  })()`);
  ok(okSave.saved === true && okSave.note === 30,
     '没撞键 → 照常保存，键位原样不动', okSave);
};
