"""Hit the running ScreenSmart API with a few representative payments."""
import json
import httpx

BASE = "http://127.0.0.1:8000"
CASES = [
    {"name": "Muammar Qadhafi", "country": "ly", "txn_id": "TX1"},        # distinctive -> MATCH
    {"name": "Mohammed Ali", "country": "ae", "txn_id": "TX2"},           # common -> REVIEW
    {"name": "Oscar Fairbanks", "country": "us", "txn_id": "TX3"},        # clean -> NO_MATCH
    {"name": "Mohammad Khaddouur", "country": "us", "txn_id": "TX4"},     # typo'd true match
]


def show(r):
    print(f"\n>>> {r['query']!r}  ({r['txn_id']})")
    print(f"    VERDICT : {r['verdict']}   p={r['probability']}   model={r['model_name']}   "
          f"{r['latency_ms']}ms")
    if r["matched_entity"]:
        m = r["matched_entity"]
        print(f"    matched : {m['name']}  [{m['type']}]  programs={m['programs'][:2]}")
    e = r["explanation"]
    print(f"    why     : {e['summary']}")
    print(f"    decision: {e['decision']}")
    for s in e["signals"]:
        print(f"              - {s}")


with httpx.Client(timeout=30) as c:
    print("HEALTH:", json.dumps(c.get(f"{BASE}/health").json(), indent=2))
    for case in CASES:
        show(c.post(f"{BASE}/screen", json=case).json())
