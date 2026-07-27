app_name = "hotel_pms"
app_title = "Hotel PMS"
app_publisher = "The Batu Hotel & Villas"
app_description = "Native hotel property management system integrated with ERPNext"
app_email = "admin@example.com"
app_license = "GPL-3.0"

required_apps = ["erpnext"]

add_to_apps_screen = [
    {
        "name": "hotel_pms",
        "logo": "/assets/hotel_pms/images/logo.svg",
        "title": "Hotel PMS",
        "route": "/desk/hotel-reservation",
        "has_permission": "hotel_pms.api.has_app_permission",
    }
]

doc_events = {
    "Sales Invoice": {
        "on_submit": "hotel_pms.integrations.sales_invoice.on_submit",
        "on_cancel": "hotel_pms.integrations.sales_invoice.on_cancel",
    },
    "POS Invoice": {
        "on_submit": "hotel_pms.integrations.pos_invoice.on_submit",
        "on_cancel": "hotel_pms.integrations.pos_invoice.on_cancel",
    }
}

scheduler_events = {
    "daily": [
        "hotel_pms.tasks.create_housekeeping_tasks",
        "hotel_pms.tasks.create_preventive_maintenance_tasks",
    ]
}

before_install = "hotel_pms.install.before_install"
after_install = "hotel_pms.install.after_install"
