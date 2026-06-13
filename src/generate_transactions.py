"""
Synthetic payment-instruction generator.

There is no public dataset of real payment instructions (they are proprietary &
sensitive), so we SYNTHESISE a realistic, *labelled* stream. Positives are sampled
from the actual sanctions list and then degraded with the exact noise that breaks
naive matching (transliteration, alias use, token reorder, typos). This both shows
"what transactions look like / how they behave" and gives us ground truth to score
precision / recall and latency against.

Output: data/processed/transactions.parquet  (+ a CSV sample) with an
`expected_verdict` ground-truth column.
"""
from __future__ import annotations
import random, pathlib, datetime as dt
import pandas as pd

# name-degradation operators + clean-name pools live in the shared package, so the
# generator and the training-pair builder apply identical noise.
from screensmart.synthesis import (
    add_typo, transliterate, reorder, CLEAN_FIRST, CLEAN_LAST, COMMON_BAIT as BAIT,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RNG = random.Random(42)

COUNTRIES = ["us", "gb", "de", "fr", "ng", "in", "br", "jp", "ae", "sg", "za", "mx"]
RAILS = ["SWIFT", "SEPA", "FedWire", "card", "FPS", "ACH"]
CCY = ["USD", "EUR", "GBP", "AED", "SGD", "JPY"]


def main(n: int = 20000):
    df = pd.read_parquet(PROC / "sanctions_clean.parquet")
    persons = df[df["schema"].isin(["Person"])].reset_index(drop=True)
    orgs = df[df["schema"].isin(["Organization", "Company", "LegalEntity"])].reset_index(drop=True)
    wallets_src = df[df["schema"] == "CryptoWallet"]
    wallet_names = wallets_src["name"].tolist()

    rows = []
    base = dt.datetime(2026, 6, 13, 9, 0, 0)
    for k in range(n):
        ts = (base + dt.timedelta(seconds=k * 3)).isoformat()
        roll = RNG.random()
        rail = RNG.choice(RAILS)
        amount = round(RNG.lognormvariate(7, 1.4), 2)
        common = dict(txn_id=f"TX{k:07d}", timestamp=ts, amount=amount,
                      currency=RNG.choice(CCY), rail=rail,
                      orig_country=RNG.choice(COUNTRIES))

        if roll < 0.90:                       # 90% clean fiat
            nm = f"{RNG.choice(CLEAN_FIRST)} {RNG.choice(CLEAN_LAST)}"
            rows.append({**common, "channel": "fiat", "bene_name": nm,
                         "bene_country": RNG.choice(COUNTRIES), "wallet": "",
                         "expected_verdict": "NO_MATCH", "scenario": "clean"})
        elif roll < 0.945:                    # ~4.5% false-positive bait: a common name
            # that PARTIALLY collides with sanctioned entries. With only a name+country
            # these genuinely cannot be auto-cleared, so the correct verdict is REVIEW
            # (a human checks DOB/ID). Auto-BLOCK here = over-block; NO_MATCH = unsafe.
            nm = RNG.choice(BAIT)
            rows.append({**common, "channel": "fiat", "bene_name": nm,
                         "bene_country": RNG.choice(COUNTRIES), "wallet": "",
                         "expected_verdict": "REVIEW", "scenario": "fp_bait"})
        elif roll < 0.975:                    # ~3% true sanctioned, but DEGRADED
            src = persons if RNG.random() < 0.6 else orgs
            real = src.sample(1, random_state=RNG.randint(0, 1 << 30)).iloc[0]["name"]
            mode = RNG.choice(["translit", "typo", "reorder", "alias_exact"])
            if mode == "translit":
                nm = transliterate(real); scen = "sanctioned_translit"; exp = "REVIEW"
            elif mode == "typo":
                nm = add_typo(real, RNG); scen = "sanctioned_typo"; exp = "REVIEW"
            elif mode == "reorder":
                nm = reorder(real, RNG); scen = "sanctioned_reorder"; exp = "MATCH"
            else:
                nm = real; scen = "sanctioned_exact"; exp = "MATCH"
            rows.append({**common, "channel": "fiat", "bene_name": nm,
                         "bene_country": RNG.choice(COUNTRIES), "wallet": "",
                         "expected_verdict": exp, "scenario": scen})
        elif roll < 0.995:                    # 2% clean crypto
            addr = "0x" + "".join(RNG.choice("0123456789abcdef") for _ in range(40))
            rows.append({**common, "channel": "crypto", "bene_name": "", "bene_country": "",
                         "wallet": addr, "expected_verdict": "NO_MATCH", "scenario": "crypto_clean"})
        else:                                 # 0.5% sanctioned crypto (real wallet)
            addr = RNG.choice(wallet_names) if wallet_names else "0xdead"
            rows.append({**common, "channel": "crypto", "bene_name": "", "bene_country": "",
                         "wallet": addr, "expected_verdict": "MATCH", "scenario": "crypto_sanctioned"})

    out = pd.DataFrame(rows)
    out.to_parquet(PROC / "transactions.parquet", index=False)
    out.head(50).to_csv(PROC / "transactions_sample.csv", index=False)
    print(f"Generated {len(out):,} transactions -> {PROC/'transactions.parquet'}")
    print("\nScenario mix:")
    print(out["scenario"].value_counts().to_string())
    print("\nChannel mix:")
    print(out["channel"].value_counts().to_string())
    print("\nExpected-verdict mix:")
    print(out["expected_verdict"].value_counts().to_string())


if __name__ == "__main__":
    main()
