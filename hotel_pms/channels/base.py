from __future__ import annotations

from typing import Protocol


class HotelDistributionAdapter(Protocol):
    """Provider transport contract.

    Adapters translate protocols. Availability, pricing, reservation validation,
    idempotency, audit and ERPNext consequences stay in hotel_pms.distribution.
    """

    provider: str

    def test_connection(self, connection) -> dict: ...
    def push_ari(self, connection, snapshot: list[dict]) -> dict: ...
    def parse_webhook(self, connection, payload: dict) -> list[dict]: ...
    def acknowledge_booking(self, connection, event: dict, reservation: str) -> dict: ...
