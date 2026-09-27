"""Shipments you send to HepsiJET: normal deliveries and scheduled returns."""

from datetime import date
from typing import Literal

from pydantic import Field, PositiveInt, model_validator
from typing_extensions import Self

from hepsijet.enums import DeliverySlot, DeliveryType, ProductCode
from hepsijet.models.base import Barcode, Desi, InputModel
from hepsijet.models.people import Address, Customer

XL_DESI_THRESHOLD = 40
"""Shipments heavier than this (41+ desi) are XL and go through a separate endpoint."""


class Shipment(InputModel):
    """A parcel going from your warehouse to a customer.

    Standard delivery needs no time slot:

        Shipment(barcode="KRL1000000001", customer=..., address=..., desi=3)

    Same-day and next-day delivery need one:

        Shipment(..., product=ProductCode.SAME_DAY, slot=DeliverySlot.AFTERNOON)
    """

    barcode: Barcode
    customer: Customer
    address: Address = Field(description="Where the parcel is delivered.")
    desi: Desi
    parcel_count: PositiveInt = 1
    product: ProductCode = ProductCode.STANDARD
    slot: DeliverySlot = DeliverySlot.ANY_TIME
    delivery_type: Literal[DeliveryType.RETAIL, DeliveryType.MARKET_PLACE] = DeliveryType.RETAIL
    order_id: str | None = Field(default=None, description="Defaults to the barcode.")
    created_on: date = Field(default_factory=date.today)
    warehouse: Address | None = Field(
        default=None,
        description="Ship from a different warehouse than the one in your HepsijetConfig.",
    )

    @property
    def is_xl(self) -> bool:
        return self.desi > XL_DESI_THRESHOLD

    @model_validator(mode="after")
    def _slot_matches_product(self) -> Self:
        is_standard = self.product is ProductCode.STANDARD
        has_slot = self.slot is not DeliverySlot.ANY_TIME

        if is_standard and has_slot:
            raise ValueError("Standard delivery doesn't use a time slot. Leave `slot` unset.")
        if not is_standard and not has_slot:
            raise ValueError(
                "Same-day and next-day delivery need a time slot: MORNING, AFTERNOON or EVENING."
            )
        return self


class ReturnShipment(InputModel):
    """A scheduled return: HepsiJET picks the parcel up from the customer and brings it to you.

    Call `returns.pickup_days()` first to choose a day when HepsiJET can pick it up.
    """

    barcode: Barcode
    customer: Customer
    pickup_address: Address = Field(description="The customer's address.")
    desi: Desi
    parcel_count: PositiveInt = 1
    order_id: str | None = Field(default=None, description="Defaults to the barcode.")
    created_on: date = Field(default_factory=date.today)
    warehouse: Address | None = Field(
        default=None,
        description="Return to a different warehouse than the one in your HepsijetConfig.",
    )
