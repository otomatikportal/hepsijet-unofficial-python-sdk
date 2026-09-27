import asyncio
import base64
from datetime import date

import httpx
import pytest
from conftest import FakeHepsijet
from pydantic import ValidationError

from hepsijet import (
    Address,
    ApiError,
    AsyncHepsijetClient,
    AuthenticationError,
    Customer,
    DeliverySlot,
    HepsijetClient,
    HepsijetConfig,
    ParcelUpdate,
    ProductCode,
    RecipientUpdate,
    ReturnShipment,
    Shipment,
    TrackingStatus,
)

# --- Auth ------------------------------------------------------------------------------


def test_token_is_fetched_once_and_reused(client: HepsijetClient, fake: FakeHepsijet) -> None:
    client.shipments.cancel("KRL1000000001")
    client.shipments.cancel("KRL1000000002")

    assert fake.issued_tokens == 1
    assert fake.requests[0].headers["Authorization"].startswith("Basic ")


def test_rejected_token_is_refreshed_and_request_retried(
    client: HepsijetClient, fake: FakeHepsijet
) -> None:
    client.shipments.cancel("KRL1000000001")
    fake.valid_token = "expired-on-the-server"  # the client's cached token is now rejected

    result = client.shipments.cancel("KRL1000000001")

    assert result.ok
    assert fake.issued_tokens == 2


def test_bad_credentials_raise_authentication_error(config: HepsijetConfig) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(401))
    client = HepsijetClient(config, http_client=httpx.Client(transport=transport))

    with pytest.raises(AuthenticationError):
        client.shipments.cancel("KRL1000000001")


def test_http_errors_raise_api_error(client: HepsijetClient, fake: FakeHepsijet) -> None:
    fake.reply("/delivery-update", {"message": "Already collected"}, status=400)

    with pytest.raises(ApiError) as error:
        client.shipments.update(
            RecipientUpdate(barcode="KRL1000000001", name="Ali", phone="5361112233")
        )

    assert error.value.status_code == 400
    assert "Already collected" in error.value.body


# --- Shipments ---------------------------------------------------------------------------


def test_create_standard_shipment_sends_documented_payload(
    client: HepsijetClient, fake: FakeHepsijet, customer: Customer, customer_address: Address
) -> None:
    shipment = Shipment(
        barcode="KRL1000000001",
        customer=customer,
        address=customer_address,
        desi=3,
        created_on=date(2026, 9, 27),
    )

    client.shipments.create(shipment)
    body = fake.last_body()

    assert fake.requests[-1].url.path == "/delivery/sendDeliveryOrderEnhanced"
    assert body["company"] == {"name": "KARLOG", "abbreviationCode": "KRL"}
    assert body["currentXDock"] == {"abbreviationCode": "KRL_IST"}
    assert body["delivery"]["customerDeliveryNo"] == "KRL1000000001"
    assert body["delivery"]["customerOrderId"] == "KRL1000000001"
    assert body["delivery"]["desi"] == "3"
    assert body["delivery"]["deliverySlotOriginal"] == "0"
    assert body["delivery"]["product"] == {"productCode": "HX_STD"}
    assert body["delivery"]["senderAddress"]["companyAddressId"] == "KRL_DEPO"
    assert body["delivery"]["recipientAddress"]["city"] == {"name": "Bursa"}
    assert body["delivery"]["recipientPerson"] == "Ayşe Yılmaz"
    assert "serviceType" not in body


def test_heavy_shipment_goes_to_xl_endpoint(
    client: HepsijetClient, fake: FakeHepsijet, customer: Customer, customer_address: Address
) -> None:
    client.shipments.create(
        Shipment(barcode="KRL1000000001", customer=customer, address=customer_address, desi=50)
    )

    assert fake.requests[-1].url.path == "/delivery/sendDeliveryOrder"
    assert fake.last_body()["serviceType"] == ["TMH"]


def test_standard_delivery_rejects_a_time_slot(
    customer: Customer, customer_address: Address
) -> None:
    with pytest.raises(ValidationError, match="doesn't use a time slot"):
        Shipment(
            barcode="KRL1000000001",
            customer=customer,
            address=customer_address,
            desi=1,
            slot=DeliverySlot.MORNING,
        )


def test_same_day_delivery_requires_a_time_slot(
    customer: Customer, customer_address: Address
) -> None:
    with pytest.raises(ValidationError, match="need a time slot"):
        Shipment(
            barcode="KRL1000000001",
            customer=customer,
            address=customer_address,
            desi=1,
            product=ProductCode.SAME_DAY,
        )


def test_barcode_length_is_validated(customer: Customer, customer_address: Address) -> None:
    with pytest.raises(ValidationError):
        Shipment(barcode="SHORT", customer=customer, address=customer_address, desi=1)


def test_parcel_update_counts_boxes(client: HepsijetClient, fake: FakeHepsijet) -> None:
    client.shipments.update(ParcelUpdate(barcode="KRL1000000001", desi_per_parcel=[1, 5, 2.5]))

    assert fake.last_body() == {
        "deliveryUpdateType": "TOTAL_PARCEL",
        "customerDeliveryNo": "KRL1000000001",
        "totalParcelInfo": {"totalParcel": 3, "desi": [1, 5, 2.5]},
    }


def test_return_swaps_addresses(
    client: HepsijetClient, fake: FakeHepsijet, customer: Customer, customer_address: Address
) -> None:
    client.returns.create(
        ReturnShipment(
            barcode="KRL1000000009", customer=customer, pickup_address=customer_address, desi=2
        )
    )
    delivery = fake.last_body()["delivery"]

    assert delivery["deliveryType"] == "RETURNED"
    assert delivery["senderAddress"]["companyAddressId"] == "KRL-C-1"
    assert delivery["recipientAddress"]["companyAddressId"] == "KRL_DEPO"


# --- Returns, labels, tracking -----------------------------------------------------------


def test_pickup_days_are_flattened(client: HepsijetClient, fake: FakeHepsijet) -> None:
    fake.reply(
        "/rest/delivery/findAvailableDeliveryDatesV2",
        {
            "status": "OK",
            "data": [
                {
                    "cityName": "İstanbul",
                    "towns": [
                        {
                            "townName": "KARTAL",
                            "xDock": [
                                {
                                    "xDockName": "KARTAL",
                                    "days": [
                                        {"date": "2026-09-28", "returnedLimit": 100},
                                        {"date": "2026-09-29", "returnedLimit": 100},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )

    days = client.returns.pickup_days(
        city="İstanbul", town="Kartal", start=date(2026, 9, 28), end=date(2026, 10, 5)
    )

    assert [day.day for day in days] == [date(2026, 9, 28), date(2026, 9, 29)]
    assert days[0].branch == "KARTAL"
    assert fake.requests[-1].url.params["deliveryType"] == "RETURNED"


def test_pdf_label_is_decoded(client: HepsijetClient, fake: FakeHepsijet) -> None:
    pdf = b"%PDF-1.4 fake"
    fake.reply("/delivery/barcodes-label", {"status": "OK", "data": base64.b64encode(pdf).decode()})

    assert client.labels.pdf("KRL1000000001") == pdf
    assert fake.last_body() == {"barcodes": ["KRL1000000001"]}
    assert fake.requests[-1].url.params["format"] == "PDF"


def test_tracking_summary_is_typed(client: HepsijetClient, fake: FakeHepsijet) -> None:
    fake.reply(
        "/rest/delivery/integration/track",
        {
            "status": "OK",
            "data": [
                {
                    "barcode": "KRL1000000001",
                    "trackingUrl": "https://hepsijet.com/gonderi-takibi/KRL1000000001",
                    "details": [
                        {
                            "transactionLocation": "Alıcıda",
                            "transactionDate": "2026-09-27T18:01:09+03:00",
                            "integrationStatus": "DELIVERED",
                            "deliveredPerson": "Ayşe",
                        }
                    ],
                }
            ],
        },
    )

    [summary] = client.tracking.summary(["KRL1000000001"])

    assert summary.is_delivered
    assert summary.latest is not None
    assert summary.latest.status is TrackingStatus.DELIVERED
    assert summary.tracking_url == "https://hepsijet.com/gonderi-takibi/KRL1000000001"


# --- Async client ------------------------------------------------------------------------


def test_async_client_sends_the_same_requests(
    config: HepsijetConfig, fake: FakeHepsijet, customer: Customer, customer_address: Address
) -> None:
    async def scenario() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(fake.handle))
        async with AsyncHepsijetClient(config, http_client=http) as client:
            await client.shipments.create(
                Shipment(
                    barcode="KRL1000000001", customer=customer, address=customer_address, desi=2
                )
            )

    asyncio.run(scenario())

    assert fake.requests[-1].url.path == "/delivery/sendDeliveryOrderEnhanced"
    assert fake.last_body()["delivery"]["desi"] == "2"
