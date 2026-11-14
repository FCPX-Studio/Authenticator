from dataclasses import dataclass

from fastapi import Request
from paddle_billing.Notifications import Secret, Verifier
from paddle_billing.Notifications.Requests.Headers import Headers
from starlette.datastructures import Headers as StarletteHeaders

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
