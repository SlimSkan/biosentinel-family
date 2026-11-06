"""Check a running BioSentinel Family deployment, end to end, over HTTP.

    python deploy/smoke_test.py https://bsf-web.<...>.azurecontainerapps.io
    python deploy/smoke_test.py http://localhost:8000 --no-ai

Standard library only, so it runs anywhere Python does. It creates one family
invite (harmless, expires in 30 days) and sends no counsellor case.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
CHECK_AI = "--no-ai" not in sys.argv
failures = 0


def call(path, body=None, headers=None, timeout=60):
    req = urllib.request.Request(BASE + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def check(name, ok, detail=""):
    global failures
    failures += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


status, h = call("/api/health")
check("server answers /api/health", status == 200 and h["ok"], f"version {h and h['version']}")
if h:
    check("Gemma reachable from the server", h["ai"].get("reachable", False) or not CHECK_AI, json.dumps(h["ai"]))

status, people = call("/api/personas")
check("demo personas load", status == 200 and len(people) >= 4)

status, f = call("/api/explain/finding", {"gene": "HBB", "classification": "Pathogenic", "sex": "F", "lang": "ar"})
check("reviewed Arabic explanation", status == 200 and f["source"] == "template" and "HBB" in f["text"])

status, c = call("/api/explain/couple", {"shared_genes": ["HBB"], "lang": "en"})
check("couple risk is 25/50/25", status == 200 and
      (c["risks"][0]["affected_pct"], c["risks"][0]["carrier_pct"]) == (25, 50))

status, inv = call("/api/invites", {"gene": "HBB", "classification": "Pathogenic"})
check("family invite created", status == 200)
if status == 200:
    s, e = call(f"/api/invites/{inv['id']}/explain", {"relation": "first_cousin", "lang": "en"})
    check("relative sees 12.5% for a first cousin", s == 200 and e["chance_pct"] == 12.5)
    s, _ = call(f"/api/invites/{inv['id']}/status")
    check("invite counters need the owner secret", s == 403)

status, _ = call("/api/cases")
check("counsellor inbox is protected", status == 401,
      "open to anyone: set BSF_COUNSELLOR_KEY" if status == 200 else "")

if CHECK_AI:
    t = time.time()
    status, a = call("/api/explain/finding", {"gene": "G6PD", "classification": "Pathogenic", "sex": "F",
                                              "lang": "en", "level": "simple", "ai": True}, timeout=240)
    secs = time.time() - t
    ok = status == 200 and a["source"] == "ai"
    check("Gemma rewrite passes the guardrails", ok,
          f"{secs:.0f}s" + ("" if ok else f", fell back to template: {a and a['problems']}"))

print(f"\n{'All checks passed' if not failures else f'{failures} check(s) failed'} for {BASE}")
sys.exit(1 if failures else 0)
