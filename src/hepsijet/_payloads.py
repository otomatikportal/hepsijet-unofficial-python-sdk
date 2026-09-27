"""Turn Python models into the JSON bodies HepsiJET expects.

This is the only file that knows the wire format of request bodies. If HepsiJET changes a
field name, fix it here.
"""

from datetime import date, time
from typing import Any

from hepsijet.config import HepsijetConfig
from hepsijet.enums import DeliverySlot, DeliveryType, ProductCode
from hepsijet.models import (
    Address,
    AddressUpdate,
    Customer,
    CustomerUpdate,
    DeliveryOptionUpdate,
    Merchant,
    ParcelUpdate,
    RecipientUpdate,
    ReturnShipment,
    Shipment,
    ShipmentUpdate,
)

JsonObject = dict[str, Any]

XL_SERVICE_TYPE = "TMH"


# --- Building blocks ---------------------------------------------------------------------


def address(value: Address) -> JsonObject:
    return {
        "companyAddressId": value.address_id,
        "country": {"name": value.country},
        "city": {"name": value.city},
        "town": {"name": value.town},
        "district": {"name": value.district},
        "addressLine1": value.line,
    }


def customer(value: Customer) -> JsonObject:
    return _without_none(
        {
            "companyCustomerId": value.customer_id,
            "firstName": value.first_name,
            "lastName": value.last_name,
            "phone1": value.phone,
            "email": value.email,
        }
    )


def company(config: HepsijetConfig) -> JsonObject:
    return {"name": config.company_name, "abbreviationCode": config.company_code}


def number(value: float) -> int | float:
    """Send 3.0 as 3, but keep 2.5 as 2.5."""
    return int(value) if value.is_integer() else value


# --- Shipments ---------------------------------------------------------------------------


def shipment(value: Shipment, config: HepsijetConfig) -> JsonObject:
    payload = _delivery_order(
        config,
        barcode=value.barcode,
        order_id=value.order_id,
        receiver=value.customer,
        sender=value.warehouse or config.warehouse,
        recipient=value.address,
        desi=value.desi,
        parcel_count=value.parcel_count,
        delivery_type=value.delivery_type,
        product=value.product,
        slot=value.slot,
        created_on=value.created_on.isoformat(),
    )
    if value.is_xl:
        payload["serviceType"] = [XL_SERVICE_TYPE]
    return payload


def return_shipment(value: ReturnShipment, config: HepsijetConfig) -> JsonObject:
    """A return is a normal order with the addresses swapped: customer → warehouse."""
    return _delivery_order(
        config,
        barcode=value.barcode,
        order_id=value.order_id,
        receiver=value.customer,
        sender=value.pickup_address,
        recipient=value.warehouse or config.warehouse,
        desi=value.desi,
        parcel_count=value.parcel_count,
        delivery_type=DeliveryType.RETURNED,
        product=ProductCode.STANDARD,
        slot=DeliverySlot.ANY_TIME,
        created_on=value.created_on.isoformat(),
    )


def _delivery_order(
    config: HepsijetConfig,
    *,
    barcode: str,
    order_id: str | None,
    receiver: Customer,
    sender: Address,
    recipient: Address,
    desi: float,
    parcel_count: int,
    delivery_type: DeliveryType,
    product: ProductCode,
    slot: DeliverySlot,
    created_on: str,
) -> JsonObject:
    return {
        "company": company(config),
        "delivery": {
            "customerDeliveryNo": barcode,
            "customerOrderId": order_id or barcode,
            "totalParcels": str(parcel_count),
            "desi": str(number(desi)),
            "deliverySlotOriginal": str(slot.value),
            "deliveryDateOriginal": created_on,
            "deliveryType": delivery_type.value,
            "product": {"productCode": product.value},
            "receiver": customer(receiver),
            "senderAddress": address(sender),
            "recipientAddress": address(recipient),
            "recipientPerson": receiver.full_name,
            "recipientPersonPhone1": receiver.phone,
        },
        "currentXDock": {"abbreviationCode": config.xdock_code},
    }


# --- Shipment updates --------------------------------------------------------------------


def shipment_update(change: ShipmentUpdate) -> JsonObject:
    match change:
        case ParcelUpdate():
            return {
                "deliveryUpdateType": "TOTAL_PARCEL",
                "customerDeliveryNo": change.barcode,
                "totalParcelInfo": {
                    "totalParcel": change.parcel_count,
                    "desi": [number(desi) for desi in change.desi_per_parcel],
                },
            }
        case DeliveryOptionUpdate():
            return {
                "deliveryUpdateType": "PRODUCT_CODE",
                "customerDeliveryNo": change.barcode,
                "productCodeInfo": _without_none(
                    {
                        "productCode": change.product.value,
                        "deliveryDateOriginal": _isoformat(change.delivery_date),
                        "deliverySlot": change.slot.value if change.slot is not None else None,
                        "deliveryStartTime": _isoformat(change.window_start),
                        "deliveryEndTime": _isoformat(change.window_end),
                    }
                ),
            }
        case CustomerUpdate():
            person = change.customer
            return {
                "deliveryUpdateType": "COMPANY_CUSTOMER",
                "customerDeliveryNo": change.barcode,
                "companyCustomerInfo": _without_none(
                    {
                        "companyCustomerId": person.customer_id,
                        "firstName": person.first_name,
                        "lastName": person.last_name,
                        "email": person.email,
                        "gsm1": person.phone,
                    }
                ),
            }
        case AddressUpdate():
            place = change.address
            return {
                "deliveryUpdateType": "COMPANY_ADDRESS",
                "customerDeliveryNo": change.barcode,
                "companyAddressInfo": {
                    "companyAddressId": place.address_id,
                    "addressLine1": place.line,
                    "countryName": place.country,
                    "cityName": place.city,
                    "townName": place.town,
                    "districtName": place.district,
                },
            }
        case RecipientUpdate():
            return {
                "deliveryUpdateType": "RECIPIENT_PERSON",
                "customerDeliveryNo": change.barcode,
                "recipientPersonInfo": _without_none(
                    {
                        "recipientPerson": change.name,
                        "recipientPersonPhone1": change.phone,
                        "recipientPersonPhone2": change.second_phone,
                        "recipientPersonEmail": change.email,
                    }
                ),
            }


def delete_reason(reason: str) -> JsonObject:
    return {"deleteReason": reason}


# --- Marketplace merchants ---------------------------------------------------------------


def merchant(value: Merchant) -> JsonObject:
    contact = value.contact
    return {
        "orderId": value.merchant_id,
        "orderDate": value.registered_on.isoformat(),
        "receiver": _without_none(
            {
                "companyCustomerId": value.merchant_id,
                "firstName": contact.first_name,
                "lastName": contact.last_name,
                "phone1": contact.phone,
                "email": contact.email,
            }
        ),
        "deliveries": [
            {
                "senderCompany": {
                    "companyCompanyId": 1,
                    "name": value.company_name,
                    "abbreviationCode": value.company_code,
                    "accountId": value.merchant_id,
                    "contactEmails": [contact.email] if contact.email else [],
                },
                "deliveryType": DeliveryType.MARKET_PLACE.value,
                "deliverySlot": str(DeliverySlot.ANY_TIME.value),
                "desi": "1",
                "product": {"productCode": ProductCode.STANDARD.value},
                "senderAddress": address(value.address),
                "recipientAddress": address(value.address),
                "applicationNo": "",
            }
        ],
    }


# --- Helpers -----------------------------------------------------------------------------


def _without_none(values: JsonObject) -> JsonObject:
    return {key: value for key, value in values.items() if value is not None}


def _isoformat(value: date | time | None) -> str | None:
    return value.isoformat() if value is not None else None
