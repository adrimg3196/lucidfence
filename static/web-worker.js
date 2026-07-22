importScripts('./web-core.js');
self.onmessage=function(event){
  const message=event.data||{};
  if(message.type!=='RUN_CYCLE') return;
  try{
    const state=LucidFenceWeb.sanitizeImport(message.state);
    const result=LucidFenceWeb.runCycle(state,message.snapshot||LucidFenceWeb.snapshot(state));
    self.postMessage({ok:true,state,result});
  }catch(error){self.postMessage({ok:false,error:String(error&&error.message||error)});}
};
