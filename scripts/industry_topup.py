"""Occasional small top-up (monthly or on demand), never in the nightly run: label the companies added since the last bulk run with
claude-haiku-5-5 (Batches API), then retrain the local model. Same key rules as label_industry_bulk.py.

Usage: ANTHROPIC_API_KEY=... python scripts/industry_topup.py SHARD_DIR [--limit 3000] [--max-usd 5]
"""
import subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
a = sys.argv[1:]
limit = a[a.index("--limit") + 1] if "--limit" in a else "3000"
cap = a[a.index("--max-usd") + 1] if "--max-usd" in a else "5"
sys.argv = [sys.argv[0], a[0], "--max-usd", cap]
sys.path.insert(0, str(root / "scripts"))
import industry_ai
from jobalfred_index import ailabel
ai = ailabel.AiLabels()
groups, units = industry_ai.load_units(a[0], ai)
units = units[:int(limit)]                    # the biggest employers among the not-yet-labelled ones
est = ailabel.estimate(units)
print(f"{len(units)} companies, estimated ${est['usd_batch']}")
if est["usd_batch"] > float(cap):
    sys.exit("above the limit")
client = ailabel.make_client(timeout=120)
if client is None:
    sys.exit("ANTHROPIC_API_KEY is not set in this shell. Nothing was sent.")
import time
ids = ailabel.bulk_submit(units, client)
for bid in ids:
    while client.messages.batches.retrieve(bid).processing_status != "ended":
        time.sleep(60)
print(ailabel.bulk_collect(ai, units, client, ids))
subprocess.run([sys.executable, str(root / "scripts" / "industry_train_local.py")], check=True)
