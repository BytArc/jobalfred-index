"""Train the local industry classifier (TF-IDF + logistic regression) and save its weights as data/industry/local-model.json.gz.

Needs scikit-learn and numpy (training machine only; the nightly run never imports them).
Usage: industry_train_local.py [--exclude eval-r4u.jsonl ...] [--min-ai-conf 0.7] [--ai-weight 1.0] [--hand-weight 3.0] [--out PATH] [--C 8]
Training labels: hand labels (labels.jsonl, eval-r*.jsonl) and, when present, the language-model labels (ai-labels.json.gz) at or above
--min-ai-conf. Company features come from work/ind/companies.pkl (rebuilt from the shards by scripts/industry_companies.py) and the homepage cache.
"""
import collections, gzip, json, pickle, sys
from pathlib import Path
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.linear_model import LogisticRegression

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import ailabel, industry as I, localclf

args = sys.argv[1:]
def opt(name, default, cast=str):
    return cast(args[args.index(name) + 1]) if name in args else default
exclude = set()
if "--exclude" in args:
    for a in args[args.index("--exclude") + 1:]:
        if a.startswith("--"):
            break
        exclude.add(a)
MIN_AI, AI_W, HAND_W, C = opt("--min-ai-conf", 0.7, float), opt("--ai-weight", 1.0, float), opt("--hand-weight", 3.0, float), opt("--C", 8.0, float)
OUT = Path(opt("--out", str(localclf.FILE)))
D = root / "data" / "industry"
comp = pickle.load(open(root / "work" / "ind" / "companies.pkl", "rb"))
hp = I.Homepages()
tax = [c for c in json.loads((D / "taxonomy.json").read_text()) if c != I.NOT_STATED]


def company_features(k):
    c = comp.get(k)
    if not c:
        return None
    entry = hp.get("c:" + k)
    hosts = ["https://" + h + "/" for h in c["hosts"]]
    domain = I.own_domain(hosts) or (entry or {}).get("d", "")
    return localclf.featurize(c["name"], domain, (entry or {}).get("t", ""), (entry or {}).get("m", ""), c["words"], c["ats"], c["cc"]), domain


labels = {}                       # company key -> (code, weight)
for f in [D / "labels.jsonl"] + sorted(D.glob("eval-r*.jsonl")):
    if f.name in exclude:
        continue
    for line in f.read_text().splitlines():
        o = json.loads(line)
        if o["key"].startswith("c:") and o["ind"] in tax:
            labels[o["key"][2:]] = (o["ind"], HAND_W)
n_hand = len(labels)
ai = ailabel.AiLabels()
if ai.data:
    by_domain = collections.defaultdict(list)
    for k, c in comp.items():
        d = I.own_domain(["https://" + h + "/" for h in c["hosts"]])
        if d:
            by_domain["d:" + d].append(k)
    for key, (code, conf, *_rest) in ai.data.items():
        if conf < MIN_AI or code not in tax:
            continue
        ks = by_domain.get(key, []) if key.startswith("d:") else ([key[2:]] if key.startswith("c:") and key[2:] in comp else [])
        for k in ks:
            labels.setdefault(k, (code, AI_W))
print(f"{n_hand} hand labels, {len(labels) - n_hand} language-model labels")
X, y, w = [], [], []
for k, (code, wt) in labels.items():
    cf = company_features(k)
    if cf:
        X.append(cf[0]); y.append(tax.index(code)); w.append(wt)
dv = DictVectorizer()
M = dv.fit_transform(X)
df = np.asarray((M > 0).sum(axis=0)).ravel()
keep = np.where(df >= 2)[0]
M = M[:, keep]
names = [dv.feature_names_[i] for i in keep]
tf = TfidfTransformer(sublinear_tf=True)
T = tf.fit_transform(M)
clf = LogisticRegression(C=C, max_iter=300, class_weight=None)
clf.fit(T, y, sample_weight=np.array(w))
classes = [tax[i] for i in clf.classes_]
coef = clf.coef_
W, idf = {}, {}
for j, name in enumerate(names):
    row = [(ci, round(float(coef[ci, j]), 3)) for ci in range(len(classes)) if abs(coef[ci, j]) >= 0.05]
    if row:
        W[name] = row
        idf[name] = round(float(tf.idf_[j]), 3)
model = {"classes": classes, "b": [round(float(b), 3) for b in clf.intercept_], "idf": idf, "w": W, "trained_on": len(y), "hand": n_hand,
         "ai": len(y) - n_hand, "C": C}
OUT.parent.mkdir(parents=True, exist_ok=True)
with gzip.open(OUT, "wt", encoding="utf-8") as fh:
    json.dump(model, fh, separators=(",", ":"), ensure_ascii=False)
print(f"trained on {len(y)} companies, {len(W)} features, {OUT.stat().st_size // 1024} KB -> {OUT}")
