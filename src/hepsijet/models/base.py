"""Base classes and shared field types for all models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

Barcode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=9, max_length=16)]
"""Your unique shipment number (HepsiJET calls it `customerDeliveryNo`).

Must be 9 to 16 characters. Start it with your company prefix to keep it unique,
e.g. "KRL1000000001".
"""

Desi = Annotated[float, Field(gt=0)]
"""Volumetric weight of a parcel."""


class InputModel(BaseModel):
    """Base for everything you send to HepsiJET. Immutable and strictly validated."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    """Base for everything HepsiJET sends back.

    Fields are snake_case in Python and camelCase on the wire. Fields that aren't declared
    are kept (see `model_extra`), not rejected, so a new field from HepsiJET never breaks you.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="allow",
        alias_generator=to_camel,
        populate_by_name=True,
    )
