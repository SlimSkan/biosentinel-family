# BioSentinel Family

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SlimSkan/biosentinel-family/blob/main/notebooks/gemma_live.ipynb)

**Know together. Decide freely.** A private, Arabic–English companion that helps couples in the
UAE understand their premarital genetic screening results, find out privately whether they carry
a change in the same gene, and reach a genetic counsellor.

Built by **Nasab Labs** for the Future Health Digital Innovation Challenge (Fertility · Challenge 03,
Understanding and Reducing Inherited Disease Risk).

## Try the live demo

**[Open the demo](https://biosentinel-family.onrender.com)**. No login is needed; all people in it are fictional.
The demo sleeps when nobody uses it: the first visit can take about a minute to wake it up.

1. Open the demo twice, in two browser tabs. Choose **Amina** in one and **Khalid** in the other.
   On a phone, use the browser menu's **Add to Home screen** (or **Install app**) to install it with its own icon.
2. Read each result (switch to العربية at the top), then answer the three quick-check questions.
3. In Amina's tab, tick the consent box and **Start**. Send the code with the WhatsApp button, or type
   it in Khalid's tab; Khalid ticks consent and presses **Join**.
   Both see only **HBB**, the one gene they share, never each other's other results.
4. See the risk grid and the options, then send a request to the counsellor
   (`/counsellor.html`).
5. In Amina's step 6, create a **family invite** and open it: a relative chooses how they are
   related and sees their own chance (for example 12.5% for a first cousin).
6. On the home page, choose **Import my lab report (PDF)** and use one of the fictional reports
   offered there (or in `web/samples/`). The PDF is read on the device, never uploaded; you check the
   results before they are used.

The online demo runs on a free server without a GPU, so the AI rewriting (Gemma 4) is switched off there and the
reviewed texts are shown. Run it locally with Ollama to see Gemma's rewrites.

## See Gemma 4 live

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SlimSkan/biosentinel-family/blob/main/notebooks/gemma_live.ipynb)

The online demo has no GPU, so its AI rewriting is off. This Colab notebook runs the same code with
**Gemma 4 on Colab's free T4 GPU**, in your own Colab session: Gemma's rewrites in English and
Arabic with the guardrails' decisions, the guardrails blocking unsafe text, the test suite, and the
full app with Gemma switched on. Choose **Runtime → Change runtime type → T4 GPU**, then
**Runtime → Run all** (about 8 minutes, mostly downloading Gemma).

## How it works

| Part | Files | Job |
|---|---|---|
| Facts | `data/panel_kb.json`, `app/knowledge.py` | Reviewed facts on 10 genes, in Arabic and English |
| Rules | `app/risk_engine.py` | Every number shown (25% / 50% / 25%, relatives' chances); no AI |
| Private match | `web/psi.js`, `app/psi_reference.py` | Private set intersection: only shared genes are revealed |
| Language | `app/explainer.py`, `app/guardrails.py` | Gemma 4 rewrites reviewed texts; six safety checks, fallback to the reviewed text |
| Report import | `web/report_reader.js`, `web/report_parser.js` | Reads a PDF lab report in the browser; finds results with rules; the person confirms |
| Server | `app/main.py` | FastAPI; sees no names and no full results |

The full learning guide is in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## Run it on your computer

```bash
pip install -r requirements.txt
ollama pull gemma4:e4b          # optional: without it, the reviewed texts are used
python -m uvicorn app.main:app --port 8010
```

Then open http://localhost:8010. In VS Code: open this folder, Run and Debug (Ctrl+Shift+D),
"BioSentinel Family: run app", F5.

## Test it

```bash
python -m pytest -q
```

## Deploy to Azure

See [deploy/README.md](deploy/README.md): Container Apps, with Gemma 4 on a serverless GPU.

## Status and limits

All data is fictional. This is a prototype: not a medical device, not clinically validated, and
the Arabic texts still need review by a native speaker and a genetic counsellor. Known limits are
listed in section 6 of [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

© 2026 Nasab Labs. All rights reserved. The code is published for evaluation; no licence to reuse
it is granted. Gene facts summarised from Orphanet (CC BY 4.0) and ClinVar (public domain).
