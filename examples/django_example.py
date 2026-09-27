"""Using the SDK in a Django project.

Split this into the files named in the comments. It assumes an `Order` model with the
fields used in `ship_order()`; adapt the names to your own models.
"""

# ── settings.py ──────────────────────────────────────────────────────────────────────────
import os

HEPSIJET_USERNAME = os.environ["HEPSIJET_USERNAME"]
HEPSIJET_PASSWORD = os.environ["HEPSIJET_PASSWORD"]
HEPSIJET_COMPANY_NAME = os.environ["HEPSIJET_COMPANY_NAME"]
HEPSIJET_COMPANY_CODE = os.environ["HEPSIJET_COMPANY_CODE"]
HEPSIJET_XDOCK_CODE = os.environ["HEPSIJET_XDOCK_CODE"]
HEPSIJET_BASE_URL = os.environ.get("HEPSIJET_BASE_URL", "https://integration-apitest.hepsijet.com")
HEPSIJET_WAREHOUSE = {
    "address_id": "KRL_DEPO",
    "city": "İstanbul",
    "town": "Kartal",
    "district": "Petrol İş",
    "line": "Kamelya Sk. No:10",
}


# ── shipping/hepsijet.py ─────────────────────────────────────────────────────────────────
# One client for the whole process. It is thread-safe and reuses connections and tokens.
from django.conf import settings  # noqa: E402

from hepsijet import Address, HepsijetClient, HepsijetConfig  # noqa: E402

hepsijet = HepsijetClient(
    HepsijetConfig(
        username=settings.HEPSIJET_USERNAME,
        password=settings.HEPSIJET_PASSWORD,
        company_name=settings.HEPSIJET_COMPANY_NAME,
        company_code=settings.HEPSIJET_COMPANY_CODE,
        xdock_code=settings.HEPSIJET_XDOCK_CODE,
        warehouse=Address(**settings.HEPSIJET_WAREHOUSE),
        base_url=settings.HEPSIJET_BASE_URL,
    )
)


# ── shipping/services.py ─────────────────────────────────────────────────────────────────
from hepsijet import Customer, Shipment  # noqa: E402


def ship_order(order) -> str:  # type: ignore[no-untyped-def]
    """Send a paid order to HepsiJET and return its barcode."""
    barcode = f"KRL{order.id:010d}"

    hepsijet.shipments.create(
        Shipment(
            barcode=barcode,
            order_id=str(order.id),
            customer=Customer(
                customer_id=f"KRL-C-{order.address.id}",
                first_name=order.customer.first_name,
                last_name=order.customer.last_name,
                phone=order.customer.phone,
                email=order.customer.email,
            ),
            address=Address(
                address_id=f"KRL-C-{order.address.id}",
                city=order.address.city,
                town=order.address.town,
                district=order.address.district,
                line=order.address.line,
            ),
            desi=order.total_desi,
            parcel_count=order.box_count,
        )
    )
    return barcode


# ── shipping/views.py ────────────────────────────────────────────────────────────────────
from django.http import HttpRequest, HttpResponse, JsonResponse  # noqa: E402

from hepsijet import ApiError  # noqa: E402


def shipping_label(request: HttpRequest, barcode: str) -> HttpResponse:
    pdf = hepsijet.labels.pdf(barcode)
    return HttpResponse(pdf, content_type="application/pdf")


def tracking(request: HttpRequest, barcode: str) -> JsonResponse:
    [parcel] = hepsijet.tracking.summary(barcode)
    return JsonResponse(parcel.model_dump(mode="json"))


def cancel(request: HttpRequest, barcode: str) -> JsonResponse:
    try:
        hepsijet.shipments.cancel(barcode)
    except ApiError as error:
        return JsonResponse({"error": error.body}, status=409)
    return JsonResponse({"cancelled": barcode})
