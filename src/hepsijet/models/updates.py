"""Changes you can make to a shipment after creating it.

Every change must be sent before HepsiJET picks the parcel up from your warehouse.
The only exception is desi, which can change until the parcel is delivered.
"""

from datetime import datetime, time

from pydantic import EmailStr, Field

from hepsijet.enums import DeliverySlot, ProductCode
from hepsijet.models.base import Barcode, Desi, InputModel
from hepsijet.models.people import Address, Customer


class ParcelUpdate(InputModel):
    """Change how many boxes there are, and each box's desi.

    ParcelUpdate(barcode="KRL1000000001", desi_per_parcel=[1, 5, 3])  # 3 boxes
    """

    barcode: Barcode
    desi_per_parcel: list[Desi] = Field(min_length=1)

    @property
    def parcel_count(self) -> int:
        return len(self.desi_per_parcel)


class DeliveryOptionUpdate(InputModel):
    """Switch between standard, same-day and next-day delivery.

    Moving from standard to same-day, send `delivery_date`, `slot` and the time window.
    Moving back to standard, send `delivery_date`.
    Switching between same-day and next-day, `product` alone is enough.
    """

    barcode: Barcode
    product: ProductCode
    delivery_date: datetime | None = None
    slot: DeliverySlot | None = None
    window_start: time | None = None
    window_end: time | None = None


class CustomerUpdate(InputModel):
    """Replace the customer's details on a shipment."""

    barcode: Barcode
    customer: Customer


class AddressUpdate(InputModel):
    """Replace the delivery address on a shipment."""

    barcode: Barcode
    address: Address


class RecipientUpdate(InputModel):
    """Change who physically receives the parcel (e.g. a neighbour or colleague)."""

    barcode: Barcode
    name: str = Field(min_length=1)
    phone: str = Field(min_length=10)
    second_phone: str | None = None
    email: EmailStr | None = None


ShipmentUpdate = (
    ParcelUpdate | DeliveryOptionUpdate | CustomerUpdate | AddressUpdate | RecipientUpdate
)
"""Any change accepted by `shipments.update()`."""
