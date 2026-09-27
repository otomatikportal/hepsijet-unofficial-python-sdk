"""Addresses and the people at them."""

from pydantic import EmailStr, Field

from hepsijet.models.base import InputModel


class Address(InputModel):
    """A physical address in Turkey.

    `address_id` must be unique per address. HepsiJET uses it to tell addresses apart,
    so prefix it with your company code, e.g. "KRL-ADDR-551".
    """

    address_id: str = Field(min_length=1)
    city: str = Field(min_length=1, examples=["İstanbul"])
    town: str = Field(min_length=1, examples=["Kartal"], description="İlçe")
    district: str = Field(min_length=1, examples=["Petrol İş"], description="Mahalle")
    line: str = Field(min_length=1, description="Full street address, e.g. 'Kamelya Sk. No:10 D:1'")
    country: str = "Türkiye"


class Contact(InputModel):
    """A person you can reach by phone."""

    first_name: str = Field(min_length=1)
    last_name: str = ""
    phone: str = Field(min_length=10, examples=["5321112233"])
    email: EmailStr | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Customer(Contact):
    """The customer who receives (or returns) a shipment.

    `customer_id` must be unique per customer address. You can reuse the address's `address_id`.
    """

    customer_id: str = Field(min_length=1)
