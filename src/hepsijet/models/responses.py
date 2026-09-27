"""What HepsiJET sends back.

Every response model keeps fields it doesn't declare (in `model_extra`), and most declared
fields are optional. HepsiJET's docs describe only some responses, so the SDK is lenient
instead of failing on a field it didn't expect.
"""

from datetime import date, datetime
from typing import Any

from pydantic import AliasChoices, Field

from hepsijet.enums import DeliveryStatus, TrackingStatus
from hepsijet.models.base import ResponseModel


class ApiResult(ResponseModel):
    """A generic reply, e.g. after creating or cancelling a shipment."""

    status: str | None = None
    message: str | None = None
    data: Any = None

    @property
    def ok(self) -> bool:
        return self.status is None or self.status.upper() == "OK"


class Area(ResponseModel):
    """A city, town (ilçe) or district (mahalle) that HepsiJET delivers to.

    Not verified against a live response yet. If `id` or `name` is None, look at `model_extra`.
    """

    id: int | str | None = Field(
        default=None, validation_alias=AliasChoices("id", "cityId", "townId", "districtId")
    )
    name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("name", "cityName", "townName", "districtName"),
    )


class PickupDay(ResponseModel):
    """A day when HepsiJET can pick up a return."""

    day: date = Field(alias="date")
    limit: int | None = Field(default=None, description="How many returns fit that day.")
    branch: str | None = Field(default=None, description="The HepsiJET branch doing the pickup.")


class TrackingEvent(ResponseModel):
    """One step in `TrackingSummary.events`."""

    status: TrackingStatus | str | None = Field(
        default=None, alias="integrationStatus", union_mode="left_to_right"
    )
    happened_at: datetime | None = Field(default=None, alias="transactionDate")
    location: str | None = Field(default=None, alias="transactionLocation")
    delivered_to: str | None = Field(default=None, alias="deliveredPerson")


class TrackingSummary(ResponseModel):
    """A shipment's headline status and public tracking link. Show this to customers."""

    barcode: str
    tracking_url: str | None = None
    events: list[TrackingEvent] = Field(default_factory=list, alias="details")

    @property
    def latest(self) -> TrackingEvent | None:
        return self.events[-1] if self.events else None

    @property
    def is_delivered(self) -> bool:
        return any(event.status == TrackingStatus.DELIVERED for event in self.events)


class HistoryEvent(ResponseModel):
    """One scan in `ShipmentHistory.events`."""

    delivery_status: DeliveryStatus | str | None = Field(default=None, union_mode="left_to_right")
    operation_status: str | None = None
    transaction_type: str | None = None
    happened_at: datetime | None = Field(default=None, alias="transactionDateTime")
    location: str | None = None
    description: str | None = Field(default=None, alias="transaction")
    non_delivery_reason: str | None = None
    delivered_person: str | None = None


class ShipmentHistory(ResponseModel):
    """Everything HepsiJET knows about a shipment. Use this in your admin panel."""

    barcode: str
    delivery_status: DeliveryStatus | str | None = Field(default=None, union_mode="left_to_right")
    delivery_type: str | None = None
    product_name: str | None = None
    current_location: str | None = None
    last_transaction: str | None = None
    arrival_branch: str | None = None
    sender: str | None = None
    recipient_name: str | None = None
    delivered_person: str | None = None
    delivered_date: datetime | None = None
    delivery_date_promised: datetime | None = None
    events: list[HistoryEvent] = Field(default_factory=list, alias="transactions")

    @property
    def is_delivered(self) -> bool:
        return self.delivery_status == DeliveryStatus.DELIVERED
