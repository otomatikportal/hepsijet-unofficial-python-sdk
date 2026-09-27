"""A fake HepsiJET server that records every request, so tests can check what was sent."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from hepsijet import Address, Customer, HepsijetClient, HepsijetConfig

Handler = Callable[[httpx.Request], httpx.Response]


class FakeHepsijet:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.routes: dict[str, Handler] = {}
        self.issued_tokens = 0
        self.valid_token = "token-1"

    def reply(self, path: str, body: Any, status: int = 200) -> None:
        self.routes[path] = lambda _request: httpx.Response(status, json=body)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)

        if request.url.path == "/auth/getToken":
            self.issued_tokens += 1
            self.valid_token = f"token-{self.issued_tokens}"
            return httpx.Response(200, json={"status": "OK", "data": {"token": self.valid_token}})

        if request.headers.get("X-Auth-Token") != self.valid_token:
            return httpx.Response(401, json={"status": "UNAUTHORIZED"})

        handler = self.routes.get(request.url.path)
        if handler is None:
            return httpx.Response(200, json={"status": "OK"})
        return handler(request)

    def last_body(self) -> Any:
        return json.loads(self.requests[-1].content)


@pytest.fixture
def fake() -> FakeHepsijet:
    return FakeHepsijet()


@pytest.fixture
def warehouse() -> Address:
    return Address(
        address_id="KRL_DEPO",
        city="İstanbul",
        town="Kartal",
        district="Petrol İş",
        line="Kamelya Sk. No:10",
    )


@pytest.fixture
def config(warehouse: Address) -> HepsijetConfig:
    return HepsijetConfig(
        username="user",
        password=SecretStr("pass"),
        company_name="KARLOG",
        company_code="KRL",
        xdock_code="KRL_IST",
        warehouse=warehouse,
    )


@pytest.fixture
def client(config: HepsijetConfig, fake: FakeHepsijet) -> HepsijetClient:
    return HepsijetClient(
        config, http_client=httpx.Client(transport=httpx.MockTransport(fake.handle))
    )


@pytest.fixture
def customer() -> Customer:
    return Customer(
        customer_id="KRL-C-1", first_name="Ayşe", last_name="Yılmaz", phone="5321112233"
    )


@pytest.fixture
def customer_address() -> Address:
    return Address(
        address_id="KRL-C-1",
        city="Bursa",
        town="Osmangazi",
        district="Güneştepe",
        line="771 Sk. No:1",
    )
