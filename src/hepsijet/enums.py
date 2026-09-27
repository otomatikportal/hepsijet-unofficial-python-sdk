"""Fixed values used by the HepsiJET API, with readable names."""

from enum import Enum


class DeliveryType(str, Enum):
    """Who is shipping, and why."""

    RETAIL = "RETAIL"
    """You ship your own products (perakende)."""

    MARKET_PLACE = "MARKET_PLACE"
    """A merchant on your marketplace ships their products (pazar yeri)."""

    RETURNED = "RETURNED"
    """A scheduled return picked up from the customer (randevulu iade)."""


class ProductCode(str, Enum):
    """How fast the parcel should arrive."""

    STANDARD = "HX_STD"
    SAME_DAY = "HX_SD"
    NEXT_DAY = "HX_ND"


class DeliverySlot(int, Enum):
    """Delivery time window. Only same-day and next-day deliveries use a slot."""

    ANY_TIME = 0
    """No specific window. Always use this with standard delivery."""

    MORNING = 1
    """09:00 to 13:00"""

    AFTERNOON = 2
    """13:00 to 18:00"""

    EVENING = 3
    """18:00 to 23:00"""


class ImageFormat(str, Enum):
    """Image formats for shipping labels. (Use `labels.pdf()` for PDF.)"""

    PNG = "PNG"
    JPEG = "JPEG"


class TrackingStatus(str, Enum):
    """The three headline statuses returned by `tracking.summary()`."""

    ACCEPTED = "ACCEPTED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"


class DeliveryStatus(str, Enum):
    """Detailed statuses returned by `tracking.history()`, roughly in the order they happen."""

    COLLECTED = "COLLECTED"
    TRANSFERRING_COLLECT = "TRANSFERRING_COLLECT"
    READY = "READY"
    WAITING_FOR_DISPATCH = "WAITING_FOR_DISPATCH"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    DELETED = "DELETED"
