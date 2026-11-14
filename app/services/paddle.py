from dataclasses import dataclass

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from paddle_billing import Client, Environment, Options
from paddle_billing.Notifications import Secret, Verifier
from paddle_billing.Notifications.Requests.Headers import Headers
from starlette.datastructures import Headers as StarletteHeaders

from app.schemas.paddle import PaddleCustomer
from config import settings


@dataclass
class _HeadersAdapter:
    """Expose Starlette's case-insensitive headers through the Paddle SDK `Headers` protocol"""
    headers: StarletteHeaders

    def get(self, key: str, default=None) -> str | None:
        return self.headers.get(key, default)


@dataclass
class _WebhookRequest:
    """Adapter matching the Paddle SDK `Request` protocol (raw bytes body + headers)"""
    headers: Headers
    body: bytes | None
    content: bytes | None = None
    data: bytes | None = None


class Paddle:
    def __init__(self) -> None:
        self.verifier = Verifier()
        self.secret = Secret(settings.PADDLE_ORDER_WEBHOOK_SECRET.get_secret_value())
        self.client = Client(
            settings.PADDLE_API_KEY.get_secret_value(),
            options=Options(Environment(settings.PADDLE_ENVIRONMENT)),
        )

    async def get_customer(self, customer_id: str) -> PaddleCustomer:
        """
        Fetch a customer from Paddle API (webhooks only carry the customer ID)

        Args:
            customer_id (str): Paddle customer ID (ctm_…)

        Returns:
            PaddleCustomer: Customer details

        Raises:
            ApiError: Paddle API rejected the request (unknown customer, bad API key…)
        """
        # The SDK is synchronous (requests): run it off the event loop
        customer = await run_in_threadpool(self.client.customers.get, customer_id)

        return PaddleCustomer(
            id=customer.id,
            email=customer.email,
            name=customer.name,
            marketing_consent=customer.marketing_consent,
            status=customer.status.value,
            locale=customer.locale,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )

    async def validate_webhook_signature(self, request: Request) -> bool:
        """
        Use Paddle SDK to verify webhook signature

        Args:
            request (Request): Incoming FastAPI request (raw body + Paddle-Signature header)

        Returns:
            bool: Is paddle request legit
        """
        # The SDK expects `.body` as raw bytes, but Starlette exposes it as an async method
        raw_body = await request.body()

        return self.verifier.verify(
            _WebhookRequest(headers=_HeadersAdapter(request.headers), body=raw_body),
            self.secret,
        )
