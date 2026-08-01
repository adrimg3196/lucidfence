(function(root){
  'use strict';
  const DB='lucidfence-web', STORE='workspace', KEY='default';
  function open(){return new Promise((resolve,reject)=>{
    if(!('indexedDB' in root)){resolve(null);return;}
    const request=indexedDB.open(DB,1);
    request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains(STORE))request.result.createObjectStore(STORE);};
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>reject(request.error);
  });}
  async function load(){
    try{
      const db=await open();
      if(!db) throw new Error('IndexedDB unavailable');
      const value=await new Promise((resolve,reject)=>{const tx=db.transaction(STORE,'readonly');const req=tx.objectStore(STORE).get(KEY);req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
      db.close();
      return value||LucidFenceWeb.initialState();
    }catch(error){
      try{const raw=localStorage.getItem(DB);return raw?JSON.parse(raw):LucidFenceWeb.initialState();}catch(ignore){return LucidFenceWeb.initialState();}
    }
  }
  async function save(state){
    const clean=LucidFenceWeb.sanitizeImport(state);
    try{
      const db=await open();
      if(!db) throw new Error('IndexedDB unavailable');
      await new Promise((resolve,reject)=>{const tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(clean,KEY);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
      db.close();
    }catch(error){localStorage.setItem(DB,JSON.stringify(clean));}
    return clean;
  }
  async function reset(){
    const state=LucidFenceWeb.initialState();
    await save(state);return state;
  }
  root.WebStore={load,save,reset};
})(typeof globalThis!=='undefined'?globalThis:this);
