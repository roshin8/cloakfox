/* MPL-2.0. User-triggered measurement in the document's principal. */
export async function measureWindow(win) {
  const sandbox=Cu.Sandbox(win,{sandboxPrototype:win,wantXrays:false,sameZoneAs:win});
  const read=`({userAgent:String(navigator.userAgent).slice(0,512),platform:String(navigator.platform).slice(0,128),language:String(navigator.language).slice(0,128),hardwareConcurrency:Number(navigator.hardwareConcurrency),timezone:String(Intl.DateTimeFormat().resolvedOptions().timeZone).slice(0,128),locale:String(Intl.DateTimeFormat().resolvedOptions().locale).slice(0,128)})`;
  try {
    // Sandbox intrinsics have their own default locale; observe the actual
    // page realm's constructors instead of accidentally diagnosing the sandbox.
    const pageRead=read.replaceAll('navigator.', 'window.navigator.').replaceAll('Intl.', 'window.Intl.');
    const window=JSON.parse(Cu.evalInSandbox(`JSON.stringify(${pageRead})`,sandbox));
    const workerResult=await Cu.evalInSandbox(`new Promise(resolve=>{
      let worker,url,timer,finished=false;
      const finish=result=>{if(finished)return;finished=true;clearTimeout(timer);if(worker)worker.terminate();if(url)URL.revokeObjectURL(url);resolve(JSON.stringify(result));};
      try{url=URL.createObjectURL(new Blob(['postMessage(${read});'],{type:'text/javascript'}));
        timer=setTimeout(()=>finish({workerError:'Worker measurement timed out or was blocked.'}),3000);
        worker=new Worker(url);worker.onmessage=event=>finish({worker:event.data});
        worker.onerror=event=>{event.preventDefault();finish({workerError:'Worker unavailable under this page security policy.'});};
      }catch(error){finish({workerError:'Worker measurement could not start.'});}
    })`,sandbox);
    return {window,...JSON.parse(workerResult)};
  } finally {Cu.nukeSandbox(sandbox);}
}
