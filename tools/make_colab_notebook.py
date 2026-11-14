"""Builds notebooks/gemma_live.ipynb, the jury's "see Gemma live" Colab notebook. Run: python tools/make_colab_notebook.py"""
import nbformat as nbf
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
C = []

C.append(md("""# BioSentinel Family · Gemma 4 live

**Nasab Labs** · Future Health Digital Innovation Challenge, Challenge 03 (Understanding and Reducing Inherited Disease Risk)

The [online demo](https://biosentinel-family.onrender.com) runs on a free server without a GPU, so its AI rewriting is switched off. This notebook runs the **same code** from [GitHub](https://github.com/SlimSkan/biosentinel-family) with **Gemma 4 on Colab's free GPU**, so you can see the AI part working and its safety checks.

**How to run it (about 8 minutes, mostly downloading Gemma):**
1. **Runtime → Change runtime type → T4 GPU → Save.**
2. **Runtime → Run all.**

It runs on your own Colab session. All people and results are **fictional**.

**What you will see:**
1. Gemma rewriting reviewed explanations for different readers and reading levels, in English and Arabic, and what the guardrails decided.
2. The guardrails blocking unsafe text: invented numbers, pressure about marriage, a dropped safety fact.
3. The full test suite.
4. The whole app running here, with Gemma switched on."""))

C.append(md("## 1. Check the GPU"))
C.append(code("""import subprocess
gpu = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout
print(gpu or "No GPU found. Use Runtime > Change runtime type > T4 GPU, then Runtime > Run all.\\n"
             "(It also works without a GPU if you set MODEL = 'gemma4:e2b' below, but slowly.)")"""))

C.append(md("## 2. Get the code and install Ollama\nOllama is a small program that runs open models such as Gemma on your own machine (here, Colab's)."))
C.append(code("""!git clone -q --depth 1 https://github.com/SlimSkan/biosentinel-family.git /content/biosentinel-family 2>/dev/null || echo "already downloaded"
%cd /content/biosentinel-family
!pip install -q -r requirements.txt
!apt-get -qq update > /dev/null && apt-get -qq install -y zstd pciutils > /dev/null
!curl -fsSL https://ollama.com/install.sh | sh > /dev/null 2>&1
!ollama --version"""))

C.append(md("## 3. Start Gemma 4\n`gemma4:e4b` (about 10 GB) fits the T4's 16 GB of GPU memory. `gemma4:e2b` (about 7 GB) is smaller and faster."))
C.append(code("""import os, time, httpx

MODEL = "gemma4:e4b"
os.environ["BSF_MODEL"] = MODEL                       # the app reads the model name from here

server = subprocess.Popen(["ollama", "serve"], env={**os.environ, "OLLAMA_KEEP_ALIVE": "-1"},
                          stdout=open("/content/ollama.log", "w"), stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        httpx.get("http://127.0.0.1:11434/api/version", timeout=2)
        print("Ollama is running")
        break
    except Exception:
        time.sleep(1)"""))
C.append(code("""!ollama pull $MODEL 2>&1 | tail -n 1"""))

C.append(md("""## 4. Gemma rewrites, checked by the guardrails

For each case the app takes a **reviewed explanation** (written in advance, always correct), asks Gemma to rewrite it for the reader, then runs **six guardrails** on Gemma's text:
numbers must come from the genetics rules · no pressure about marriage or pregnancy · a carrier is never called ill · short enough for a phone · every key fact and number kept · in Arabic, no assuming the reader is a woman.

If any check fails, the reader sees the reviewed text instead. Every number comes from deterministic genetics rules (`app/risk_engine.py`), never from Gemma."""))
C.append(code('''import sys, html
sys.path.insert(0, "/content/biosentinel-family")
from app import explainer, guardrails, risk_engine
from IPython.display import HTML, display

# Keep a copy of Gemma's raw answer, so we can show it even when the guardrails reject it.
_ask = explainer._ask_gemma
raw = {}
def _spy(system, user):
    raw["text"] = _ask(system, user)
    return raw["text"]
explainer._ask_gemma = _spy

def show(title, key, gene, lang, level, allowed, pct=None):
    reviewed = explainer.template_text(key, gene, lang, level, pct)
    t0 = time.time()
    out = explainer.explain(key, gene, lang, level, allowed, use_ai=True, pct=pct)
    secs = time.time() - t0
    gemma = explainer._clean(raw.get("text", "")) if raw.get("text") else "(Gemma did not answer)"
    ok = out["source"] == "ai"
    verdict = ("<b style='color:#1f6f6b'>Passed all checks: the reader sees Gemma's text</b>" if ok else
               "<b style='color:#9a5b13'>Rejected: the reader sees the reviewed text</b><br>"
               + html.escape("; ".join(out["problems"])))
    d = "rtl" if lang == "ar" else "ltr"
    display(HTML(f"""<div style="border:1px solid #d9d0c5;border-radius:8px;padding:10px 14px;margin:10px 0">
      <div style="font-weight:600">{html.escape(title)}</div>
      <div style="color:#7a706a;font-size:12px">{key} · {gene} · {lang} · {level} · {secs:.0f}s</div>
      <div style="margin-top:6px;color:#7a706a;font-size:13px">Reviewed text</div>
      <div dir="{d}" style="background:#f1ece5;padding:8px;border-radius:6px">{html.escape(reviewed)}</div>
      <div style="margin-top:6px;color:#7a706a;font-size:13px">Gemma 4</div>
      <div dir="{d}" style="background:#e0eeec;padding:8px;border-radius:6px">{html.escape(gemma)}</div>
      <div style="margin-top:6px">{verdict}</div></div>"""))
    raw.clear()
    return ok

cases = [
    ("Amina's own result, simple words", "carrier_self", "HBB", "en", "simple", {0, 100}, None),
    ("Amina's own result, in Arabic", "carrier_self", "HBB", "ar", "standard", {0, 100}, None),
    ("X-linked result for a woman (must keep the fava-bean trigger)", "xl_carrier_female", "G6PD", "en", "simple", {0, 50, 100}, None),
    ("The couple's shared result, in Arabic", "ar_both_carriers", "HBB", "ar", "standard", {0, 25, 50, 100}, None),
    ("A first cousin opening a family invite (12.5% chance)", "relative_ar", "HBB", "en", "standard", {0, 100, 12.5}, 12.5),
    ("An uncertain result (VUS), more detail", "vus", "BTD", "en", "detailed", {0, 100}, None),
]
passed = sum(show(*c) for c in cases)
print(f"Gemma's text passed all checks in {passed} of {len(cases)} cases."
      + ("" if passed == len(cases) else " In the others the reader safely saw the reviewed text instead."))'''))

C.append(md("""## 5. The guardrails blocking unsafe text

These texts are written on purpose to break the rules. Each must be rejected. The last one imitates a real failure we saw while testing: a short rewrite that dropped the fava-bean trigger, a safety fact for G6PD deficiency."""))
C.append(code('''unsafe = [
    "There is a 30% chance your child is affected.",
    "There is a 1 in 3 chance.",
    "You should not marry each other.",
    "You have sickle cell disease.",
    "يجب عليكما عدم الزواج.",
    "احتمال ٣٠٪ أن يتأثر الطفل.",
]
REASON = {"numbers": "Invented number (not from the genetics rules)", "directive": "Pushes a decision about marriage or pregnancy",
          "diagnosis": "Calls a healthy carrier ill"}
def reasons(text):
    problems = guardrails.check(text, {0, 25, 50, 100})
    return "; ".join(REASON.get(p.split()[0], p) + (f" {p.split(':')[1].strip()}" if p.startswith("numbers") else "")
                     for p in problems) or "NOT CAUGHT"
rows = "".join(f"<tr><td dir='auto'>{html.escape(t)}</td><td>{html.escape(reasons(t))}</td></tr>" for t in unsafe)
display(HTML(f"<table><tr><th>Text</th><th>Why it is rejected</th></tr>{rows}</table>"))

# A rewrite that forgets the fava-bean trigger:
dropped = ("You carry a change in the G6PD gene, on the X chromosome. Women who carry it are usually healthy. "
           "Each son has a 50% chance of being affected and each daughter a 50% chance of being a carrier, "
           "whatever your partner's result. Some medicines can be a trigger. A genetic counsellor can help.")
explainer._ask_gemma = lambda *a: dropped
out = explainer.explain("xl_carrier_female", "G6PD", "en", "simple", {0, 50, 100}, use_ai=True)
explainer._ask_gemma = _spy
print("Dropped-fact rewrite ->", out["source"], out["problems"])'''))

C.append(md("## 6. Run the test suite\nThe safety-critical parts are covered by automatic tests: risk numbers, guardrails, private matching maths, report import and the privacy of the API."))
C.append(code("!cd /content/biosentinel-family && python -m pytest -q 2>&1 | tail -n 3"))

C.append(md("""## 7. Open the full app, with Gemma switched on

This starts the app inside this Colab session and opens it in a new browser tab.
- Choose **Amina**, answer the quick check, and press **Rewrite with Gemma 4** on a result.
- For the private match, open the app link in a second tab and choose **Khalid**.
- **Import my lab report (PDF)** works too; fictional reports are offered on that page.

The app link only works while this notebook is running."""))
C.append(code('''app_server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
                              cwd="/content/biosentinel-family", env={**os.environ, "BSF_MODEL": MODEL},
                              stdout=open("/content/app.log", "w"), stderr=subprocess.STDOUT)
for _ in range(30):
    try:
        print("App health:", httpx.get("http://127.0.0.1:8000/api/health", timeout=10).json()["ai"])
        break
    except Exception:
        time.sleep(1)

from google.colab import output
output.serve_kernel_port_as_window(8000, path="/", anchor_text="Open BioSentinel Family (with Gemma 4)")'''))

C.append(md("""---
**Limits, stated openly:** a prototype, not a medical device; all data is fictional; the Arabic texts still need review by a native speaker and a genetic counsellor. Full design notes and known limits: [docs/HOW_IT_WORKS.md](https://github.com/SlimSkan/biosentinel-family/blob/main/docs/HOW_IT_WORKS.md).

© 2026 Nasab Labs. All rights reserved."""))

nb.cells = C
nb.metadata = {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4", "name": "gemma_live.ipynb"},
               "kernelspec": {"name": "python3", "display_name": "Python 3"}, "language_info": {"name": "python"}}
out = REPO / "notebooks" / "gemma_live.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.validate(nb)
nbf.write(nb, str(out))
print("wrote", out, "cells:", len(C))
