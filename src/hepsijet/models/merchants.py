"""Marketplace merchants. Skip this if you only ship your own products."""

from datetime import date

from pydantic import Field

from hepsijet.models.base import InputModel
from hepsijet.models.people import Address, Contact


class Merchant(InputModel):
    """A merchant (or merchant warehouse) that ships through your marketplace.

    Register each merchant once. `merchant_id` is how you refer to it later, e.g. to delete it.
    """

    merchant_id: str = Field(min_length=1, examples=["KRL_Depo1"])
    company_name: str = Field(min_length=1)
    company_code: str = Field(min_length=1, description="Short code; can equal company_name.")
    address: Address
    contact: Contact
    registered_on: date = Field(default_factory=date.today)
