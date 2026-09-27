"""Synchronous client. Use it in Django views, management commands, Celery tasks and scripts."""

import threading
from datetime import date
from http import HTTPStatus
from typing import TypeVar

import httpx
from typing_extensions import Self

from hepsijet import _endpoints as endpoints
from hepsijet._auth import TokenCache, read_token, token_request
from hepsijet._endpoints import DEFAULT_DELETE_REASON, Barcodes, Endpoint
from hepsijet.config import HepsijetConfig
from hepsijet.enums import ImageFormat
from hepsijet.models import (
    ApiResult,
    Area,
    Merchant,
    PickupDay,
    ReturnShipment,
    Shipment,
    ShipmentHistory,
    ShipmentUpdate,
    TrackingSummary,
)

T = TypeVar("T")


class HepsijetClient:
    """Talks to HepsiJET. Create one and reuse it; it's thread-safe.

        with HepsijetClient(config) as hepsijet:
            hepsijet.shipments.create(shipment)
            print(hepsijet.tracking.summary("KRL1000000001"))

    The client gets an auth token when it first needs one, reuses it, and fetches a new
    one before it expires or if HepsiJET rejects it.
    """

    def __init__(self, config: HepsijetConfig, *, http_client: httpx.Client | None = None) -> None:
        self.config = config
        self._http = http_client or httpx.Client(timeout=config.timeout_seconds)
        self._tokens = TokenCache()
        self._token_lock = threading.Lock()

        self.shipments = Shipments(self)
        self.returns = Returns(self)
        self.labels = Labels(self)
        self.tracking = Tracking(self)
        self.service_areas = ServiceAreas(self)
        self.merchants = Merchants(self)

    def send(self, endpoint: Endpoint[T]) -> T:
        """Call one endpoint. If the token was rejected, get a new one and try once more."""
        response = self._http.send(endpoint.to_request(self.config.base_url, self._token()))

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            self._tokens.clear()
            response = self._http.send(endpoint.to_request(self.config.base_url, self._token()))

        return endpoint.read(response)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _token(self) -> str:
        with self._token_lock:
            token = self._tokens.get()
            if token is None:
                token = read_token(self._http.send(token_request(self.config)))
                self._tokens.store(token)
            return token


class Shipments:
    """Create, change and cancel shipments."""

    def __init__(self, client: HepsijetClient) -> None:
        self._client = client

    def create(self, shipment: Shipment) -> ApiResult:
        """Send a new shipment. Parcels over 40 desi are sent as XL automatically."""
        return self._client.send(endpoints.create_shipment(shipment, self._client.config))

    def update(self, change: ShipmentUpdate) -> ApiResult:
        """Change a shipment before pickup. See `hepsijet.models.updates` for the options."""
        return self._client.send(endpoints.update_shipment(change))

    def cancel(self, barcode: str, reason: str = DEFAULT_DELETE_REASON) -> ApiResult:
        """Cancel a shipment. Only works before HepsiJET picks it up."""
        return self._client.send(endpoints.cancel_shipment(barcode, reason))


class Returns:
    """Scheduled returns: HepsiJET picks a parcel up from the customer."""

    def __init__(self, client: HepsijetClient) -> None:
        self._client = client

    def pickup_days(self, *, city: str, town: str, start: date, end: date) -> list[PickupDay]:
        """Days between `start` and `end` when HepsiJET can pick up from this town."""
        return self._client.send(endpoints.return_pickup_days(city, town, start, end))

    def create(self, shipment: ReturnShipment) -> ApiResult:
        return self._client.send(endpoints.create_return(shipment, self._client.config))


class Labels:
    """Shipping labels to print and stick on the box."""

    def __init__(self, client: HepsijetClient) -> None:
        self._client = client

    def pdf(self, barcodes: Barcodes) -> bytes:
        """One PDF file with a page per label."""
        return self._client.send(endpoints.pdf_labels(barcodes))

    def images(
        self, barcodes: Barcodes, image_format: ImageFormat = ImageFormat.PNG
    ) -> list[bytes]:
        """One image file per label."""
        return self._client.send(endpoints.image_labels(barcodes, image_format))

    def zpl(self, barcode: str, parcel_count: int = 1) -> str:
        """ZPL code for Zebra label printers, one label per parcel."""
        return self._client.send(endpoints.zpl_labels(barcode, parcel_count))


class Tracking:
    """Where are my parcels?"""

    def __init__(self, client: HepsijetClient) -> None:
        self._client = client

    def summary(self, barcodes: Barcodes) -> list[TrackingSummary]:
        """Headline status and a public tracking link. Good for customer-facing pages."""
        return self._client.send(endpoints.tracking_summary(barcodes))

    def history(self, barcodes: Barcodes) -> list[ShipmentHistory]:
        """Every scan, the current location and who received it. Good for your admin panel."""
        return self._client.send(endpoints.tracking_history(barcodes))


class ServiceAreas:
    """Places HepsiJET delivers to: cities → towns (ilçe) → districts (mahalle).

    This data rarely changes. Cache it instead of calling on every request.
    """

    def __init__(self, client: HepsijetClient) -> None:
        self._client = client

    def cities(self) -> list[Area]:
        return self._client.send(endpoints.cities())

    def towns(self, city_id: int | str) -> list[Area]:
        return self._client.send(endpoints.towns(city_id))

    def districts(self, town_id: int | str) -> list[Area]:
        return self._client.send(endpoints.districts(town_id))


class Merchants:
    """Marketplace merchants. Skip this if you only ship your own products."""

    def __init__(self, client: HepsijetClient) -> None:
        self._client = client

    def register(self, merchant: Merchant) -> ApiResult:
        """Register a merchant or merchant warehouse. Do this once per merchant."""
        return self._client.send(endpoints.register_merchant(merchant))

    def delete(self, merchant_id: str, reason: str = DEFAULT_DELETE_REASON) -> ApiResult:
        return self._client.send(endpoints.delete_merchant(merchant_id, reason))
