(()=>{
  const q=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  function readToken(){
    const hashToken=new URLSearchParams(location.hash.slice(1)).get('token');
    if(hashToken){sessionStorage.setItem('hotel_guest_token',hashToken);history.replaceState(null,'',location.pathname)}
    return hashToken||sessionStorage.getItem('hotel_guest_token')||window.guestToken||'';
  }
  const token=readToken();
  const msg=text=>{q('message').innerHTML=`<div class="hotel-alert">${esc(text)}</div>`};
  q('submit').onclick=async()=>{
    if(!token)return msg('Guest access token is missing.');
    const payload={vehicle_number:q('vehicle').value,primary_id_type:q('id-type').value,primary_id_number:q('id-number').value,signature_name:q('signature').value,terms_accepted:q('terms').checked?1:0,privacy_consent:q('privacy').checked?1:0,request_key:crypto.randomUUID(),occupants:[{full_name:q('name').value,nationality:q('nationality').value,id_type:q('id-type').value,id_number:q('id-number').value}]};
    try{
      const response=await fetch('/api/method/hotel_pms.guest_portal.submit_self_checkin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({raw_token:token,payload})});
      const json=await response.json();
      if(!response.ok||json.exc)throw new Error(typeof json.message==='string'?json.message:'Request failed');
      msg(`Registration ${json.message.registration} submitted.`);
    }catch(error){msg(error.message)}
  };
})();
