"""
Offline job — mine market-basket association rules from `transactions` and write
them to the `assocrules` collection (read by pipeline/assoc_rules.py at serve
time).

Mines rules for several contexts:
  - "any" (all transactions)
  - per timeOfDay (breakfast/lunch/afternoon/dinner/late)
  - per dineMode (dine_in/takeaway)

Only single-item consequents are kept (simple to serve). Run after seeding:
    python -m app.mine_rules
"""
import itertools
from collections import defaultdict

import pandas as pd
from mlxtend.frequent_patterns import fpgrowth, association_rules
from mlxtend.preprocessing import TransactionEncoder

from app.config import config
from app.db import get_db

TIMES = ["breakfast", "lunch", "afternoon", "dinner", "late"]
DINES = ["dine_in", "takeaway"]


def _baskets(txs):
    out = []
    for tx in txs:
        skus = sorted({l["sku"] for l in tx.get("lines", []) if l.get("sku")})
        if len(skus) >= 2:  # need co-occurrence
            out.append(skus)
    return out


def _mine(baskets, context, min_support, min_conf):
    if len(baskets) < 30:
        return []
    te = TransactionEncoder()
    arr = te.fit(baskets).transform(baskets)
    df = pd.DataFrame(arr, columns=te.columns_)
    freq = fpgrowth(df, min_support=min_support, use_colnames=True)
    if freq.empty:
        return []
    rules = association_rules(freq, metric="confidence", min_threshold=min_conf)
    if rules.empty:
        return []
    docs = []
    for _, row in rules.iterrows():
        cons = list(row["consequents"])
        if len(cons) != 1:  # keep single-item consequents
            continue
        ante = sorted(list(row["antecedents"]))
        if len(ante) > 2:  # cap antecedent size for fast subset matching
            continue
        docs.append({
            "antecedent": ante,
            "consequent": cons[0],
            "support": float(row["support"]),
            "confidence": float(row["confidence"]),
            "lift": float(row["lift"]),
            "context": context,
        })
    return docs


def main():
    db = get_db()
    all_tx = list(db.transactions.find({}, {"lines.sku": 1, "timeOfDay": 1, "dineMode": 1}))
    print(f"[mine] loaded {len(all_tx)} transactions")

    jobs = [("any", "any", all_tx)]
    for t in TIMES:
        jobs.append((t, "any", [x for x in all_tx if x.get("timeOfDay") == t]))
    for d in DINES:
        jobs.append(("any", d, [x for x in all_tx if x.get("dineMode") == d]))

    all_docs = []
    for tod, dine, subset in jobs:
        baskets = _baskets(subset)
        docs = _mine(baskets, {"timeOfDay": tod, "dineMode": dine},
                     config.MIN_SUPPORT, config.MIN_CONFIDENCE)
        print(f"[mine] context(time={tod}, dine={dine}): {len(baskets)} baskets → {len(docs)} rules")
        all_docs.extend(docs)

    db.assocrules.delete_many({})
    if all_docs:
        db.assocrules.insert_many(all_docs)
    db.assocrules.create_index([("antecedent", 1)])
    db.assocrules.create_index([("consequent", 1)])
    print(f"[mine] wrote {len(all_docs)} rules to assocrules")


if __name__ == "__main__":
    main()
