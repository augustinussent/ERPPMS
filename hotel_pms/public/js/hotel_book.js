(()=>{
  let selected=null;
  const q=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const msg=(text,ok=false)=>{q('message').innerHTML=`<div class="hotel-alert ${ok?'hotel-ok':''}">${esc(text)}</div>`};
  async function call(method,args={},post=false){
    const response=await fetch(`/api/method/${method}`,{method:post?'POST':'GET',headers:{'Content-Type':'application/json'},body:post?JSON.stringify(args):undefined});
    const json=await response.json();
    if(!response.ok||json.exc)throw new Error(typeof json.message==='string'?json.message:'Request failed');
    return json.message;
  }
  async function context(){
    const slug=q('property-slug').value||window.hotelPropertySlug;
    if(!slug)return;
    try{
      const data=await call(`hotel_pms.guest_portal.get_public_booking_context?property_slug=${encodeURIComponent(slug)}`);
      q('property-name').textContent=data.property.public_name;
      q('property-tagline').textContent=data.property.tagline||'';
      q('property-description').textContent=data.property.description||'';
      q('public-policies').textContent=data.property.policies||'';
      q('public-terms').textContent=data.property.terms||'';
      q('public-privacy').textContent=data.property.privacy_notice||'';
      q('public-faq').textContent=data.property.faq||'';
      const map=q('public-map');
      if(data.property.map_url){map.href=data.property.map_url;q('public-info').style.display='block'}else{map.style.display='none'}
      if(data.property.hero_image)q('public-hero').style.backgroundImage=`linear-gradient(rgba(0,0,0,.45),rgba(0,0,0,.45)),url("${encodeURI(data.property.hero_image).replace(/["'()]/g,'')}")`;
      q('property-gallery').innerHTML=(data.property.gallery||[]).map(image=>`<div class="hotel-card"><img src="${esc(image.image)}" alt="${esc(image.caption||data.property.public_name)}"><p>${esc(image.caption||'')}</p></div>`).join('');
    }catch(error){msg(error.message)}
  }
  q('search-btn').onclick=async()=>{
    try{
      msg('Searching…');
      const params=new URLSearchParams({property_slug:q('property-slug').value,arrival_date:q('arrival').value,departure_date:q('departure').value,adults:q('adults').value,children:q('children').value,voucher_code:q('voucher').value});
      const data=await call(`hotel_pms.guest_portal.search_public_availability?${params}`);
      q('results').innerHTML=data.rooms.map((room,index)=>`<div class="hotel-card">${room.image?`<img src="${esc(room.image)}" alt="${esc(room.title)}">`:''}<h3>${esc(room.title)}</h3><p>${esc(room.description||'')}</p><p><b>${Number(room.quote.grand_total).toLocaleString()}</b> total</p><p>${Number(room.available_rooms)} room(s) available</p><button class="hotel-btn choose" data-i="${index}">Choose</button></div>`).join('')||'<p>No room is available.</p>';
      document.querySelectorAll('.choose').forEach(button=>button.onclick=()=>{selected=data.rooms[Number(button.dataset.i)];q('booking').style.display='block';q('quantity').max=selected.available_rooms;msg(`Selected ${selected.title}`,true)});
      if(data.rooms.length)msg('Availability updated.',true);
    }catch(error){msg(error.message)}
  };
  q('book-btn').onclick=async()=>{
    if(!selected)return msg('Choose a room first.');
    try{
      const payload={property_slug:q('property-slug').value,room_type:selected.room_type,arrival_date:q('arrival').value,departure_date:q('departure').value,adults:q('adults').value,children:q('children').value,voucher_code:q('voucher').value,guest_name:q('guest-name').value,email:q('email').value,phone:q('phone').value,quantity:q('quantity').value,company_website:q('company-website').value,accept_terms:q('terms').checked?1:0,accept_privacy:q('privacy').checked?1:0,request_key:crypto.randomUUID()};
      const data=await call('hotel_pms.guest_portal.create_public_booking',{payload},true);
      msg(`Booking ${data.reservation} created. Redirecting…`,true);
      if(data.portal_token)location.href=`/hotel-guest#token=${encodeURIComponent(data.portal_token)}`;
    }catch(error){msg(error.message)}
  };
  context();
})();
