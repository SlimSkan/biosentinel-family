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
Gemma 4 runs live in the demo (hosted by Google through the Gemini API).

1. **Counsellor first:** open `/counsellor.html` in one tab (key on slide 11). This registers it as a
   counsellor device, so cases can be encrypted for it.
2. Open the demo twice more. Choose **Amina** in one tab and **Khalid** in the other.
   Read each result (switch to العربية at the top), **ask Gemma a question** about it, and answer
   the quick check: get one wrong to see Gemma re-explain that idea.
3. In Amina's tab, tick consent and **Start**; send the code by WhatsApp or type it in Khalid's tab,
   who ticks consent and presses **Join**. Both see only **HBB**, never each other's other results.
4. **Compare options** side by side and see the next-steps plan.
5. Step 6: the **family carrier map**. Tap Amina's mother and mark "Tested: does not carry it":
   the map shows the change came from the father's side.
6. Step 5: choose a service, **prepare the summary** (Gemma's summary cites its sources), then
   **Encrypt and send**. The counsellor tab decrypts it; set "Appointment offered" and watch
   Amina's tracker update.
7. Home page: **Import my lab report** with a fictional PDF or **HL7 FHIR** file (`web/samples/`).
   Read on the device, never uploaded; you confirm the results first.

On a phone, use the browser menu's **Add to Home screen** to install it.

## See Gemma 4 live

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SlimSkan/biosentinel-family/blob/main/notebooks/gemma_live.ipynb)

Want to see Gemma 4 run on an open GPU instead of Google's API? This Colab notebook runs the same code with
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
| Language | `app/explainer.py`, `app/guardrails.py`, `app/llm.py` | Gemma 4 rewrites reviewed texts; six safety checks, fallback to the reviewed text |
| Tutor | `app/tutor.py` | Re-explains missed ideas; answers questions from cited facts only |
| Options | `web/options.js` | Side-by-side, unranked option comparison and next-steps plan |
| Family map | `risk_engine.family_map()`, `web/familytree.js` | Relatives' chances, updated when relatives are marked as tested |
| Referral | `app/brief.py`, `web/seal.js`, `web/counsellor.html` | Explainable brief, end-to-end encrypted, status tracking |
| Report import | `web/report_reader.js`, `web/report_parser.js`, `web/fhir_parser.js` | Reads a PDF or HL7 FHIR Genomics result in the browser; rules, not AI; the person confirms |
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
