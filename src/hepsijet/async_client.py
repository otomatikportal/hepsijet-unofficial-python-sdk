"""Asynchronous client. Use it in FastAPI and other asyncio code.

It mirrors `HepsijetClient` method for method; only `await` is added.
"""

import asyncio
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


class AsyncHepsijetClient:
    """Talks to HepsiJET without blocking the event loop. Create one and reuse it.

    async with AsyncHepsijetClient(config) as hepsijet:
        await hepsijet.shipments.create(shipment)
        print(await hepsijet.tracking.summary("KRL1000000001"))
    """

    def __init__(
        self, config: HepsijetConfig, *, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self.config = config
        self._http = http_client or httpx.AsyncClient(timeout=config.timeout_seconds)
        self._tokens = TokenCache()
        self._token_lock = asyncio.Lock()

        self.shipments = AsyncShipments(self)
        self.returns = AsyncReturns(self)
        self.labels = AsyncLabels(self)
        self.tracking = AsyncTracking(self)
        self.service_areas = AsyncServiceAreas(self)
        self.merchants = AsyncMerchants(self)

    async def send(self, endpoint: Endpoint[T]) -> T:
        """Call one endpoint. If the token was rejected, get a new one and try once more."""
        response = await self._http.send(
            endpoint.to_request(self.config.base_url, await self._token())
        )

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            self._tokens.clear()
            response = await self._http.send(
                endpoint.to_request(self.config.base_url, await self._token())
            )

        return endpoint.read(response)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _token(self) -> str:
        async with self._token_lock:
            token = self._tokens.get()
            if token is None:
                token = read_token(await self._http.send(token_request(self.config)))
                self._tokens.store(token)
            return token


class AsyncShipments:
    """Create, change and cancel shipments."""

    def __init__(self, client: AsyncHepsijetClient) -> None:
        self._client = client

    async def create(self, shipment: Shipment) -> ApiResult:
        """Send a new shipment. Parcels over 40 desi are sent as XL automatically."""
        return await self._client.send(endpoints.create_shipment(shipment, self._client.config))

    async def update(self, change: ShipmentUpdate) -> ApiResult:
        """Change a shipment before pickup. See `hepsijet.models.updates` for the options."""
        return await self._client.send(endpoints.update_shipment(change))

    async def cancel(self, barcode: str, reason: str = DEFAULT_DELETE_REASON) -> ApiResult:
        """Cancel a shipment. Only works before HepsiJET picks it up."""
        return await self._client.send(endpoints.cancel_shipment(barcode, reason))


class AsyncReturns:
    """Scheduled returns: HepsiJET picks a parcel up from the customer."""

    def __init__(self, client: AsyncHepsijetClient) -> None:
        self._client = client

    async def pickup_days(self, *, city: str, town: str, start: date, end: date) -> list[PickupDay]:
        """Days between `start` and `end` when HepsiJET can pick up from this town."""
        return await self._client.send(endpoints.return_pickup_days(city, town, start, end))

    async def create(self, shipment: ReturnShipment) -> ApiResult:
        return await self._client.send(endpoints.create_return(shipment, self._client.config))


class AsyncLabels:
    """Shipping labels to print and stick on the box."""

    def __init__(self, client: AsyncHepsijetClient) -> None:
        self._client = client

    async def pdf(self, barcodes: Barcodes) -> bytes:
        """One PDF file with a page per label."""
        return await self._client.send(endpoints.pdf_labels(barcodes))

    async def images(
        self, barcodes: Barcodes, image_format: ImageFormat = ImageFormat.PNG
    ) -> list[bytes]:
        """One image file per label."""
        return await self._client.send(endpoints.image_labels(barcodes, image_format))

    async def zpl(self, barcode: str, parcel_count: int = 1) -> str:
        """ZPL code for Zebra label printers, one label per parcel."""
        return await self._client.send(endpoints.zpl_labels(barcode, parcel_count))


class AsyncTracking:
    """Where are my parcels?"""

    def __init__(self, client: AsyncHepsijetClient) -> None:
        self._client = client

    async def summary(self, barcodes: Barcodes) -> list[TrackingSummary]:
        """Headline status and a public tracking link. Good for customer-facing pages."""
        return await self._client.send(endpoints.tracking_summary(barcodes))

    async def history(self, barcodes: Barcodes) -> list[ShipmentHistory]:
        """Every scan, the current location and who received it. Good for your admin panel."""
        return await self._client.send(endpoints.tracking_history(barcodes))


class AsyncServiceAreas:
    """Places HepsiJET delivers to: cities → towns (ilçe) → districts (mahalle).

    This data rarely changes. Cache it instead of calling on every request.
    """

    def __init__(self, client: AsyncHepsijetClient) -> None:
        self._client = client

    async def cities(self) -> list[Area]:
        return await self._client.send(endpoints.cities())

    async def towns(self, city_id: int | str) -> list[Area]:
        return await self._client.send(endpoints.towns(city_id))

    async def districts(self, town_id: int | str) -> list[Area]:
        return await self._client.send(endpoints.districts(town_id))


class AsyncMerchants:
    """Marketplace merchants. Skip this if you only ship your own products."""

    def __init__(self, client: AsyncHepsijetClient) -> None:
        self._client = client

    async def register(self, merchant: Merchant) -> ApiResult:
        """Register a merchant or merchant warehouse. Do this once per merchant."""
        return await self._client.send(endpoints.register_merchant(merchant))

    async def delete(self, merchant_id: str, reason: str = DEFAULT_DELETE_REASON) -> ApiResult:
        return await self._client.send(endpoints.delete_merchant(merchant_id, reason))
