ARG FRAPPE_IMAGE=frappe/erpnext:v16
FROM ${FRAPPE_IMAGE}
USER root
COPY --chown=frappe:frappe . /home/frappe/frappe-bench/apps/hotel_pms
RUN /home/frappe/frappe-bench/env/bin/pip install --no-cache-dir -e /home/frappe/frappe-bench/apps/hotel_pms
USER frappe
