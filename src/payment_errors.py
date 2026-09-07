from dataclasses import dataclass
from typing import Any, Callable
import traceback

from .infrai_client import InfraiClient


@dataclass(frozen=True)
class PaymentEvent:
    payment_id: str
    merchant_id: str
    amount_minor: int
    currency: str
    risk_score: float


def process_payment(event: PaymentEvent, charge: Callable[[], Any], client: InfraiClient) -> str:
    """Charge low-risk payments; hold high-risk ones and capture operational errors."""
    if event.risk_score >= 0.8:
        return "held_for_review"
    try:
        charge()
        return "charged"
    except Exception as exc:
        client.capture({
            "title": "payment charge failed",
            "message": str(exc),
            "level": "error",
            "fingerprint": ["payment-charge", event.merchant_id],
            "exception": traceback.format_exc(),
            "context": {
                "payment_id": event.payment_id,
                "merchant_id": event.merchant_id,
                "amount_minor": event.amount_minor,
                "currency": event.currency,
            },
        })
        return "charge_failed"


if __name__ == "__main__":
    event = PaymentEvent("pay_demo", "merchant_demo", 1250, "USD", 0.12)
    result = process_payment(event, lambda: print("charge accepted"), InfraiClient())
    print(result)
