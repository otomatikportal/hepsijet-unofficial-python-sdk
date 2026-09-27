"""Every HepsiJET endpoint in one place: method, path, body, and how to read the reply.

Nothing here does I/O. Both the sync and the async client send these same `Endpoint`
objects, so the two clients can't drift apart.
"""

import base64
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Generic, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from hepsijet import _payloads as payloads
from hepsijet.config import HepsijetConfig
from hepsijet.enums import DeliveryType, ImageFormat
from hepsijet.errors import ApiError, UnexpectedResponseError
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
M = TypeVar("M", bound=BaseModel)

DEFAULT_DELETE_REASON = "IPTAL"

Barcodes = str | Iterable[str]
"""One barcode, or several."""


@dataclass(frozen=True)
class Endpoint(Generic[T]):
    """One HTTP call to HepsiJET, and how to turn its reply into a `T`."""

    method: str
    path: str
    parse: Callable[[httpx.Response], T]
    json: Any = None
    params: Mapping[str, str] | None = None

    def to_request(self, base_url: str, token: str) -> httpx.Request:
        return httpx.Request(
            self.method,
            base_url + self.path,
            json=self.json,
            params=self.params,
            headers={"X-Auth-Token": token, "Accept": "application/json"},
        )

    def read(self, response: httpx.Response) -> T:
        if response.is_error:
            raise ApiError(response)
        return self.parse(response)


# --- Shipments ---------------------------------------------------------------------------


def create_shipment(shipment: Shipment, config: HepsijetConfig) -> Endpoint[ApiResult]:
    path = (
        "/delivery/sendDeliveryOrder" if shipment.is_xl else "/delivery/sendDeliveryOrderEnhanced"
    )
    return Endpoint("POST", path, _result, json=payloads.shipment(shipment, config))


def update_shipment(change: ShipmentUpdate) -> Endpoint[ApiResult]:
    return Endpoint("POST", "/delivery-update", _result, json=payloads.shipment_update(change))


def cancel_shipment(barcode: str, reason: str) -> Endpoint[ApiResult]:
    return Endpoint(
        "POST",
        f"/rest/delivery/deleteDeliveryOrder/{_segment(barcode)}",
        _result,
        json=payloads.delete_reason(reason),
    )


# --- Returns -----------------------------------------------------------------------------


def return_pickup_days(city: str, town: str, start: date, end: date) -> Endpoint[list[PickupDay]]:
    params = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "deliveryType": DeliveryType.RETURNED.value,
        "city": city,
        "town": town,
    }
    return Endpoint(
        "GET", "/rest/delivery/findAvailableDeliveryDatesV2", _pickup_days, params=params
    )


def create_return(shipment: ReturnShipment, config: HepsijetConfig) -> Endpoint[ApiResult]:
    return Endpoint(
        "POST",
        "/delivery/sendDeliveryOrderEnhanced",
        _result,
        json=payloads.return_shipment(shipment, config),
    )


# --- Labels ------------------------------------------------------------------------------


def pdf_labels(barcodes: Barcodes) -> Endpoint[bytes]:
    return Endpoint(
        "POST",
        "/delivery/barcodes-label",
        _single_file,
        json={"barcodes": _as_list(barcodes)},
        params={"format": "PDF"},
    )


def image_labels(barcodes: Barcodes, image_format: ImageFormat) -> Endpoint[list[bytes]]:
    return Endpoint(
        "POST",
        "/delivery/barcodes-label",
        _base64_files,
        json={"barcodes": _as_list(barcodes)},
        params={"format": image_format.value},
    )


def zpl_labels(barcode: str, parcel_count: int) -> Endpoint[str]:
    return Endpoint(
        "GET", f"/delivery/generateZplBarcode/{_segment(barcode)}/{parcel_count}", _zpl_text
    )


# --- Tracking ----------------------------------------------------------------------------


def tracking_summary(barcodes: Barcodes) -> Endpoint[list[TrackingSummary]]:
    return Endpoint(
        "POST",
        "/rest/delivery/integration/track",
        _list_of(TrackingSummary),
        json={"barcodes": _as_list(barcodes), "isTrackAdded": True},
    )


def tracking_history(barcodes: Barcodes) -> Endpoint[list[ShipmentHistory]]:
    return Endpoint(
        "POST",
        "/rest/deliveryTransaction/getDeliveryTracking",
        _list_of(ShipmentHistory),
        json={"deliveries": [{"customerDeliveryNo": barcode} for barcode in _as_list(barcodes)]},
    )


# --- Service areas (settlement) ----------------------------------------------------------


def cities() -> Endpoint[list[Area]]:
    return Endpoint("GET", "/settlement/cities", _list_of(Area))


def towns(city_id: int | str) -> Endpoint[list[Area]]:
    return Endpoint("GET", f"/settlement/city/{_segment(city_id)}/towns", _list_of(Area))


def districts(town_id: int | str) -> Endpoint[list[Area]]:
    return Endpoint("GET", f"/settlement/town/{_segment(town_id)}/districts", _list_of(Area))


# --- Marketplace merchants ---------------------------------------------------------------


def register_merchant(merchant: Merchant) -> Endpoint[ApiResult]:
    return Endpoint(
        "POST", "/advance/sendDeliveryAdvance/v2", _result, json=payloads.merchant(merchant)
    )


def delete_merchant(merchant_id: str, reason: str) -> Endpoint[ApiResult]:
    return Endpoint(
        "POST",
        f"/rest/advance/deleteDeliveryAdvance/{_segment(merchant_id)}",
        _result,
        json=payloads.delete_reason(reason),
    )


# --- Reading replies ---------------------------------------------------------------------


def _body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as error:
        raise UnexpectedResponseError("Expected a JSON reply", response) from error


def _data(response: httpx.Response) -> Any:
    """Most replies look like `{"status": "OK", "data": ...}`. Return what's inside `data`."""
    body = _body(response)
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def _result(response: httpx.Response) -> ApiResult:
    body = _body(response)
    if isinstance(body, dict):
        return ApiResult.model_validate(body)
    return ApiResult(data=body)


def _list_of(model: type[M]) -> Callable[[httpx.Response], list[M]]:
    def parse(response: httpx.Response) -> list[M]:
        items = _data(response)
        if not isinstance(items, list):
            raise UnexpectedResponseError("Expected a list", response)
        return [model.model_validate(item) for item in items]

    return parse


def _pickup_days(response: httpx.Response) -> list[PickupDay]:
    """Flatten data[city].towns[town].xDock[branch].days[day] into one list of days."""
    days: list[PickupDay] = []
    for city in _data(response) or []:
        for town in city.get("towns", []):
            for branch in town.get("xDock", []):
                for day in branch.get("days", []):
                    days.append(
                        PickupDay.model_validate(
                            {
                                "date": day.get("date"),
                                "limit": day.get("returnedLimit"),
                                "branch": branch.get("xDockName"),
                            }
                        )
                    )
    return days


def _base64_files(response: httpx.Response) -> list[bytes]:
    data = _data(response)
    encoded = [data] if isinstance(data, str) else data
    if not isinstance(encoded, list) or not all(isinstance(item, str) for item in encoded):
        raise UnexpectedResponseError("Expected Base64-encoded label data", response)
    return [base64.b64decode(item) for item in encoded]


def _single_file(response: httpx.Response) -> bytes:
    files = _base64_files(response)
    if not files:
        raise UnexpectedResponseError("Expected one PDF file, got none", response)
    return files[0]


def _zpl_text(response: httpx.Response) -> str:
    if "json" not in response.headers.get("content-type", ""):
        return response.text

    data = _data(response)
    if isinstance(data, str):
        return data
    if isinstance(data, list) and all(isinstance(label, str) for label in data):
        return "\n".join(data)
    raise UnexpectedResponseError("Expected ZPL text", response)


def _as_list(barcodes: Barcodes) -> list[str]:
    return [barcodes] if isinstance(barcodes, str) else list(barcodes)


def _segment(value: int | str) -> str:
    """Make a value safe to put inside a URL path."""
    return quote(str(value), safe="")
