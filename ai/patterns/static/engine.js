/* Browser mirror of engine.py. Verified against Python across thresholds/exclusions. */
(function(root) {
'use strict';
const cmp=(a,b)=>a<b?-1:a>b?1:0;
const round=n=>Math.round((n+Number.EPSILON)*1e6)/1e6;
function cosine(a,b){let s=0,aa=0,bb=0;for(let i=0;i<a.length;i++){s+=a[i]*b[i];aa+=a[i]*a[i];bb+=b[i]*b[i]}return aa&&bb?s/Math.sqrt(aa*bb):0}
function eligible(e){return e.in_iasi&&(e.facets.some(f=>f.startsWith('cause:'))||e.facets.length>=2)}
function discover(bundle,options={}){
 const excluded=options.excluded||[],threshold=options.threshold??.35,scope=options.scope||'fixtures';
 if(!['fixtures','sources'].includes(scope))throw Error('scope must be fixtures or sources');
 if(threshold<.10||threshold>.95)throw Error('threshold must be between 0.10 and 0.95');
 if(excluded.some(id=>!bundle.events.some(e=>e.id===id)))throw Error('Unknown excluded event ID');
 let events=bundle.events.filter(e=>!excluded.includes(e.id)&&e.in_iasi);
 events=events.filter(e=>scope==='sources'?(e.articles.length&&e.source_profile):eligible(e));
 if(scope==='sources')events=events.map(e=>({...e,facets:e.source_facets}));
 const result={scope,threshold,excluded:[...new Set(excluded)].sort(cmp),eligible_ids:events.map(e=>e.id),patterns:[],unassigned_ids:[],note:null,engine:bundle.model.method};
 if(events.length<(scope==='sources'?5:3)){
  result.note=scope==='sources'?'Insufficient source evidence: fewer than five events have matched source excerpts. The five-event guardrail is a demo policy, not statistical validation.':'Fewer than three sufficiently described eligible events remain.';
  result.unassigned_ids=result.eligible_ids;return result;
 }
 const vectors=scope==='sources'?bundle.source_vectors:bundle.vectors;
 const sims={};for(const a of events){sims[a.id]={};for(const b of events)sims[a.id][b.id]=cosine(vectors[a.id],vectors[b.id])}
 const population={};for(const e of events)for(const f of e.facets)population[f]=(population[f]||0)+1;
 let candidates=[];
 for(const anchor of events){
  const ranked=events.filter(e=>e.id!==anchor.id).sort((a,b)=>sims[anchor.id][b.id]-sims[anchor.id][a.id]||cmp(a.id,b.id));
  let members=[anchor];
  for(const e of ranked){if(members.length>=6)break;if(members.every(m=>sims[e.id][m.id]+1e-9>=threshold))members.push(e)}
  const sites=new Set(members.map(m=>m.site_id||m.location));if(members.length<3||sites.size<2)continue;
  const counts={};for(const e of members)for(const f of e.facets)counts[f]=(counts[f]||0)+1;
  const distinct=Object.keys(counts).filter(f=>counts[f]>=Math.ceil(.66*members.length)).sort((a,b)=>
   -(counts[a]/members.length-population[a]/events.length)+(counts[b]/members.length-population[b]/events.length)||counts[b]-counts[a]||cmp(a,b));
  if(!distinct.length)continue;
  const pairs=[];for(let i=0;i<members.length;i++)for(let j=i+1;j<members.length;j++)pairs.push(sims[members[i].id][members[j].id]);
  const ids=members.map(e=>e.id).sort(cmp);
  const facets=distinct.map(f=>({key:f,label:bundle.facet_labels[f],count:counts[f],total:members.length,other_count:population[f]-counts[f],other_total:events.length-members.length}));
  const why=members.map(e=>({id:e.id,shared:distinct.filter(f=>e.facets.includes(f)),not_recorded:distinct.filter(f=>!e.facets.includes(f)),mean_similarity:round(members.filter(m=>m.id!==e.id).reduce((s,m)=>s+sims[e.id][m.id],0)/(members.length-1))}));
  const mean=e=>members.reduce((s,m)=>s+sims[e.id][m.id],0)/members.length;
  const outsiders=events.filter(e=>!ids.includes(e.id)).sort((a,b)=>mean(b)-mean(a)||cmp(a.id,b.id));
  candidates.push({id:'p-'+ids.join('-'),title:distinct.slice(0,2).map(f=>bundle.facet_labels[f]).join(' · '),member_ids:ids,site_count:sites.size,facets,members:why,comparison_ids:outsiders.slice(0,2).map(e=>e.id),article_event_count:members.filter(e=>e.articles.length).length,article_count:new Set(members.flatMap(e=>e.articles.map(a=>a.id))).size,mean_similarity:round(pairs.reduce((s,x)=>s+x,0)/pairs.length),min_similarity:round(Math.min(...pairs))});
 }
 candidates.sort((a,b)=>b.member_ids.length-a.member_ids.length||b.mean_similarity-a.mean_similarity||cmp(a.id,b.id));
 for(const p of candidates){let s=new Set(p.member_ids);if(result.patterns.some(q=>q.member_ids.filter(x=>s.has(x)).length/new Set([...q.member_ids,...s]).size>=.60))continue;result.patterns.push(p);if(result.patterns.length===4)break}
 const covered=new Set(result.patterns.flatMap(p=>p.member_ids));result.unassigned_ids=events.filter(e=>!covered.has(e.id)).map(e=>e.id);
 if(!result.patterns.length)result.note='No cross-location group passes the current similarity and support rules. No pattern is forced.';
 return result;
}
root.PatternEngine={discover,cosine,eligible};
if(typeof module!=='undefined')module.exports=root.PatternEngine;
})(typeof window!=='undefined'?window:globalThis);
