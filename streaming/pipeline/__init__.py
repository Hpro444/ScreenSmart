"""ScreenSmart streaming pipeline — the event-driven services that tie the screening
modules together: ingest → Kafka → (screensmart + exposure workers) → accumulator →
Postgres + verdicts topic → WebSocket → frontend.

This package contains ONLY the glue services (ingest, accumulator, ws_gateway). It does
NOT import `screensmart_app` or `exposure_graph` (which both use the package name
`screensmart` and would collide) — it talks to them purely over Kafka topics.
"""
__version__ = "0.1.0"
