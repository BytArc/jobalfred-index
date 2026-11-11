"""One-off bulk industry labelling by claude-haiku-5-5 (Message Batches API), then retrain the free local model on the result.

Usage:  ANTHROPIC_API_KEY=... python scripts/label_industry_bulk.py [SHARD_DIR] [--max-usd 50] [--estimate-only] [--no-retrain]

  SHARD_DIR  a directory with the published shards and manifest.json; downloaded from the index-latest release with `gh` when omitted.
  Prints the company count and the cost estimate first and stops without spending anything above --max-usd (default 50).
  Waits for the batch to finish (usually under an hour, at most 24), writes data/industry/ai-labels.json.gz, then retrains
  data/industry/local-model.json.gz with scripts/industry_train_local.py (needs scikit-learn and numpy) unless --no-retrain.
The key is read from the environment by the SDK; it is never printed, logged or stored. If it is not set the script stops.
"""
import json, subprocess, sys, time
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "scripts"))
from jobalfred_index import ailabel
import industry_ai

a = sys.argv[1:]
shard_dir = next((x for x in a if not x.startswith("--") and not x.replace(".", "").isdigit()), None)
max_usd = float(a[a.index("--max-usd") + 1]) if "--max-usd" in a else 50.0
if shard_dir is None:
    shard_dir = str(root / "work" / "bulk-shards")
    Path(shard_dir).mkdir(parents=True, exist_ok=True)
    subprocess.run(["gh", "release", "download", "index-latest", "--repo", "BytArc/jobalfred-index", "--dir", shard_dir, "--clobber"], check=True)
ai = ailabel.AiLabels()
groups, units = industry_ai.load_units(shard_dir, ai)
est = ailabel.estimate(units)
print(f"{len(groups)} companies in the index; {len(units)} still to label.")
print(f"Estimated cost with the Batches API: ${est['usd_batch']} ({est['input_tokens']:,} input and {est['output_tokens']:,} output tokens; ${est['usd_standard']} at standard prices).")
if "--estimate-only" in a:
    sys.exit(0)
if est["usd_batch"] > max_usd:
    sys.exit(f"Above ${max_usd}: not submitting. Pass --max-usd to raise the limit.")
client = ailabel.make_client(timeout=120)
if client is None:
    sys.exit("ANTHROPIC_API_KEY is not set in this shell (or the anthropic package is missing: pip install anthropic). Nothing was sent.")
ids = ailabel.bulk_submit(units, client)
Path(root / "work").mkdir(exist_ok=True)
(root / "work" / "ai-batches.json").write_text(json.dumps({"ids": ids, "keys": [u["key"] for u in units]}))
print("submitted", ids, "- waiting for the batch (progress every minute)")
for bid in ids:
    while True:
        b = client.messages.batches.retrieve(bid)
        if b.processing_status == "ended":
            break
        print(f"  {bid}: {b.request_counts.processing} processing, {b.request_counts.succeeded} succeeded")
        time.sleep(60)
print(ailabel.bulk_collect(ai, [{"key": k} for k in json.loads((root / "work" / "ai-batches.json").read_text())["keys"]], client, ids))
if "--no-retrain" not in a:
    subprocess.run([sys.executable, str(root / "scripts" / "industry_train_local.py")], check=True)
print("Done. Commit data/industry/ai-labels.json.gz and data/industry/local-model.json.gz.")
