"""A typed, readable Python SDK for the HepsiJET cargo API.

    from hepsijet import HepsijetClient, HepsijetConfig, Shipment

Use `HepsijetClient` in sync code (Django) and `AsyncHepsijetClient` in async code (FastAPI).
"""

from hepsijet.async_client import AsyncHepsijetClient
from hepsijet.client import HepsijetClient
from hepsijet.config import TEST_BASE_URL, HepsijetConfig
from hepsijet.enums import (
    DeliverySlot,
    DeliveryStatus,
    DeliveryType,
    ImageFormat,
    ProductCode,
    TrackingStatus,
)
from hepsijet.errors import (
    ApiError,
    AuthenticationError,
    HepsijetError,
    UnexpectedResponseError,
)
from hepsijet.models import (
    Address,
    AddressUpdate,
    ApiResult,
    Area,
    Contact,
    Customer,
    CustomerUpdate,
    DeliveryOptionUpdate,
    HistoryEvent,
    Merchant,
    ParcelUpdate,
    PickupDay,
    RecipientUpdate,
    ReturnShipment,
    Shipment,
    ShipmentHistory,
    ShipmentUpdate,
    TrackingEvent,
    TrackingSummary,
)

__version__ = "0.1.0"

__all__ = [
    "TEST_BASE_URL",
    "Address",
    "AddressUpdate",
    "ApiError",
    "ApiResult",
    "Area",
    "AsyncHepsijetClient",
    "AuthenticationError",
    "Contact",
    "Customer",
    "CustomerUpdate",
    "DeliveryOptionUpdate",
    "DeliverySlot",
    "DeliveryStatus",
    "DeliveryType",
    "HepsijetClient",
    "HepsijetConfig",
    "HepsijetError",
    "HistoryEvent",
    "ImageFormat",
    "Merchant",
    "ParcelUpdate",
    "PickupDay",
    "ProductCode",
    "RecipientUpdate",
    "ReturnShipment",
    "Shipment",
    "ShipmentHistory",
    "ShipmentUpdate",
    "TrackingEvent",
    "TrackingStatus",
    "TrackingSummary",
    "UnexpectedResponseError",
]
