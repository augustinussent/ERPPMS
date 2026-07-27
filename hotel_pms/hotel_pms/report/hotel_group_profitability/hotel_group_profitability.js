frappe.query_reports["Hotel Group Profitability"] = {
    filters: [
        {
            fieldname: "property",
            label: __("Property"),
            fieldtype: "Link",
            options: "Hotel Property"
        },
        {
            fieldname: "from_date",
            label: __("Arrival From"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("Arrival To"),
            fieldtype: "Date"
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nInquiry\nTentative\nConfirmed\nEvent Active\nCompleted\nClosed\nCancelled"
        }
    ]
};
