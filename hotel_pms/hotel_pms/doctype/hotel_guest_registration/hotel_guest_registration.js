
frappe.ui.form.on("Hotel Guest Registration", {
  refresh(frm) {
    hotel_pms.photo_policy.apply(frm, ["id_file", "address_proof_file"]);
    if (!frm.is_new()) {
      frm.add_custom_button(__("Print Registration Card"), () => {
        const url = frappe.urllib.get_full_url(`/printview?doctype=Hotel%20Guest%20Registration&name=${encodeURIComponent(frm.doc.name)}&format=Hotel%20Guest%20Registration%20Card&no_letterhead=0`);
        window.open(url, "_blank");
      });
      if (frm.doc.id_retention_mode !== "Do Not Upload") {
        frm.add_custom_button(__("Upload ID Securely"), () => secureUpload(frm, "id"), __("Documents"));
        frm.add_custom_button(__("Upload Address Proof Securely"), () => secureUpload(frm, "address"), __("Documents"));
        if (frm.doc.id_file || frm.doc.address_proof_file) {
          frm.add_custom_button(__("Purge Documents"), async () => {
            await frappe.call({method:"hotel_pms.media.purge_guest_documents_for_staff",args:{registration:frm.doc.name,reason:"Manual verified purge"},freeze:true});
            frm.reload_doc();
          }, __("Documents"));
        }
      }
    }
  },
});

function secureUpload(frm, kind) {
  const dialog=new frappe.ui.Dialog({title:kind==="id"?__("Upload ID Securely"):__("Upload Address Proof Securely"),fields:[
    {fieldname:"file_html",fieldtype:"HTML",options:`<input type="file" class="form-control secure-doc-file" accept="image/jpeg,image/png,image/webp">`}
  ],primary_action_label:__("Upload"),primary_action:async()=>{
    const file=dialog.$wrapper.find('.secure-doc-file')[0].files[0];
    if(!file)return frappe.msgprint(__("Choose an image file."));
    const image_data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
    await frappe.call({method:"hotel_pms.media.upload_guest_document_for_staff",args:{registration:frm.doc.name,kind,image_data,filename:file.name},freeze:true});
    dialog.hide();frm.reload_doc();
  }});dialog.show();
}
