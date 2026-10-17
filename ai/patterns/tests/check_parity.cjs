const {spawnSync}=require('node:child_process');
const {writeFileSync}=require('node:fs');
const path=require('node:path');
const engine=require('../static/engine.js');
const result=spawnSync(process.argv[2]||'python',['-m','ai.patterns.tests.parity_reference'],{cwd:path.resolve(__dirname,'../../..'),encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'},maxBuffer:20*1024*1024});
if(result.status!==0)throw Error(result.stderr);
const {bundle,cases}=JSON.parse(result.stdout);
function compare(a,b,where=''){
 if(typeof a==='number'&&typeof b==='number'){if(Math.abs(a-b)>1e-6)throw Error(`${where}: ${a} != ${b}`);return}
 if(Array.isArray(a)){if(!Array.isArray(b)||a.length!==b.length)throw Error(`${where}: array shape`);a.forEach((x,i)=>compare(x,b[i],where+'['+i+']'));return}
 if(a&&typeof a==='object'){if(Object.keys(a).sort().join('|')!==Object.keys(b).sort().join('|'))throw Error(`${where}: object keys`);for(const k of Object.keys(a))compare(a[k],b[k],where+'.'+k);return}
 if(a!==b)throw Error(`${where}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`);
}
for(const [i,c] of cases.entries())compare(c.expected,engine.discover(bundle,c.options),'case '+i);
const report={label:'Python/browser-engine parity',passed:cases.length,failed:0,thresholds:18,exclusion_sets:19,scopes:2,numeric_tolerance:1e-6};
if(process.argv[3])writeFileSync(process.argv[3],JSON.stringify(report,null,2));
process.stdout.write(JSON.stringify(report,null,2)+'\n');
