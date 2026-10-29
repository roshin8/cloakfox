// Offline diagnostic. Reads unmodified pinned CreepJS; never used by browser policy.
const fs=require('fs');const dir=process.cwd();
const source=fs.readFileSync('tests/fingerprint/reports/library-fixtures/creepjs/src/webgl/index.ts','utf8');
const list=source.slice(source.indexOf('const getParamNames = () => ['),source.indexOf('].sort()')).replace(/\/\/[^\n]*/g,'');
const names=new Set([...list.matchAll(/'([A-Z0-9_]+)'/g)].map(m=>m[1]));
const knownBrands=new Set(source.match(/const brandCapabilities = (\[[^\n]+\])/)[1].match(/'[0-9a-f]+'/g).map(x=>x.slice(1,-1)));
const knownCaps=new Set(JSON.parse(source.match(/const capabilities = (\[[^\n]+\])/)[1]));
const corpus=JSON.parse(fs.readFileSync('additions/cloakcfg/gpu-reference-records.json'));
function hash(x){const s=JSON.stringify(x);let h=0x811c9dc5;for(let i=0;i<s.length;i++)h=Math.imul(31,h)+s.charCodeAt(i)|0;return(h>>>0).toString(16).padStart(8,'0')}
function brand(gpu){if(!gpu)return null;return /radeon/i.test(gpu)?'AMD':/geforce/i.test(gpu)?'NVIDIA':(/(adreno|amd|apple|intel|llvm|mali|microsoft|nvidia|parallels|powervr|samsung|swiftshader|virtualbox|vmware)/i.exec(gpu)?.[0]||'other').toUpperCase()}
function projection(record,adapted=false,canonicalState=false){const p={};const contexts=[corpus.contexts[record.webgl],corpus.contexts[record.webgl2]];for(const c of contexts){for(const entry of Object.values(c.observed.params))if(names.has(entry.name))p[entry.name]=entry.value;}
 const gl=contexts[0].observed;p.MAX_VIEWPORT_DIMS=gl.params['3386'].value;p.MAX_TEXTURE_MAX_ANISOTROPY_EXT=gl.maxAnisotropy;p.MAX_DRAW_BUFFERS_WEBGL=gl.maxDrawBuffersWebgl;p.antialias=gl.contextAttributes.antialias;
 const shaders={35633:'VERTEX_SHADER',35632:'FRAGMENT_SHADER'},precision={36336:'LOW_FLOAT',36337:'MEDIUM_FLOAT',36338:'HIGH_FLOAT',36341:'HIGH_INT'};
 for(const entry of gl.shaderPrecisionFormats){if(!precision[entry.precisionType])continue;for(const[k,v]of Object.entries(entry.shaderPrecisionFormat))p[shaders[entry.shaderType]+'.'+precision[entry.precisionType]+'.'+k]=adapted?(entry.precisionType===36341?(k==='precision'?0:k==='rangeMin'?31:30):(k==='precision'?23:127)):v;}
 if(adapted){p.MAX_ELEMENT_INDEX=4294967295;p.MAX_TEXTURE_LOD_BIAS=16;p.MAX_SERVER_WAIT_TIMEOUT=0;const q=contexts[1].staticCapabilities.parameters,v=k=>q[k]?.value;const varying=Math.min(v(36348),v(35659)/4,v(37154)/4,v(37157)/4);for(const k of ['MAX_VARYING_VECTORS'])p[k]=varying;for(const k of ['MAX_VARYING_COMPONENTS','MAX_VERTEX_OUTPUT_COMPONENTS','MAX_FRAGMENT_INPUT_COMPONENTS'])p[k]=4*varying;}
 if(canonicalState)for(const k of ['STENCIL_VALUE_MASK','STENCIL_WRITEMASK','STENCIL_BACK_VALUE_MASK','STENCIL_BACK_WRITEMASK'])p[k]=4294967295;
 return p;
}
function analyze(r,p){const values=[...new Set(Object.values(p).filter(v=>v&&typeof v!='string').flat().map(Number))].sort((a,b)=>a-b);const bh=hash([brand(r.gpu.renderer),''+values]);const ch=values.reduce((a,v,i)=>a^(+v+i),0);return{brandHash:bh,capabilityHash:ch,brandKnown:knownBrands.has(bh),capabilitiesKnown:knownCaps.has(ch)}}
const rows=corpus.records.filter(r=>[r.webgl,r.webgl2].every(k=>corpus.contexts[k].observed?.params)).map(r=>({id:r.id,family:r.family,os:r.os,gpu:r.gpu,original:analyze(r,projection(r)),adapted:analyze(r,projection(r,true)),adaptedCurrentState:analyze(r,projection(r,true,true))}));
module.exports={corpus,projection,analyze,rows,names};
if(require.main===module){
 const counts=Object.fromEntries(['original','adapted','adaptedCurrentState'].map(type=>[type,rows.filter(r=>r[type].brandKnown&&r[type].capabilitiesKnown).length]));
 console.log(JSON.stringify({purpose:'Offline projection only; native execution admission is independently required',sourceArchive:corpus.source.archive.sha256,completeObservedPairs:rows.length,excludedPairs:corpus.records.length-rows.length,recognized:counts,rows},null,2));
}
