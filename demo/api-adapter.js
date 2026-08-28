const API_BASE='http://127.0.0.1:8766';
const apiButton=document.querySelector('#apiMode');
const statusLabel=document.querySelector('#connectionStatus');
apiButton.addEventListener('click',async()=>{
  apiButton.disabled=true; apiButton.textContent='Connecting…';
  try{
    const health=await (await fetch(`${API_BASE}/health`)).json();
    const payload=await (await fetch(`${API_BASE}/alerts`)).json();
    statusLabel.textContent=`API mode · ${health.model_version}`;
    apiButton.textContent='API connected';
    apiButton.classList.add('connected');
    document.querySelector('[data-view="queue"]').click();
    const list=document.querySelector('.alert-list');
    if(list) list.innerHTML=payload.alerts.map(a=>`<div class="alert"><i class="alert-dot ${a.band}"></i><div><h3>${a.title}</h3><p>${a.id} · timestep ${a.time_step} · ${a.action}</p></div><span class="pill ${a.band}">${a.band}</span><div class="alert-score">${Number(a.score).toFixed(2)}</div></div>`).join('');
  }catch(e){
    statusLabel.textContent='Recorded mode · API unavailable'; apiButton.textContent='Retry API'; apiButton.disabled=false;
  }
});

const liveTab=document.createElement('button');
liveTab.className='tab'; liveTab.dataset.view='live'; liveTab.textContent='Live score';
document.querySelector('nav').appendChild(liveTab);
const featureNames=['in_tx_count_t','out_tx_count_t','tx_count_t','in_tx_count_last3','out_tx_count_last3','tx_count_last3','in_tx_count_last5','out_tx_count_last5','tx_count_last5','cumulative_in_tx_count','cumulative_out_tx_count','cumulative_tx_count','active_timesteps_to_t','active_last3_timesteps','active_last5_timesteps','in_degree_t','out_degree_t','unique_counterparties_t','unique_counterparties_last3','unique_counterparties_last5','new_counterparties_t','cumulative_unique_counterparties'];
function liveView(){return `<div class="section-head"><div><h1>Live score</h1><p>Submit a feature vector to the saved horizon-1 model through the local API.</p></div></div><div class="grid two-col"><section class="card"><div class="eyebrow">Controlled scoring input</div><h2 style="font:600 18px 'Space Grotesk';margin:8px 0">Score one actor</h2><p style="color:var(--muted);line-height:1.5;font-size:12px">This prototype exposes three key operational signals. Other model features are sent as zero unless you provide them through the API directly.</p><form id="scoreForm"><label>Actor ID<input name="address" value="demo-live-001" required></label><label>Time step<input name="time_step" type="number" value="48" min="1" required></label><label>Transactions at t<input name="tx_count_t" type="number" value="4" min="0" required></label><label>Unique counterparties<input name="unique_counterparties_t" type="number" value="12" min="0" required></label><label>New links<input name="new_counterparties_t" type="number" value="7" min="0" required></label><button class="button" type="submit">Run live score</button></form><div id="scoreResult"></div></section><section class="card"><div class="eyebrow">Inference contract</div><div class="mini-note" style="margin-top:12px">The API validates the actor ID, requires all model features, rejects non-numeric or non-finite values, and returns insufficient evidence when the vector is incomplete.</div><div class="timeline"><div><strong>Input</strong><br>Actor identity, timestep, and causal/graph features.</div><div><strong>Inference</strong><br>Saved xgb-graph-v1 model produces a probability.</div><div><strong>Decision</strong><br>Critical/high → human review; monitor → retain context.</div></div></section></div>`}
liveTab.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));liveTab.classList.add('active');document.querySelector('#main').innerHTML=liveView();document.querySelector('#scoreForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);const features=Object.fromEntries(featureNames.map(n=>[n,0]));for(const n of ['tx_count_t','unique_counterparties_t','new_counterparties_t'])features[n]=Number(f.get(n));const out=document.querySelector('#scoreResult');out.innerHTML='<div class="mini-note">Scoring…</div>';try{const res=await fetch(`${API_BASE}/score`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:f.get('address'),time_step:Number(f.get('time_step')),features})});const data=await res.json();if(!res.ok)throw Error(data.error||'Request failed');const r=data.result;out.innerHTML=`<div class="mini-note"><strong>${r.title}</strong><br>Score: <strong>${r.score===null?'—':Number(r.score).toFixed(4)}</strong> · Band: <strong>${r.band}</strong><br>Action: ${r.action}<br>${(r.evidence||[]).join(' · ')}<br><small>${r.model_version||''}</small></div>`}catch(err){out.innerHTML=`<div class="mini-note" style="border-color:var(--red)">API unavailable or request rejected: ${err.message}</div>`}})});
