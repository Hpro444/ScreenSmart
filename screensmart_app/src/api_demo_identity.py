"""Demonstrate the identity (DOB/passport/national-ID) and risk layers via the API."""
import httpx

BASE = "http://127.0.0.1:8000"
CASES = [
    ("Exact national-ID hit, GARBLED name",
     {"name": "Xandr Markmann", "country": "us", "national_id": "561103307661", "txn_id": "ID1"}),
    ("Real name + MATCHING DOB (corroborated)",
     {"name": "Alexander Markman", "country": "ru", "dob": "1948-07-16", "txn_id": "DOB_OK"}),
    ("Common-name bait, NO identity -> must REVIEW",
     {"name": "Mohammed Ali", "country": "ae", "txn_id": "BAIT_NONE"}),
    ("Same bait + MISMATCHING DOB -> should clear",
     {"name": "Mohammed Ali", "country": "ae", "dob": "1995-03-03", "txn_id": "BAIT_DOB"}),
    ("Borderline name, LOW-risk context (small domestic card)",
     {"name": "Alexandr Markman", "country": "ru", "amount": 200, "currency": "USD",
      "rail": "card", "orig_country": "us", "txn_id": "RISK_LO"}),
    ("Borderline name, HIGH-risk context (large SWIFT from RU)",
     {"name": "Alexandr Markman", "country": "ru", "amount": 500000, "currency": "RUB",
      "rail": "SWIFT", "orig_country": "ru", "txn_id": "RISK_HI"}),
]

with httpx.Client(timeout=30) as c:
    for label, body in CASES:
        r = c.post(f"{BASE}/screen", json=body).json()
        e = r["explanation"]
        print(f"\n### {label}")
        print(f"    verdict={r['verdict']}  p={r['probability']}  risk={r['risk_score']}  "
              f"thresholds(review/block)={e['thresholds']['review']}/{e['thresholds']['block']}")
        if r["matched_entity"]:
            print(f"    matched: {r['matched_entity']['name']}")
        for s in e["signals"]:
            print(f"      - {s}")
