import frappe
from frappe.tests import IntegrationTestCase
class TestPlatformIntegration(IntegrationTestCase):
 def test_api_schema_is_packaged(self):
  from pathlib import Path
  import hotel_pms
  assert (Path(hotel_pms.__file__).resolve().parents[1]/'docs'/'openapi-v1.json').exists()
