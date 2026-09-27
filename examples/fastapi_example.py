"""Using the SDK in a FastAPI app.

Run with:  uvicorn examples.fastapi_example:app --reload
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response

from hepsijet import (
    Address,
    ApiError,
    ApiResult,
    AsyncHepsijetClient,
    HepsijetConfig,
    Shipment,
    ShipmentHistory,
    TrackingSummary,
)


def load_config() -> HepsijetConfig:
    return HepsijetConfig(
        username=os.environ["HEPSIJET_USERNAME"],
        password=os.environ["HEPSIJET_PASSWORD"],
        company_name=os.environ["HEPSIJET_COMPANY_NAME"],
        company_code=os.environ["HEPSIJET_COMPANY_CODE"],
        xdock_code=os.environ["HEPSIJET_XDOCK_CODE"],
        warehouse=Address(
            address_id="KRL_DEPO",
            city="İstanbul",
            town="Kartal",
            district="Petrol İş",
            line="Kamelya Sk. No:10",
        ),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """One client for the app's lifetime: shared connections, shared token."""
    async with AsyncHepsijetClient(load_config()) as client:
        app.state.hepsijet = client
        yield


app = FastAPI(lifespan=lifespan)


def get_hepsijet(request: Request) -> AsyncHepsijetClient:
    client: AsyncHepsijetClient = request.app.state.hepsijet
    return client


Hepsijet = Annotated[AsyncHepsijetClient, Depends(get_hepsijet)]


@app.post("/shipments")
async def create_shipment(shipment: Shipment, hepsijet: Hepsijet) -> ApiResult:
    """The SDK's `Shipment` model doubles as the request body, validation included."""
    try:
        return await hepsijet.shipments.create(shipment)
    except ApiError as error:
        raise HTTPException(status_code=502, detail=error.body) from error


@app.get("/shipments/{barcode}/tracking")
async def track(barcode: str, hepsijet: Hepsijet) -> TrackingSummary:
    [parcel] = await hepsijet.tracking.summary(barcode)
    return parcel


@app.get("/shipments/{barcode}/history")
async def history(barcode: str, hepsijet: Hepsijet) -> ShipmentHistory:
    [shipment] = await hepsijet.tracking.history(barcode)
    return shipment


@app.get("/shipments/{barcode}/label.pdf")
async def label(barcode: str, hepsijet: Hepsijet) -> Response:
    return Response(await hepsijet.labels.pdf(barcode), media_type="application/pdf")


@app.delete("/shipments/{barcode}")
async def cancel(barcode: str, hepsijet: Hepsijet) -> ApiResult:
    return await hepsijet.shipments.cancel(barcode)
