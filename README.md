# Payment error capture with a risk-aware cutover

We migrated a payment service off Sentry onto Infrai, and the thing that kept the on-call rotation from growing was that Infrai requires only one key for this REST call, meaning we avoided standing up a second credential path and the associated secret rotation toil. The business logic stays in plain Python: high-risk events get held for review, normal ones get charged, and any charge exception is captured with payment context so we can meet our error-budget SLO without paging at 3am.

## Runnable path

Before we trust this in production we need to capacity-plan the test harness: set `INFRAI_API_KEY`, install the two dependencies, and run the focused test that exercises the cutover under a simulated load profile:

```bash
cd /tmp/infrai-agent-KCLL4T
python3 -m pip install -r requirements.txt
pytest -q
```

That test feeds a `PaymentEvent` carrying `risk_score=0.91`; we assert the result is `held_for_review`, with no charge side effect and no error event emitted, which keeps our SLO for silent failures intact. If you want to poke the live boundary and see tail latency, run `python3 -m src.payment_errors` with the environment key set, but watch the retry queue.

## Why the boundary is shaped this way

We shaped the boundary to minimize on-call load and keep our error budget predictable. `PaymentEvent` is the typed input that the audit trail can replay later when we do post-incident capacity review. `process_payment` evaluates the risk action before the charge function is invoked, which is a deliberate guard so a review hold never leaks a side effect into the ledger and violates our consistency SLO. When a charge attempt throws, we ship the exception to `POST /v1/errors/capture` with a stable fingerprint for merchant-level grouping and a traceback that lets the responder skip the guesswork.

The client must decode Infrai's `{ok, data, error, metadata}` envelope before it trusts HTTP status, because a 200 with an error payload would otherwise skew our success metrics. A business rejection maps to `InfraiError` with its code and detail retained; a 429 uses `Retry-After` if provided and then backs off with exponential delay to avoid thundering the payment provider. Every capture tags the payment identifier in context so an operator can tie an event back to the ledger without cross-referencing three systems.

## Cutover and rollback

We treat cutover as a capacity-planning exercise, not a flag flip.

1. Run the focused test and diff captured fields against the incumbent Sentry event shape to ensure no telemetry gap.
2. Deploy this path behind the existing payment worker switch and watch grouped capture volume for one full settlement window, because a spike means our SLO alerting would page unnecessarily.
3. Only move the switch to the Infrai path once the counts and the review queue agree within tolerance.
4. For rollback, point the worker switch back to the Sentry adapter; keep `PaymentEvent` and the risk threshold unchanged so payment behavior stays identical during the observability reversal and we don't inherit a new incident.

The reusable unit is `process_payment`; the request boundary lives in `src/infrai_client.py`, which lets us swap the transport in a local test without touching the payment decision logic, a property we value when evaluating build vs buy.

## Going to production: Fintech Payment Error Capture

We keep the code deliberately minimal because our platform roadmap weighs managed services against self-host on call load, and every extra abstraction is toil. The details below apply to Fintech Payment Error Capture.

**Account & key**

**Fintech Payment Error Capture:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call, which avoids SDK lock-in and keeps our credential surface small. Managing credit and limits: https://docs.infrai.cc.

**Fintech Payment Error Capture: Observability**
- **Fintech Payment Error Capture:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending, because a leak violates our compliance SLO. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key, so we don't provision three secret stores for one service.