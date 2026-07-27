(()=>{
  const root=document.getElementById('portal');
  const message=document.getElementById('message');
  const esc=value=>String(value??'').replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  function readToken(){
    const hashToken=new URLSearchParams(location.hash.slice(1)).get('token');
    if(hashToken){sessionStorage.setItem('hotel_guest_token',hashToken);history.replaceState(null,'',location.pathname)}
    return hashToken||sessionStorage.getItem('hotel_guest_token')||window.guestToken||'';
  }
  const token=readToken();
  const msg=text=>{message.innerHTML=`<div class="hotel-alert">${esc(text)}</div>`};
  async function call(method,args={},post=false){
    const response=await fetch(`/api/method/${method}`,{method:post?'POST':'GET',headers:{'Content-Type':'application/json'},body:post?JSON.stringify(args):undefined});
    const json=await response.json();
    if(!response.ok||json.exc)throw new Error(typeof json.message==='string'?json.message:'Request failed');
    return json.message;
  }
  async function load(){
    if(!token)return msg('Guest access token is missing. Open the secure link supplied by the hotel.');
    try{
      const data=await call('hotel_pms.guest_portal.get_guest_portal',{raw_token:token},true),reservation=data.reservation;
      const cancellation=data.cancellation?`<div class="hotel-card"><h3>Cancellation confirmation</h3><table class="hotel-table"><tr><th>Number</th><td>${esc(data.cancellation.name)}</td></tr><tr><th>Date</th><td>${esc(data.cancellation.transaction_date)}</td></tr><tr><th>Fee</th><td>${Number(data.cancellation.final_fee||0).toLocaleString()}</td></tr><tr><th>Estimated refund</th><td>${Number(data.cancellation.refund_due||0).toLocaleString()}</td></tr></table></div>`:'';
      const privacyRows=(data.privacy_requests||[]).map(request=>`<tr><td>${esc(request.name)}</td><td>${esc(request.request_type)}</td><td>${esc(request.status)}</td><td>${request.request_type==='Data Access'&&request.status==='Completed'?`<button class="hotel-btn secondary privacy-download" data-name="${esc(request.name)}">Download</button>`:''}</td></tr>`).join('');
      root.innerHTML=`<div class="hotel-card"><h2>Reservation ${esc(reservation.name)}</h2><table class="hotel-table"><tr><th>Status</th><td>${esc(reservation.status)}</td></tr><tr><th>Stay</th><td>${esc(reservation.arrival_date)} to ${esc(reservation.departure_date)}</td></tr><tr><th>Total</th><td>${Number(reservation.quoted_grand_total||0).toLocaleString()}</td></tr><tr><th>Deposit received</th><td>${Number(reservation.deposit_received||0).toLocaleString()}</td></tr></table>${data.features.self_checkin?`<a class="hotel-btn" href="/hotel-checkin#token=${encodeURIComponent(token)}">Self check-in</a> `:''}<button class="hotel-btn secondary" id="pay">Payment link</button> ${data.features.cancellation&&data.cancellation_preview?`<button class="hotel-btn secondary" id="cancel">Cancel booking</button> `:''}<button class="hotel-btn secondary" id="print">Print confirmation</button></div><div class="hotel-card"><h3>Invoices</h3>${data.invoices.length?`<table class="hotel-table">${data.invoices.map(invoice=>`<tr><td>${esc(invoice.name)}</td><td>${Number(invoice.grand_total).toLocaleString()}</td><td>Due ${Number(invoice.outstanding_amount).toLocaleString()}</td></tr>`).join('')}</table>`:'No invoices yet.'}</div>${cancellation}<div class="hotel-card"><h3>Privacy requests</h3><p><button class="hotel-btn secondary privacy-request" data-type="Data Access">Request my data</button> <button class="hotel-btn secondary privacy-request" data-type="Marketing Opt-out">Marketing opt-out</button> <button class="hotel-btn secondary privacy-request" data-type="Anonymization">Request anonymization</button></p>${privacyRows?`<table class="hotel-table"><tr><th>Request</th><th>Type</th><th>Status</th><th></th></tr>${privacyRows}</table>`:'No privacy requests.'}</div>`;
      document.getElementById('pay').onclick=pay;
      document.getElementById('print').onclick=()=>window.print();
      const cancelButton=document.getElementById('cancel');
      if(cancelButton)cancelButton.onclick=cancel;
      document.querySelectorAll('.privacy-request').forEach(button=>button.onclick=()=>privacyRequest(button.dataset.type));
      document.querySelectorAll('.privacy-download').forEach(button=>button.onclick=()=>downloadPrivacy(button.dataset.name));
    }catch(error){msg(error.message)}
  }
  async function pay(){
    try{
      const data=await call('hotel_pms.guest_portal.guest_create_payment_request',{raw_token:token,request_key:crypto.randomUUID()},true);
      if(data.payment_url)location.href=data.payment_url;else msg(`Payment Request ${data.payment_request} created.`);
    }catch(error){msg(error.message)}
  }
  async function cancel(){
    const reason=prompt('Cancellation reason');
    if(!reason)return;
    try{
      const data=await call('hotel_pms.guest_portal.guest_cancel_reservation',{raw_token:token,reason,request_key:crypto.randomUUID()},true);
      msg(`Reservation cancelled. Confirmation: ${data.cancellation}`);
      load();
    }catch(error){msg(error.message)}
  }
  async function privacyRequest(type){
    if(type==='Anonymization'&&!confirm('Anonymization is subject to identity verification, legal retention, active stays, and outstanding balances. Continue?'))return;
    try{
      const data=await call('hotel_pms.guest_portal.submit_privacy_request',{raw_token:token,request_type:type,details:'Submitted through guest portal',request_key:crypto.randomUUID()},true);
      msg(`Privacy request ${data.privacy_request} submitted.`);
      load();
    }catch(error){msg(error.message)}
  }
  async function downloadPrivacy(requestName){
    try{
      const data=await call('hotel_pms.guest_portal.get_privacy_request_result',{raw_token:token,request_name:requestName},true);
      if(!data.export)return msg('The data export is not ready.');
      const blob=new Blob([JSON.stringify(data.export,null,2)],{type:'application/json'});
      const url=URL.createObjectURL(blob),anchor=document.createElement('a');
      anchor.href=url;anchor.download=`${requestName}.json`;anchor.click();URL.revokeObjectURL(url);
    }catch(error){msg(error.message)}
  }
  load();
})();
