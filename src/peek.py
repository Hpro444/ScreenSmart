"""Quick structural peek at downloaded files (headers, row counts, sample)."""
import pathlib, csv, itertools
RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

def head_csv(p, n=3):
    with open(p, encoding="utf-8", errors="replace", newline="") as f:
        rdr = csv.reader(f)
        rows = list(itertools.islice(rdr, n))
    return rows

for name in ["opensanctions_sanctions.csv", "ofac_sdn.csv", "uk_ofsi_conlist.csv"]:
    p = RAW / name
    if not p.exists():
        continue
    print("=" * 90)
    print(name)
    rows = head_csv(p, 3)
    for i, r in enumerate(rows):
        print(f"  row{i} ({len(r)} cols): {str(r)[:300]}")
