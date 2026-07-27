from __future__ import annotations


class AdapterNotCertified(RuntimeError):
    pass


class NormalizedJsonAdapter:
    provider = "Generic JSON"

    def test_connection(self, connection) -> dict:
        return {"ok": True, "detail": "Normalized JSON webhook is available; transport authentication is connection-scoped."}

    def push_ari(self, connection, snapshot: list[dict]) -> dict:
        raise AdapterNotCertified("Generic JSON has no outbound ARI transport. Use the API response or build a certified provider adapter.")

    def parse_webhook(self, connection, payload: dict) -> list[dict]:
        rows = payload.get("events") if isinstance(payload.get("events"), list) else [payload]
        return [dict(row) for row in rows if isinstance(row, dict)]

    def acknowledge_booking(self, connection, event: dict, reservation: str) -> dict:
        return {"ok": True, "detail": "No provider acknowledgement required."}


class CertificationAdapter:
    def __init__(self, provider: str):
        self.provider = provider

    def _blocked(self):
        raise AdapterNotCertified(
            f"{self.provider} transport is registered as Adapter, not Shipped. Activate only after partner credentials, field mapping and certification tests are recorded."
        )

    def test_connection(self, connection) -> dict: self._blocked()
    def push_ari(self, connection, snapshot: list[dict]) -> dict: self._blocked()
    def parse_webhook(self, connection, payload: dict) -> list[dict]: self._blocked()
    def acknowledge_booking(self, connection, event: dict, reservation: str) -> dict: self._blocked()


_ADAPTERS = {
    "Generic JSON": NormalizedJsonAdapter(),
    "Channex": CertificationAdapter("Channex"),
    "STAAH": CertificationAdapter("STAAH"),
    "AioSell": CertificationAdapter("AioSell"),
}


def provider_for(provider: str):
    return _ADAPTERS.get(provider) or CertificationAdapter(provider or "Custom")
