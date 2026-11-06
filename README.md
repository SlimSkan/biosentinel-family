# BioSentinel Family

**Know together. Decide freely.** A private, Arabic–English companion that helps couples in the
UAE understand their premarital genetic screening results, find out privately whether they carry
a change in the same gene, and reach a genetic counsellor.

Built by **Nasab Labs** for the Future Health Digital Innovation Challenge (Fertility · Challenge 03,
Understanding and Reducing Inherited Disease Risk).

## Try the live demo

**[Open the demo](https://biosentinel-family.onrender.com)**. No login is needed; all people in it are fictional.
The demo sleeps when nobody uses it: the first visit can take about a minute to wake it up.

1. Open the demo twice, in two browser tabs. Choose **Amina** in one and **Khalid** in the other.
2. Read each result (switch to العربية at the top), then answer the three quick-check questions.
3. In Amina's tab, tick the consent box and **Start**; type the code in Khalid's tab and **Join**.
   Both see only **HBB**, the one gene they share, never each other's other results.
4. See the risk grid and the options, then send a request to the counsellor
   (`/counsellor.html`).
5. In Amina's step 6, create a **family invite** and open it: a relative chooses how they are
   related and sees their own chance (for example 12.5% for a first cousin).

The online demo runs on a free server without a GPU, so the AI rewriting (Gemma 4) is switched off there and the
reviewed texts are shown. Run it locally with Ollama to see Gemma's rewrites.

## How it works

| Part | Files | Job |
|---|---|---|
| Facts | `data/panel_kb.json`, `app/knowledge.py` | Reviewed facts on 10 genes, in Arabic and English |
| Rules | `app/risk_engine.py` | Every number shown (25% / 50% / 25%, relatives' chances); no AI |
| Private match | `web/psi.js`, `app/psi_reference.py` | Private set intersection: only shared genes are revealed |
| Language | `app/explainer.py`, `app/guardrails.py` | Gemma 4 rewrites reviewed texts; six safety checks, fallback to the reviewed text |
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
