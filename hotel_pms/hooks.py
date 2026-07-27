app_name = "hotel_pms"
app_title = "Hotel PMS"
app_publisher = "The Batu Hotel & Villas"
app_description = "Native hotel property management system integrated with ERPNext"
app_email = "admin@example.com"
app_license = "GPL-3.0"

required_apps = ["erpnext"]

app_include_js = ["/assets/hotel_pms/js/photo_policy.js"]

override_whitelisted_methods = {
    "frappe.handler.upload_file": "hotel_pms.media.upload_file",
    "upload_file": "hotel_pms.media.upload_file",
}

add_to_apps_screen = [
    {
        "name": "hotel_pms",
        "logo": "/assets/hotel_pms/images/logo.svg",
        "title": "Hotel PMS",
        "route": "/app/hotel-front-desk",
        "has_permission": "hotel_pms.api.has_app_permission",
    }
]

doc_events = {
    "File": {
        "before_insert": "hotel_pms.media.validate_file_upload",
    },
    "Payment Entry": {
        "on_submit": "hotel_pms.integrations.payment_entry.on_submit",
        "on_cancel": "hotel_pms.integrations.payment_entry.on_cancel",
    },
    "Sales Invoice": {
        "on_submit": "hotel_pms.integrations.sales_invoice.on_submit",
        "on_cancel": "hotel_pms.integrations.sales_invoice.on_cancel",
        "on_trash": "hotel_pms.integrations.sales_invoice.on_trash",
    },
    "POS Invoice": {
        "on_submit": "hotel_pms.integrations.pos_invoice.on_submit",
        "on_cancel": "hotel_pms.integrations.pos_invoice.on_cancel",
    }
}

scheduler_events = {
    "cron": {
        "*/15 * * * *": ["hotel_pms.front_desk.process_no_show_candidates", "hotel_pms.operations.monitor_operation_slas"],
    },
    "daily": [
        "hotel_pms.tasks.create_housekeeping_tasks",
        "hotel_pms.tasks.create_preventive_maintenance_tasks",
        "hotel_pms.tasks.expire_tentative_group_holds",
        "hotel_pms.tasks.release_group_room_blocks_at_cutoff",
        "hotel_pms.reconcile.reconcile_erpnext_links",
    ]
}

before_install = "hotel_pms.install.before_install"
after_install = "hotel_pms.install.after_install"
