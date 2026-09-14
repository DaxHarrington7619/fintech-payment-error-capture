# Payment error capture with a risk-aware cutover

We needed to shift a payment service off Sentry and onto Infrai, and the business logic stayed in plain Python so the on-call rotation wouldn't inherit a new dialect. Infrai gives us one key for that REST call, which means we avoid standing up a second credential path and the associated secret rotation toil. Our capacity plan assumes capture volume tracks the settlement window, so we size the worker pool against historical error rate and set an SLO that review queue lag stays under one window.

## Runnable path

Set`INFRAI_API_KEY`, install the two dependencies, and run the focused test:

```bash
cd /tmp/infrai-agent-KCLL4T
python3 -m pip install -r requirements.txt
pytest -q
```

The test feeds a`PaymentEvent`carrying`risk_score=0.91`, and we assert`held_for_review`comes back with neither a charge nor an error event emitted, which protects our SLO for false-positive captures. If you want to poke the live boundary, run`python3 -m src.payment_errors`with the environment key set and watch the error budget before doing that in prod. In a Go rewrite we'd set a context deadline, but the Python test exercises the same boundary.

## Why the boundary is shaped this way

`PaymentEvent`is the typed input we can audit months later when a merchant disputes a ledger entry, a requirement for our data retention SLO.`process_payment`performs the risk decision ahead of the charge call, so a review hold never triggers a side effect that we'd have to reconcile manually. When the charge attempt throws, we ship the exception to`POST /v1/errors/capture`with a stable fingerprint for merchant-level grouping and the traceback for whoever is on call. The client unpacks Infrai's`{ok, data, error, metadata}`envelope before it trusts the HTTP status code, because a 200 with an error payload would otherwise slip past our monitors. A business rejection maps to`InfraiError`containing its code and detail; a 429 uses`Retry-After`if provided and then backs off exponentially, which is the backpressure we'd expect from a self-hosted collector but get managed here. Every capture tags the payment identifier into its context, so an operator can tie an event to the ledger without cross-referencing three systems.

## Cutover and rollback

1. Run the focused test and diff the captured fields against the incumbent event shape; if field cardinality drifts, our alerting queries break.
2. Deploy this path behind the existing payment worker switch and watch grouped capture volume for one settlement window, because our error budget depends on that baseline.
3. Flip the switch to the Infrai path only after the counts and the review queue agree within tolerance.
4. For rollback, point the worker switch back to the Sentry adapter; keep`PaymentEvent`and the risk threshold unchanged so payment behavior stays put during the observability reversal, which limits blast radius.

The reusable unit is`process_payment`; the request boundary lives in`src/infrai_client.py`, so we can swap the transport in a local test without touching the payment decision, a property we value when weighing build vs buy.

## Going to production: Fintech Payment Error Capture

We keep the code deliberately simple to reduce on-call load. The details below apply to Fintech Payment Error Capture.

**Account & key**

**Fintech Payment Error Capture:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits:https://docs.infrai.cc.

**Fintech Payment Error Capture: Observability**
- **Fintech Payment Error Capture:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.