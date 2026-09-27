"""Your HepsiJET account settings."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from hepsijet.models.people import Address

TEST_BASE_URL = "https://integration-apitest.hepsijet.com"
"""HepsiJET's test server. HepsiJET gives you the live URL together with your live credentials."""


class HepsijetConfig(BaseModel):
    """Everything the SDK needs to act on your behalf.

    HepsiJET issues every value here except `warehouse`. That one must match, exactly,
    the warehouse address you registered with them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    username: str
    password: SecretStr
    company_name: str
    company_code: str
    xdock_code: str = Field(description="HepsiJET's `currentXDock.abbreviationCode` for you.")
    warehouse: Address = Field(description="The address you ship from.")
    base_url: str = TEST_BASE_URL
    timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, url: str) -> str:
        return url.rstrip("/")
