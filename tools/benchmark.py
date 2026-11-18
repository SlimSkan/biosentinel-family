"""Concordance benchmark: does the app agree with independent calculations?

1. Couples: 100 seeded synthetic couples with random pathogenic / likely pathogenic / VUS / benign
   results. The app's own path is used end to end: the PSI item rules (web/match_items.js, run in
   Node) and risk_engine.couple_risk(). The reference is computed here, separately, by enumerating
   the Punnett square of each gene (one copy from each parent) and comparing variant ids directly.
2. Family map: each relative's chance in risk_engine.family_map() versus the coefficient of
   relationship, computed here by counting paths through common ancestors in the pedigree
   (a different method from the app's halving rule).
3. Simulator: 100,000 random pregnancies from web/simulator.js versus 25 / 50 / 25 %.

Run: python tools/benchmark.py   (writes docs/BENCHMARK.md and prints a summary)
"""
import itertools
import json
import random
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import knowledge, risk_engine  # noqa: E402

CLASSES = ["Pathogenic", "Likely pathogenic", "Uncertain significance", "Likely benign"]
COUNTED = {"Pathogenic", "Likely pathogenic"}


def node(script: str, stdin: str = "") -> str:
    return subprocess.run([shutil.which("node"), "--input-type=module", "-e", script], input=stdin,
                          capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- 1. couples
def synthetic_couples(n=100, seed=2026):
    rng = random.Random(seed)
    genes = list(knowledge.kb()["genes"])
    couples = []
    for _ in range(n):
        pair = []
        for _person in range(2):
            pick = rng.sample(genes, rng.randint(0, 3))
            # bias towards overlaps so that shared genes are common enough to test
            if pair and rng.random() < 0.5 and pair[0]:
                pick = list({*pick, rng.choice(pair[0])["gene"]})
            pair.append([{"gene": g, "variant": f"c.{rng.choice([100, 200])}A>G", "classification": rng.choice(CLASSES)}
                         for g in pick])
        couples.append(pair)
    return couples


def reference(a, b):
    """Independent answer: Punnett enumeration per gene, VUS and benign excluded, XL never a couple risk."""
    out = {}
    for gene in sorted({v["gene"] for v in a} & {v["gene"] for v in b}):
        va = [v for v in a if v["gene"] == gene and v["classification"] in COUNTED]
        vb = [v for v in b if v["gene"] == gene and v["classification"] in COUNTED]
        if not va or not vb or knowledge.gene(gene)["inheritance"] != "AR":
            continue
        kids = [x + y for x, y in itertools.product([0, 1], [0, 1])]          # 1 = changed copy
        out[gene] = {"affected": Fraction(kids.count(2), 4), "carrier": Fraction(kids.count(1), 4),
                     "neither": Fraction(kids.count(0), 4),
                     "same": bool({v["variant"] for v in va} & {v["variant"] for v in vb})}
    return out


def app_answer(couples):
    mod = (ROOT / "web" / "match_items.js").as_uri()
    script = (f"import {{psiItems, readMatch}} from '{mod}';"
              "let d = ''; process.stdin.on('data', (c) => d += c); process.stdin.on('end', () => {"
              "  const out = JSON.parse(d).map(([a, b]) => { const A = psiItems(a), B = new Set(psiItems(b));"
              "    return readMatch(A.filter((x) => B.has(x))); });"
              "  console.log(JSON.stringify(out)); });")
    matches = json.loads(node(script, json.dumps(couples)))
    answers = []
    for m in matches:
        answers.append({r.gene: {"affected": Fraction(r.affected).limit_denominator(100),
                                 "carrier": Fraction(r.carrier).limit_denominator(100),
                                 "neither": Fraction(r.unaffected).limit_denominator(100),
                                 "same": r.variant_match == "same"}
                        for r in risk_engine.couple_risk(m["shared"], m["sameVariant"])})
    return answers


# ---------------------------------------------------------------- 2. family map
def relationship_coefficient(a: str, b: str) -> Fraction:
    """r = sum over common ancestors of (1/2)^(steps a->ancestor + steps ancestor->b), plus direct lines."""
    parents = {k: v[2] for k, v in risk_engine.PEDIGREE.items()}

    def ancestors(x, d=0):
        yield x, d
        for p in parents.get(x, []):
            yield from ancestors(p, d + 1)

    if b in dict(ancestors(a)) or a in dict(ancestors(b)):            # direct line (parent, grandparent, child)
        da, db = dict(ancestors(a)), dict(ancestors(b))
        return Fraction(1, 2 ** (da.get(b, db.get(a))))
    da, db = dict(ancestors(a)), dict(ancestors(b))
    common = set(da) & set(db)
    # only the closest common ancestors (not their own ancestors) start independent paths
    closest = {c for c in common if not any(c in dict(ancestors(o)) and o != c for o in common)}
    return sum((Fraction(1, 2 ** (da[c] + db[c])) for c in closest), Fraction(0))


def family_check():
    rows = []
    m = {n["id"]: n["pct"] for n in risk_engine.family_map("HBB")["nodes"]}
    for rid in risk_engine.PEDIGREE:
        if rid == "me":
            continue
        ref = float(relationship_coefficient("me", rid) * 100)
        rows.append((rid, m[rid], ref, abs(m[rid] - ref) < 1e-9))
    return rows


# ---------------------------------------------------------------- 3. simulator
def simulator_check(n=100_000):
    mod = (ROOT / "web" / "simulator.js").as_uri()
    out = node(f"import {{draw}} from '{mod}'; const c = {{}};"
               f"for (let i = 0; i < {n}; i++) {{ const o = draw('AR'); c[o] = (c[o] || 0) + 1; }}"
               "console.log(JSON.stringify(c));")
    c = json.loads(out)
    return {k: c.get(k, 0) / n for k in ("affected", "carrier", "neither")}


def run():
    couples = synthetic_couples()
    refs = [reference(a, b) for a, b in couples]
    apps = app_answer(couples)
    agree = sum(r == a for r, a in zip(refs, apps))
    at_risk = sum(bool(r) for r in refs)
    vus_only = sum(
        1 for (a, b), r in zip(couples, refs)
        if ({v["gene"] for v in a} & {v["gene"] for v in b}) and not r)
    genes_flagged = sum(len(r) for r in refs)
    diff_variant = sum(1 for r in refs for g in r.values() if not g["same"])
    fam = family_check()
    sim = simulator_check()
    sim_ok = all(abs(sim[k] - e) < 0.01 for k, e in (("affected", .25), ("carrier", .5), ("neither", .25)))
    return {"couples": len(couples), "agree": agree, "at_risk": at_risk, "genes_flagged": genes_flagged,
            "different_variant": diff_variant, "overlap_not_flagged": vus_only, "family": fam,
            "family_agree": sum(r[3] for r in fam), "sim": sim, "sim_ok": sim_ok}


def write_report(res):
    fam_rows = "\n".join(f"| {rid} | {app}% | {ref:g}% | {'yes' if ok else 'NO'} |" for rid, app, ref, ok in res["family"])
    md = f"""# Concordance benchmark

Generated by `python tools/benchmark.py`. Synthetic data only: this checks that the software
computes what the genetics rules say; it is not a clinical validation.

## 1. Couples (private match + risk engine vs. independent Punnett enumeration)

| Measure | Result |
|---|---|
| Synthetic couples (seed 2026) | {res['couples']} |
| Couples where the app and the reference agree exactly | **{res['agree']} / {res['couples']}** |
| At-risk couples (shared pathogenic / likely pathogenic, autosomal recessive) | {res['at_risk']} |
| Shared genes flagged | {res['genes_flagged']} (of which {res['different_variant']} with different variants) |
| Couples sharing a gene that must NOT be flagged (a VUS, benign, or X-linked) | {res['overlap_not_flagged']}, none flagged |

## 2. Family carrier map vs. coefficient of relationship

| Relative | App | Reference | Agree |
|---|---|---|---|
{fam_rows}

**{res['family_agree']} / {len(res['family'])}** relatives agree.

## 3. Simulator (100,000 random pregnancies)

Affected {res['sim']['affected']:.3f} · carrier {res['sim']['carrier']:.3f} · neither {res['sim']['neither']:.3f}
(expected 0.25 / 0.50 / 0.25): **{'within 1 point' if res['sim_ok'] else 'OUT OF RANGE'}**.
"""
    (ROOT / "docs" / "BENCHMARK.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    res = run()
    write_report(res)
    print(f"couples {res['agree']}/{res['couples']} agree; at-risk {res['at_risk']}; "
          f"overlaps correctly not flagged {res['overlap_not_flagged']}; family {res['family_agree']}/{len(res['family'])}; "
          f"simulator ok={res['sim_ok']}")
