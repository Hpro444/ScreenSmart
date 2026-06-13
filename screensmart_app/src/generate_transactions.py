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
    eval_degrade, random_dob, entity_split, CLEAN_FIRST, CLEAN_LAST, COMMON_BAIT as BAIT,
)
from screensmart.config import settings

PROC = settings.processed_dir
RNG = random.Random(42)

COUNTRIES = ["us", "gb", "de", "fr", "ng", "in", "br", "jp", "ae", "sg", "za", "mx"]
RAILS = ["SWIFT", "SEPA", "FedWire", "card", "FPS", "ACH"]
CCY = ["USD", "EUR", "GBP", "AED", "SGD", "JPY"]


def _split_ids(field) -> list[str]:
    return [s.strip() for s in str(field or "").split(";") if s.strip()]


def main(n: int = 20000):
    df = pd.read_parquet(PROC / "sanctions_clean.parquet")
    # hold out a disjoint set of entities for the test stream — the model trains only on
    # the complementary set (see synthesis.entity_split), so this measures generalisation.
    _train_ids, eval_ids = entity_split(df["id"].tolist())
    df_eval = df[df["id"].isin(eval_ids)]
    persons = df_eval[df_eval["schema"].isin(["Person"])].reset_index(drop=True)
    orgs = df_eval[df_eval["schema"].isin(["Organization", "Company", "LegalEntity"])].reset_index(drop=True)
    wallets_src = df[df["schema"] == "CryptoWallet"]
    wallet_names = wallets_src["name"].tolist()
    empty_id = {"bene_dob": "", "bene_passport": "", "bene_national_id": ""}

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
            ident = dict(empty_id)
            if RNG.random() < 0.3:            # some clean payees carry a (non-matching) DOB
                ident["bene_dob"] = random_dob(RNG)
            rows.append({**common, "channel": "fiat", "bene_name": nm,
                         "bene_country": RNG.choice(COUNTRIES), "wallet": "", **ident,
                         "expected_verdict": "NO_MATCH", "scenario": "clean"})
        elif roll < 0.945:                    # ~4.5% false-positive bait: a common name
            # that PARTIALLY collides with sanctioned entries. With a DOB that does NOT
            # match the sanctioned namesake, the system can now CLEAR them (the realistic
            # way real screening resolves common-name false positives).
            nm = RNG.choice(BAIT)
            ident = dict(empty_id)
            if RNG.random() < 0.6:
                ident["bene_dob"] = random_dob(RNG)    # mismatching DOB -> clears
            rows.append({**common, "channel": "fiat", "bene_name": nm,
                         "bene_country": RNG.choice(COUNTRIES), "wallet": "", **ident,
                         "expected_verdict": "REVIEW", "scenario": "fp_bait"})
        elif roll < 0.975:                    # ~3% true sanctioned, but DEGRADED
            src = persons if RNG.random() < 0.6 else orgs
            row = src.sample(1, random_state=RNG.randint(0, 1 << 30)).iloc[0]
            real = row["name"]
            ent_dob = str(row.get("birth_date", "") or "")
            ent_ids = _split_ids(row.get("identifiers", ""))
            # NOTE: degraded names use eval_degrade (a DIFFERENT noise family than the
            # training-pair synthesis) so the benchmark reflects generalisation. The
            # scenario label is just the metric bucket, not the literal operation.
            mode = RNG.choice(["translit", "typo", "reorder", "alias_exact"])
            if mode == "alias_exact":
                nm = real; scen = "sanctioned_exact"; exp = "MATCH"
            else:
                nm, _op = eval_degrade(real, RNG)
                scen = f"sanctioned_{mode}"
                exp = "MATCH" if mode == "reorder" else "REVIEW"
            # attach the entity's real DOB / ID some of the time (strong corroboration)
            ident = dict(empty_id)
            r2 = RNG.random()
            if ent_dob and r2 < 0.5:
                ident["bene_dob"] = ent_dob               # exact DOB match
            elif r2 < 0.65:
                ident["bene_dob"] = random_dob(RNG)        # rare data-entry mismatch
            if ent_ids and RNG.random() < 0.3:
                ident["bene_national_id"] = RNG.choice(ent_ids)   # exact ID -> definitive MATCH
            rows.append({**common, "channel": "fiat", "bene_name": nm,
                         "bene_country": RNG.choice(COUNTRIES), "wallet": "", **ident,
                         "expected_verdict": exp, "scenario": scen})
        elif roll < 0.995:                    # 2% clean crypto
            addr = "0x" + "".join(RNG.choice("0123456789abcdef") for _ in range(40))
            rows.append({**common, "channel": "crypto", "bene_name": "", "bene_country": "",
                         "wallet": addr, **empty_id,
                         "expected_verdict": "NO_MATCH", "scenario": "crypto_clean"})
        else:                                 # 0.5% sanctioned crypto (real wallet)
            addr = RNG.choice(wallet_names) if wallet_names else "0xdead"
            rows.append({**common, "channel": "crypto", "bene_name": "", "bene_country": "",
                         "wallet": addr, **empty_id,
                         "expected_verdict": "MATCH", "scenario": "crypto_sanctioned"})

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
