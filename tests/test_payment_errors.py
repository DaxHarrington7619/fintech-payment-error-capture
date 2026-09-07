from src.payment_errors import PaymentEvent, process_payment


class CaptureSpy:
    def __init__(self):
        self.payloads = []

    def capture(self, payload):
        self.payloads.append(payload)
        return {"event_id": "evt_test"}


def test_high_risk_payment_is_held_without_charging_or_capture():
    spy = CaptureSpy()
    charged = []
    event = PaymentEvent("p1", "m1", 5000, "USD", 0.91)

    result = process_payment(event, lambda: charged.append(True), spy)

    assert result == "held_for_review"
    assert charged == []
    assert spy.payloads == []
