# hepsijet

A typed, readable Python SDK for the [HepsiJET cargo API](https://developers.hepsiburada.com/tr/companies/hepsijet).

- **Sync and async clients** with identical methods: `HepsijetClient` for Django, `AsyncHepsijetClient` for FastAPI.
- **Typed models** (pydantic v2). Your editor autocompletes every field, and mistakes are caught when you build the model, before anything reaches HepsiJET.
- **Automatic tokens.** The client logs in, caches the token and refreshes it for you.
- **Python names, not wire names.** You write `Shipment(barcode=..., desi=3)`, and the SDK sends `customerDeliveryNo`, `deliverySlotOriginal` and the rest.

```bash
pip install ./hepsijet-sdk          # or: pip install hepsijet-0.1.0-py3-none-any.whl
```

Requires Python 3.10+.

---

## 1. Configure once

HepsiJET gives you every value below except `warehouse`, which must match the warehouse
address you registered with them.

```python
from hepsijet import Address, HepsijetConfig

config = HepsijetConfig(
    username="...",
    password="...",
    company_name="KARLOG",  # from HepsiJET
    company_code="KRL",  # from HepsiJET
    xdock_code="KRL_IST",  # from HepsiJET
    warehouse=Address(
        address_id="KRL_DEPO",  # from HepsiJET
        city="İstanbul",
        town="Kartal",
        district="Petrol İş",
        line="Kamelya Sk. No:10",
    ),
    # base_url="https://...",         # live URL from HepsiJET. The default is the test server.
)
```

## 2. Everything the client can do

```python
from hepsijet import HepsijetClient

hepsijet = HepsijetClient(config)  # create once, reuse everywhere (thread-safe)
```

| Task | Call | Returns |
|---|---|---|
| Create a shipment (auto-XL above 40 desi) | `hepsijet.shipments.create(shipment)` | `ApiResult` |
| Change a shipment before pickup | `hepsijet.shipments.update(change)` | `ApiResult` |
| Cancel a shipment before pickup | `hepsijet.shipments.cancel(barcode)` | `ApiResult` |
| Days available for a return pickup | `hepsijet.returns.pickup_days(city=, town=, start=, end=)` | `list[PickupDay]` |
| Create a scheduled return | `hepsijet.returns.create(return_shipment)` | `ApiResult` |
| Label as PDF | `hepsijet.labels.pdf(barcodes)` | `bytes` |
| Labels as PNG/JPEG | `hepsijet.labels.images(barcodes, ImageFormat.PNG)` | `list[bytes]` |
| Label for Zebra printers | `hepsijet.labels.zpl(barcode, parcel_count)` | `str` |
| Customer-facing status + link | `hepsijet.tracking.summary(barcodes)` | `list[TrackingSummary]` |
| Full scan history | `hepsijet.tracking.history(barcodes)` | `list[ShipmentHistory]` |
| Cities / towns / districts served | `hepsijet.service_areas.cities()` · `.towns(city_id)` · `.districts(town_id)` | `list[Area]` |
| Register a marketplace merchant | `hepsijet.merchants.register(merchant)` | `ApiResult` |
| Delete a marketplace merchant | `hepsijet.merchants.delete(merchant_id)` | `ApiResult` |

`barcodes` can be a single string or a list of strings.

### Create a shipment

```python
from hepsijet import Address, Customer, DeliverySlot, ProductCode, Shipment

shipment = Shipment(
    barcode="KRL1000000001",  # your unique number, 9 to 16 characters
    customer=Customer(
        customer_id="KRL-C-551",
        first_name="Ayşe",
        last_name="Yılmaz",
        phone="5321112233",
        email="ayse@example.com",
    ),
    address=Address(
        address_id="KRL-C-551",
        city="Bursa",
        town="Osmangazi",
        district="Güneştepe",
        line="771 Sk. No:1 D:5",
    ),
    desi=3,
    parcel_count=1,
)
hepsijet.shipments.create(shipment)

# Same-day, 13:00–18:00
Shipment(..., product=ProductCode.SAME_DAY, slot=DeliverySlot.AFTERNOON)
```

Invalid combinations fail right away, with a clear message:

```python
Shipment(..., product=ProductCode.SAME_DAY)
# ValidationError: Same-day and next-day delivery need a time slot: MORNING, AFTERNOON or EVENING.
```

### Change or cancel

```python
from hepsijet import ParcelUpdate, DeliveryOptionUpdate, RecipientUpdate, ProductCode

hepsijet.shipments.update(ParcelUpdate(barcode="KRL1000000001", desi_per_parcel=[1, 5, 3]))
hepsijet.shipments.update(
    DeliveryOptionUpdate(barcode="KRL1000000001", product=ProductCode.NEXT_DAY)
)
hepsijet.shipments.update(
    RecipientUpdate(barcode="KRL1000000001", name="Ali Can", phone="5361112233")
)
# Also available: CustomerUpdate, AddressUpdate

hepsijet.shipments.cancel("KRL1000000001")
```

### Labels

```python
pdf_bytes = hepsijet.labels.pdf(["KRL1000000001", "KRL1000000002"])
zpl_code = hepsijet.labels.zpl("KRL1000000001", parcel_count=2)
```

### Tracking

```python
for parcel in hepsijet.tracking.summary(["KRL1000000001", "KRL1000000002"]):
    print(
        parcel.barcode,
        parcel.latest.status if parcel.latest else "not picked up",
        parcel.tracking_url,
    )

[history] = hepsijet.tracking.history("KRL1000000001")
for event in history.events:
    print(event.happened_at, event.delivery_status, event.location, event.description)
```

### Scheduled returns

```python
from datetime import date, timedelta
from hepsijet import ReturnShipment

days = hepsijet.returns.pickup_days(
    city="İstanbul", town="Kartal", start=date.today(), end=date.today() + timedelta(days=7)
)

hepsijet.returns.create(
    ReturnShipment(
        barcode="KRL-R-100000001",
        customer=customer,
        pickup_address=customer_address,  # the SDK swaps sender and recipient for you
        desi=2,
    )
)
```

### Errors

```python
from hepsijet import HepsijetError, ApiError, AuthenticationError

try:
    hepsijet.shipments.cancel("KRL1000000001")
except AuthenticationError:
    ...  # wrong username or password
except ApiError as error:
    print(error.status_code, error.body)  # HepsiJET said no (e.g. already picked up)
except HepsijetError:
    ...  # anything else from this SDK
```

Invalid input raises `pydantic.ValidationError` when you build the model, before any request is sent.

---

## 3. Django

Create the client once, in a module, and import it wherever you need it.

```python
# shipping/hepsijet.py
from django.conf import settings
from hepsijet import Address, HepsijetClient, HepsijetConfig

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
```

```python
# shipping/views.py
from django.http import HttpResponse, JsonResponse
from .hepsijet import hepsijet


def label(request, barcode: str) -> HttpResponse:
    return HttpResponse(hepsijet.labels.pdf(barcode), content_type="application/pdf")


def track(request, barcode: str) -> JsonResponse:
    [parcel] = hepsijet.tracking.summary(barcode)
    return JsonResponse(parcel.model_dump(mode="json"))
```

See [`examples/django_example.py`](examples/django_example.py) for creating a shipment from an order model.

## 4. FastAPI

Open the async client when the app starts and close it on shutdown.

```python
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from hepsijet import AsyncHepsijetClient, TrackingSummary


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncHepsijetClient(load_config()) as client:
        app.state.hepsijet = client
        yield


app = FastAPI(lifespan=lifespan)


def get_hepsijet(request: Request) -> AsyncHepsijetClient:
    return request.app.state.hepsijet


Hepsijet = Annotated[AsyncHepsijetClient, Depends(get_hepsijet)]


@app.get("/shipments/{barcode}/tracking")
async def track(barcode: str, hepsijet: Hepsijet) -> TrackingSummary:
    [parcel] = await hepsijet.tracking.summary(barcode)
    return parcel


@app.get("/shipments/{barcode}/label.pdf")
async def label(barcode: str, hepsijet: Hepsijet) -> Response:
    return Response(await hepsijet.labels.pdf(barcode), media_type="application/pdf")
```

Because the models are pydantic, you can use them directly as FastAPI request and response bodies.
See [`examples/fastapi_example.py`](examples/fastapi_example.py).

---

## 5. How the code is organised

```
src/hepsijet/
├── client.py          HepsijetClient: the sync client and its resource groups
├── async_client.py    AsyncHepsijetClient: the same, with async/await
├── config.py          HepsijetConfig: your account settings
├── enums.py           ProductCode, DeliverySlot, DeliveryType, ...
├── errors.py          HepsijetError and subclasses
├── models/            What you send (Shipment, updates, ...) and what you get back
├── _endpoints.py      Every endpoint: method, path, and how to read the reply   ← mirrors the API docs
├── _payloads.py       Python models → HepsiJET JSON bodies                     ← the only place wire field names live
└── _auth.py           Token fetching and caching
```

Both clients send the same `Endpoint` objects, so the sync and async behaviour can't drift
apart. To add a new endpoint, add a function to `_endpoints.py` and one method to each client.

## 6. Unverified details in HepsiJET's docs

HepsiJET's documentation leaves some things out. The SDK handles each one leniently, but
check these against the **test server** before going live:

1. **Reply shapes.** Most replies aren't documented. Response models keep every field they
   don't declare in `model_extra`, so nothing is lost. `Area` (service areas) and the label
   replies are the least certain.
2. **Token reply.** The SDK looks for the token at `data.token`, then `token`.
3. **`currentXDock` placement.** The docs show it at the top level for normal shipments and
   inside `delivery` for XL ones. The SDK sends it at the top level for both.
4. **Merchant registration.** The docs' example body is a copy of the shipment example; the
   SDK follows the field-by-field description instead.

## Development

```bash
pip install -e ".[dev]"
pytest
mypy
ruff check .
```
