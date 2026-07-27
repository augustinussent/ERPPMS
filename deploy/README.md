# Production-gate container build
Pin `FRAPPE_IMAGE` to an exact tested ERPNext v16 release or digest. Do not deploy `latest`.

```bash
docker build --build-arg FRAPPE_IMAGE=frappe/erpnext:<PINNED_V16_TAG> -t hotel-pms:1.0.0-rc1 -f deploy/Dockerfile .
```
The image build proves packaging only. Production approval still requires migration, restore, security, performance, and accounting evidence in a `Hotel Production Gate Run`.

Set the same digest inside the runtime environment so the gate can compare it:

```bash
HOTEL_PMS_IMAGE_DIGEST=sha256:<digest>
# or site_config.json: {"hotel_pms_image_digest": "sha256:<digest>"}
```
