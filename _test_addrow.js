/* 从 index.html 定向抽出「加一行」相关函数，在 Node 里跑行为测试。
   DOM 全部打桩（renderTable / document / alert）。 */
const fs=require('fs'),vm=require('vm');
const FILE='D:/缓存/workbuddy/CubaseEM/em/web/index.html';
const src=fs.readFileSync(FILE,'utf8').replace(/\r\n/g,'\n');

/* 括号平衡扫描：跳过注释与字符串（含模板串 ${}），返回闭合后一位 */
function balanced(s,open){
  const oc=s[open],cc=oc==='{'?'}':']';
  let d=0,i=open;
  while(i<s.length){
    const c=s[i],n=s[i+1];
    if(c==='/'&&n==='/'){while(i<s.length&&s[i]!=='\n')i++;continue;}
    if(c==='/'&&n==='*'){i+=2;while(i<s.length&&!(s[i]==='*'&&s[i+1]==='/'))i++;i+=2;continue;}
    if(c==='"'||c==="'"||c==='`'){
      const q=c;i++;
      while(i<s.length){
        if(q==='`'&&s[i]==='$'&&s[i+1]==='{'){i+=2;i=balanced(s,i-1);continue;}
        if(s[i]==='\\'){i+=2;continue;}
        if(s[i]===q){i++;break;}
        i++;
      }
      continue;
    }
    if(c===oc)d++;else if(c===cc){d--;if(d===0)return i+1;}
    i++;
  }
  throw new Error('unbalanced at '+open);
}
function grabFn(name){
  const m=new RegExp('\\nfunction '+name+'\\s*\\(').exec(src);
  if(!m)throw new Error('fn not found: '+name);
  return src.slice(m.index+1,balanced(src,src.indexOf('{',m.index)));
}
function grabConst(decl){
  const i=src.indexOf(decl);
  if(i<0)throw new Error('const not found: '+decl);
  let j=i;while(j<src.length&&src[j]!=='{'&&src[j]!=='[')j++;
  return src.slice(i,balanced(src,j))+';';
}

const code=[
  grabConst('const NOTES=['),'let OCT_BASE=2;',
  grabFn('noteName'),
  grabConst('const SERIES={'),grabConst('const FIELD_DEFAULT={'),
  grabFn('fieldValue'),grabFn('wrapColor'),grabFn('predClassValue'),grabFn('predFmt'),
  grabFn('blankRow'),grabFn('setField'),
  grabFn('expandName'),grabFn('autoName'),
  grabConst('const TAIL_CLASSES=['),grabFn('tailTwo'),grabFn('inheritColor'),grabFn('addRow')
].join('\n');

const runner=`
function T(name,rows,exp,alertKey){
  S.rows=rows.map(function(o){var r=blankRow();Object.keys(o).forEach(function(k){r[k]=o[k];});return r;});
  S.defaultName='';__alerts.length=0;
  addRow();
  const r=S.rows[S.rows.length-1],errs=[];
  Object.keys(exp).forEach(function(f){
    const want=exp[f],got=r[f];
    if(want===null){if(got!==null&&got!==undefined&&got!=='')errs.push(f+' 应为空，实际 '+got);}
    else if(got!==want)errs.push(f+' 期望 '+want+'，实际 '+got);
  });
  if(alertKey&&__alerts.join('|').indexOf(alertKey)<0)errs.push('缺少提示「'+alertKey+'」');
  if(!alertKey&&__alerts.length)errs.push('不该弹窗: '+String(__alerts[0]).slice(0,50));
  __results.push({name:name,ok:errs.length===0,errs:errs,n:__alerts.length});
}
T('空表加第一行：只有名字',[ ],{name:'插槽1',note:null,color:1});
T('按键递增 +1',[{switch:'ks',note:36},{switch:'ks',note:37}],{note:38});
T('按键相同值 → 填同一个',[{switch:'ks',note:36},{switch:'ks',note:36}],{note:36});
T('按键递减 -1',[{switch:'ks',note:37},{switch:'ks',note:36}],{note:35});
T('按键差2 → 不填并弹窗',[{switch:'ks',note:36},{switch:'ks',note:38}],{note:null},'触发键');
T('只有一个按键值 → 不填并弹窗',[{switch:'ks',note:36}],{note:null},'触发键');
T('前面乱但最后两个连续 → 照排',[{switch:'ks',note:36},{switch:'ks',note:60},{switch:'ks',note:37},{switch:'ks',note:38}],{note:39});
T('触发键越界 → 不填并弹窗',[{switch:'ks',note:126},{switch:'ks',note:127}],{note:null},'触发键');
T('通道＋按键：两个空分开算',[{switch:'ks+ch',note:36,channel:3},{switch:'ks+ch',note:37,channel:4}],{note:38,channel:5});
T('纯通道行递增',[{switch:'ch',channel:1},{switch:'ch',channel:2}],{channel:3});
T('双键齐按：第一键补、第二键不补',[{switch:'ks2',note:36,note2:48},{switch:'ks2',note:37,note2:49}],{note:38,note2:null});
T('CC：号相同、值递增',[{switch:'cc',cc_num:4,cc_val:1},{switch:'cc',cc_num:4,cc_val:2}],{cc_num:4,cc_val:3});
T('细则：长度相同/力度系数+1/转调+1',[{length_fact:0.5,velocity_fact:2,transpose:-12},{length_fact:0.5,velocity_fact:3,transpose:-11}],{length_fact:0.5,velocity_fact:4,transpose:-10});
T('力度窗口 +1',[{min_velocity:100,max_velocity:120},{min_velocity:101,max_velocity:121}],{min_velocity:102,max_velocity:122});
T('音高窗口 +1',[{min_pitch:60,max_pitch:72},{min_pitch:61,max_pitch:73}],{min_pitch:62,max_pitch:74});
T('细则最后两个不连续 → 不填并弹窗',[{min_velocity:100},{min_velocity:110}],{min_velocity:null},'最小力度');
T('显示色递增',[{color:1},{color:2}],{color:3});
T('显示色到头绕回 1',[{color:15},{color:16}],{color:1});
T('触发方式继承上一行',[{switch:'cc',cc_num:1,cc_val:1},{switch:'cc',cc_num:1,cc_val:2}],{switch:'cc',cc_val:3});
`;

const ctx={S:{rows:[],defaultName:'',sel:new Set()},__alerts:[],__results:[],
  renderTable(){},document:{querySelector(){return null;}},
  alert(m){ctx.__alerts.push(m);}};
vm.createContext(ctx);
vm.runInContext(code+'\n'+runner,ctx,{filename:'addrow.js'});

let bad=0;
ctx.__results.forEach(r=>{
  if(!r.ok)bad++;
  console.log((r.ok?'PASS  ':'FAIL  ')+r.name+(r.ok?'':'\n        '+r.errs.join('\n        ')));
});
console.log('\n共 '+ctx.__results.length+' 条，失败 '+bad+' 条');
process.exit(bad?1:0);
