# How BioSentinel Family works — a learning guide

This guide explains the prototype file by file, and the design ideas behind it.
Read it with the code open beside it. Every file is short and commented.

---

## 1. The big picture

```
 Amina's phone (browser)                 Server (FastAPI, Python)                Khalid's phone (browser)
 ───────────────────────                 ────────────────────────                ────────────────────────
 web/app.js  + web/psi.js                app/main.py                             web/app.js + web/psi.js
   │ her report (in page memory)           │                                       │ his report
   │ her secret PSI key  ───never sent──   │                                       │ his secret PSI key
   │                                       │                                       │
   │── one gene at a time ──────────────►  explain/finding ─► risk_engine          │
   │◄── explanation ────────────────────   │                 ─► explainer ─► llm.py ─► Gemma 4 (Gemini API or Ollama)
   │                                       │                 ─► guardrails         │
   │                                       │                                       │
   │── locked values ──────────────────►   PSI relay (mailbox)  ◄── locked values ─│
   │◄─────────────────────────────────     sees only random-looking numbers  ─────►│
   │                                       │                                       │
   │── shared genes only ──────────────►   explain/couple ─► risk_engine (25/50/25)│
   │── brief, ENCRYPTED on her phone ──►   cases (ciphertext) ─► counsellor.html   │
   │── "invite my family" (one gene) ──►   invites: random id + 2 counters         │
   │                                       │                                       │
                                     Relative's phone: invite.html?i=<random id>
                                     says how they are related (stays on the phone)
                                     ─► invites/{id}/explain ─► relative_chance()
```

Three layers, each with one job:

| Layer | Files | Job |
|---|---|---|
| Facts | `data/panel_kb.json`, `app/knowledge.py` | The only source of medical facts |
| Logic | `app/risk_engine.py`, `app/psi_reference.py`, `web/psi.js` | Deterministic, testable decisions and maths |
| Language | `app/explainer.py`, `app/guardrails.py` | Turning facts into words people understand, safely |

The server in `app/main.py` connects them; `web/` is what the user sees.

---

## 2. The journey of one request

Follow Amina when she opens her result:

1. `partner.html?p=amina` loads `app.js`, which calls `GET /api/personas/amina`.
   In real life the screening lab would deliver this report; here a demo file plays the lab.
2. For **each gene separately**, `app.js` calls `POST /api/explain/finding` with only
   `{gene, classification, sex, lang, level}`. No name, no other genes.
3. `main.py → explain_finding()` asks `risk_engine.individual_findings()` what kind of finding
   this is (ordinary carrier, X-linked carrier in a woman, or uncertain variant), and which
   numbers are allowed (`allowed_numbers()`).
4. `explainer.explain()` fills the reviewed **template** for that kind, in her language.
   If she pressed "Rewrite with Gemma 4", it also asks Gemma to rewrite the template.
5. `guardrails.check()` inspects Gemma's text. If anything is wrong, the template is used instead.
6. The answer returns with `source: "ai"` or `"template"`, shown as a badge on the card.

---

## 3. File by file

### `data/panel_kb.json` — the knowledge base
Ten genes, each with: inheritance (`AR` or `XL`), condition name and a short summary in
English and Arabic, and Orphanet codes. **Why a file and not the AI's memory?** Because a
file can be reviewed, versioned and signed off by a genetic counsellor. An AI's memory cannot.

### `data/personas.json` — fictional people
Amina and Khalid share HBB (sickle cell / beta-thalassaemia). Amina also carries G6PD
(X-linked) and GJB2; Khalid carries CFTR. Sara and Omar share nothing; Omar has a variant of
uncertain significance (VUS). Each pair exercises a different branch of the logic.

### `app/knowledge.py` — loading facts
Reads the two JSON files once (`@lru_cache` keeps them in memory) and gives simple accessors.

### `app/risk_engine.py` — the genetics rules
The most important file to understand, because **every number the user sees comes from here**.

- **Autosomal recessive (AR):** a child is affected only with a changed copy from both parents.
  Carrier × carrier gives the Punnett square: 1/4 affected, 1/2 carrier, 1/4 neither.
  That is `couple_risk()`.
- **X-linked (XL):** the gene is on the X chromosome. A carrier mother passes it to half of
  her sons (affected) and half of her daughters (carriers), *whatever the father's result*.
  So XL is never a "couple" finding; it is flagged to the woman herself in
  `individual_findings()`, and she decides whether to share it.
- **VUS:** we never interpret an uncertain variant. It always escalates to a counsellor.
- `allowed_numbers()` lists every percentage the AI may use, for the guardrails.

### `app/guardrails.py` — the safety net for AI text
Six checks. The first four catch what the AI **adds**: **numbers** (every "%" or "1 in N", in
English or Arabic, including Arabic-Indic digits, must be in the allowed set), **directive
language** ("you should not marry", "لا تتزوجوا"…), **diagnosis language** ("you have the
disease" for a carrier), and **length**. The fifth, **coverage**, catches what the AI **drops**:
every key fact and every number of the reviewed text must still be there.
The sixth, **gender**, is for Arabic, where "you" has a male and a female form: a rewrite may
not address the reader as a woman unless the reviewed text does (only the X-linked text for a
woman does). Gemma did this on a page for a relative of unknown sex, *even after the prompt
told it not to*.
The patterns are deliberately broad: a false alarm costs nothing because the reviewed template
is always correct.

**How coverage works.** Each fact is a small record:
`{"id": "fava", "say": "fava beans can trigger it", "en": ["fava", "broad bean"], "ar": ["الفول"]}`.
The `say` line is sent to Gemma as a "you MUST still say" list; the keywords are what
`missing_facts()` looks for afterwards (one is enough). Facts come from two places:
`TEMPLATE_FACTS` in `explainer.py` (one list per kind of finding: "carriers are healthy",
"same chance in each pregnancy", "the choice is yours"…) and `key_facts` per gene in
`panel_kb.json` (G6PD: fava beans, medicines). `normalise()` removes Arabic vowel marks and
unifies alef forms, so الأدوية and الادوية match. `missing_numbers()` compares the numbers in
the reviewed text with the rewrite, so dropping "50%" is caught too.

The same idea twice: **tell the model what matters, then check it did it.** Neither half is
enough alone. The prompt makes success likely; the check makes failure harmless.

### `app/explainer.py` — templates plus Gemma
- `TEMPLATES`: reviewed texts per finding type, language and level.
- `SYSTEM_PROMPT`: the rules Gemma must follow (only given facts, only allowed numbers, never
  directive, who the reader is, no added greetings).
- `explain()`: template first → optional Gemma rewrite → guardrails → fallback.
  If Ollama is not running, it silently falls back too. The app never breaks because the AI did.

Lessons from testing:
- Gemma's first Arabic rewrite passed every check, yet it addressed the *couple* on Amina's
  *private* result and added an unrequested blessing. The prompt now states the audience.
- The "simple" English G6PD text dropped the fava-bean trigger, a safety fact. That led to the
  coverage check. Across 30 rewrites (5 findings × 3 levels × 2 languages), it first rejected
  one: a **false alarm**, because Gemma wrote the feminine Arabic "ليست تشخيصاً" and the keyword
  list only had "ليس تشخيص". Reading the accepted texts also showed that "women carriers are
  usually healthy" was not on the required list, so it was added. After both fixes: 30/30
  accepted, and each new case became a test.
- Family invite texts, 16 rewrites: 5 first rejected, all the **same false alarm**: Gemma wrote
  "قرار إجراء الفحص هو اختيارك", and the keywords only had "الاختيار" with "ال". Keywords became
  stems ("اختيار", "قرار"). Reading the accepted texts found two real problems that no check
  caught: Gemma dropped "depends on which side of the family" (now a required fact), and it
  addressed a relative as a woman, "قد تحملين أنتِ" (now the gender check).
- In the browser, Gemma repeated the closing counsellor sentence twice; `_clean()` now drops a
  sentence repeated word for word.
Always read real outputs: tests prove the rules you thought of; reading finds the ones you didn't.
And a prompt rule makes a failure rarer; only a check makes it harmless.

### `app/psi_reference.py` and `web/psi.js` — private matching
Same algorithm twice: JavaScript runs in the phones; Python is used by the tests and is easier
to read. A test proves both produce identical numbers. See section 4.

### `app/main.py` — the server
FastAPI turns Python functions into web endpoints. `pydantic` models (`ExplainOne`, `Locked`…)
validate every input: unknown language, wrong sex code or a list over 64 items is refused
before any of our code runs. Endpoints:

| Endpoint | Purpose | What the server learns |
|---|---|---|
| `GET /api/personas/{id}` | demo lab delivers a report | (demo only) |
| `POST /api/explain/finding` | explain one gene | one gene, not linked to a name |
| `POST /api/match`, `/a1`, `/b1`, `/a2`, `GET /api/match/{code}` | PSI mailbox | random-looking numbers only |
| `POST /api/explain/couple` | explain the shared genes | the shared genes |
| `POST /api/cases`, `GET /api/cases` | counsellor inbox | only what the couple ticked |
| `POST /api/invites` | create a family invite | one gene; no name, no variant, no other genes |
| `GET /api/invites/{id}`, `POST …/explain`, `POST …/event` | relative's page | the relation, used once and not stored; two counters |
| `GET /api/invites/{id}/status` (header `X-Invite-Owner`) | sender's counters | nothing new |

Everything is stored in memory: restarting the server wipes it. Fine for a demo; a database
comes later.

### `web/app.js` — the phone app
One file, five steps, each a `render…()` function. `S` holds the state *in page memory only*.
`T` holds all text in English and Arabic; switching language sets `dir="rtl"`.
The **teach-back** quiz is in `renderQuiz()`: a wrong answer means *our* explanation failed,
so it switches to simpler wording and shows the right answers, without blame.
The match code is in `startMatch()` (Amina) and `joinMatch()` (Khalid).

### Family invites — `web/invite.html`, `web/invite.js`, step 6 in `app.js`
**Why:** when one person learns they carry a variant, their brothers, sisters and cousins have a
high chance of carrying it too, and most never find out. Telling relatives ("cascade testing")
finds many more carriers than screening strangers, but people find the conversation hard.

**How it protects everyone:**
- The link holds only a random id (`secrets.token_urlsafe`). The server stores the gene and two
  counters, nothing about the sender.
- The *relative* says how they are related, on their own phone, so the sender never has to
  label anyone. The relation is used to pick the number, then forgotten.
- The sender keeps a second secret, the `owner` token, in page memory. Only it can read the counters:
  "opened 3 times, 1 asked about next steps". Never who.
- Uncertain results (VUS) can never be sent (`can_invite()`): we must not spread an uncertain finding.
- The WhatsApp message does not name the gene, in case someone else reads the chat.

**The genetics (`relative_chance()` in `risk_engine.py`).** You inherited your variant from one
parent. Each step of relationship halves the chance that a relative inherited the same copy:
parent, child, brother or sister 1/2 (50%); half-sibling, grandparent, aunt, uncle, niece,
nephew 1/4 (25%); first cousin 1/8 (12.5%). These are minimums from your side; the population
chance comes on top, and it is higher when parents are related.
X-linked genes get **no** number: it depends on which side of the family and on the relative's
sex, which only a counsellor can work out. "I'm not sure" also gets no number.

12.5% forced a change in `guardrails._percentages()`: it now reads decimals (`12.5%`, Arabic
`١٢٫٥٪`, and "1 in 8").

### Import a lab report — `web/report_reader.js`, `web/report_parser.js`
The person can use their own PDF report instead of a demo person.
1. **Read in the browser.** `report_reader.js` uses pdf.js (Mozilla's PDF reader) to get the text,
   on the phone. The file is never uploaded, so the server still never sees a full result.
   Text pieces are grouped by their height on the page, so a table row stays one line.
2. **Find the results with rules, not AI.** `report_parser.js` looks, line by line, for a gene this
   app covers plus a classification (Pathogenic, Likely pathogenic, Uncertain significance).
   Lines like "No pathogenic variants detected in: CFTR, ..." name genes the person does NOT carry,
   so they are listed separately and never become findings. Benign results are ignored, a gene the
   app does not cover is shown with a "ask a counsellor" note, and a line naming two genes is skipped
   as ambiguous. A missed or invented gene would change a couple's risk, which is why rules (testable)
   are used instead of an AI model here.
3. **The person confirms.** They see exactly what was read, can untick a line, must choose their sex
   (it changes what X-linked results mean), and tick "I checked these against my paper report".
   Only then is the report used, exactly like a lab-delivered one.

Limits: text PDFs only (a photo or scanned page has no text to read; that would need OCR), and the
rules are tuned to common report layouts. In production the lab would send a signed FHIR result
instead, which removes both limits. `tools/make_sample_reports.py` writes the fictional sample PDFs.

### Installable app — `web/manifest.json`, `web/sw.js`, `web/icons/`
The app is a **progressive web app (PWA)**: a website a phone can install from the browser, with its
own icon and full screen, without an app store.
- `manifest.json` gives the phone the name, icons and colours. The "maskable" icons are full
  squares with the helix in the central safe zone, because Android crops icons to circles.
- `sw.js`, the **service worker**, is a small script the browser runs in the background. Ours is
  **network first**: it always fetches the newest version and uses the saved copy only offline.
  It **never saves `/api/` answers**, so no result or match is ever written to the phone's cache.
- The match code can be sent by WhatsApp. The link fills in the code on the partner's phone, but
  the partner must still tick consent and press Join: a link can never join a match by itself.

### `web/counsellor.html` — the counsellor console
Registers this browser as a counsellor device (public key to the server, private key kept here),
decrypts each case locally, shows the brief, and sets the status the couple sees.

### `tests/test_core.py` — 155 tests
They focus on what must never break: the 25/50/25 numbers, X-linked and VUS handling, every
template passing the guardrails in both languages, every template covering its own key facts
for every panel gene, a dropped fact or number being caught (the real fava-bean case), unsafe
texts being rejected, the relative chances (50/25/12.5), the invite API never exposing the
sender or storing the relation, the 2048-bit
prime being correct, PSI finding exactly the shared gene, Python and browser agreeing, and a
full API run in which the relay never sees a gene name.

---

## 3b. Version 0.3: what changed after the jury's feedback

The review asked for live AI, a family-tree view, standard lab formats, structured options,
explainable briefs for specialists, strong privacy and a clear referral pathway. Each one:

### Live AI — `app/llm.py`
One door to Gemma 4. With `GEMINI_API_KEY` set (Render's Environment tab), it calls
**Gemma 4 hosted by Google** (`gemma-4-26b-a4b-it`, Gemini API); otherwise it calls a local
Ollama (laptop, Colab, Azure GPU). The key travels in a header, never in a URL. What is sent is
de-identified: gene, condition, risk numbers, quiz answers. Never a name, contact or full result.

### Adaptive teaching — `app/tutor.py`
- **Teach-back:** each idea missed in the quick check (carrier, partner, autonomy) is re-explained
  by Gemma *starting from the reader's own wrong answer*, then checked by the same guardrails.
- **Ask a question:** Gemma answers only from **numbered facts** about the reader's own results
  (F1, F2…) and must cite a fact after every sentence. Missing or invented citations, a number
  not in the facts, or any directive language → the reader gets a safe "ask a counsellor" text.
  The cited facts are shown under the answer, so every answer is explainable.

### Structured options and next steps — `web/options.js`
Six options with the same fields (when, what it involves, what it can tell you, things to
consider, a question for the counsellor). Pick up to three to compare side by side. A next-steps
checklist is built by rules from the result type (shared gene, X-linked, VUS) and the picks.
Never ranked, reviewed text only.

### Family-tree carrier map — `risk_engine.family_map()`, `web/familytree.js`
A pedigree around the person. Each relative shows their chance of carrying the same change.
Mark a relative as tested and the map updates with real genetics: if the mother tested negative,
the change came from the father's side (father ~100%, uncle 50%, cousin 25%; mother's side 0%).
X-linked genes show the son/daughter rule and leave the rest to a counsellor. Relationships only.

### Standard lab results — `web/fhir_parser.js`, `tools/make_sample_fhir.py`
Reads **HL7 FHIR R4 Genomics Reporting** bundles (LOINC 69548-6 variant observations, gene
48018-6, HGVS 48004-6/48005-3, clinical significance 53037-8, Present/Absent). Read on the phone,
never uploaded; the person confirms, exactly like the PDF route.

### Explainable brief, encrypted referral, tracking — `app/brief.py`, `web/seal.js`, `web/brief_view.js`
1. **Brief:** rules build the structured part (reason, risk figures, understanding, options,
   relatives tested, suggested agenda). Gemma writes a 3–4 sentence summary for the specialist,
   with a cited fact per sentence (checked; otherwise a rule-written summary).
2. **Encryption:** each counsellor device has an ECDH P-256 key pair (private key stays in its
   browser). The phone encrypts the brief + contact with AES-256-GCM, and wraps that key for each
   registered device with ECDH + HKDF-SHA-256. **The server stores ciphertext only.**
3. **Referral pathway:** choice of certified service (demo listings), a time-sensitive flag if the
   person is pregnant, and a private token to follow the status (sent → seen → contacting →
   appointment offered), which the counsellor updates from the console.
4. **Educational, not diagnostic:** a banner on every result screen, and on every brief.

---

## 3c. Version 0.3.1: scientific credibility and controls

- **Same gene vs same variant** (`web/match_items.js`): the private match compares genes AND exact
  variants (`HBB` and `HBB|c.20A>T`) in one PSI. The couple learns whether the shared change is
  identical; a different variant is never revealed. The chance is 25% either way for an autosomal
  recessive gene, but with two different variants an affected child is compound heterozygous and
  severity can depend on the combination, so the app says so and refers to a counsellor.
- **Clinical safety rule:** a VUS (or anything benign) is never put into the match, so it can never
  create a couple risk or an alert.
- **Identified vs residual risk:** the couple screen separates the risk from the variants found from
  what screening cannot rule out (genes not on the panel, undetectable or unknown variants).
- **Risk simulator** (`web/simulator.js`): a Punnett square, random pregnancies and a teach-back
  question on independence ("a first affected child does not change the next 25%").
- **Controls:** withdraw a referral (deleted from the server), audit trail of every status change
  with the counsellor device id, device revocation, optional key expiry.
- **Arabic dialects:** a question in Gulf Arabic (or another dialect) is answered in simple Modern
  Standard Arabic.
- **Evidence:** `tools/benchmark.py` → [BENCHMARK.md](BENCHMARK.md); [THREAT_MODEL.md](THREAT_MODEL.md).

---

## 4. Private Set Intersection, explained

**The problem:** Amina and Khalid want to know which genes they *both* carry, without either
seeing the other's full list, and without trusting the server.

**The padlock analogy.** Each has a padlock only they can open. Amina locks each of her gene
names and sends the locked boxes. Khalid adds *his* padlock on top and sends them back, in the
same order. He also sends his own genes, locked with his padlock only. Amina adds her padlock
to those. Now every box carries both padlocks, and the special property of these padlocks is
that the order they were added does not matter. So a doubly-locked "HBB" from Amina looks
*identical* to a doubly-locked "HBB" from Khalid. They compare boxes, never opening any.

**The maths.** A "padlock" is exponentiation in a large prime group:
`lock(x) = H(x)^a mod P`. Locks commute because `(H^a)^b = H^(ab) = (H^b)^a`.
Undoing a lock would require solving the discrete logarithm problem, believed infeasible for a
2048-bit prime. `H()` hashes the gene name into the group; we square the result so it lands in
the subgroup of prime order `Q = (P−1)/2`, where this reasoning holds.

**What each party learns:** the shared genes, and how many genes the other has on their list.
The relay sees only random-looking numbers; it can tell how many matched, but not which.

**Known weaknesses (say these openly to the judges):**
1. *Set inflation.* A dishonest partner could submit all panel genes and learn the other's
   full carrier list. Production fix: the lab digitally signs each person's result, and the
   protocol only accepts signed inputs (authorised PSI).
2. *Semi-honest model.* We assume both run the real app. A modified app could misbehave.
3. *Small domain.* There are only ~570 gene names, so the secret keys are essential: without
   them anyone could hash every gene and compare.

---

## 5. Design principles worth remembering

1. **Facts and language are separate.** The AI never decides a fact or a number. It only
   rephrases facts it is given. This one rule removes most AI risk in health.
2. **Defence in depth.** Template → AI → guardrails → fallback. Each layer assumes the one
   before it can fail.
3. **Data minimisation.** Each component receives the least it needs (table in section 3).
4. **Deterministic core, tested.** Risk rules and cryptography are plain functions with tests.
   Tests are your evidence for the "Responsible AI" judging criterion.
5. **Human in the loop by design.** Shared-carrier and VUS results always route to a counsellor.
6. **Graceful degradation.** No AI, slow AI, or bad AI output: the app still works safely.

---

## 6. Honest limits of v0.1 and what comes next

| Limit now | Next step |
|---|---|
| Coverage check uses keywords: it proves a topic is *mentioned*, not that the sentence around it is right ("fava beans are safe" would pass coverage) | An AI judge or entailment model comparing each rewrite with the template, plus counsellor review of a sample of real outputs |
| Gemma runs on Google's servers (Gemini API) for the online demo; de-identified facts are sent | On-device model in production, or a UAE-hosted Gemma (Azure) |
| Report held in page memory; PDF and FHIR import are not signature-checked | Lab-signed FHIR results, encrypted on-device storage |
| PSI set inflation possible | Lab-signed results |
| Counsellor console uses one shared key; device keys live in the browser's storage | Microsoft Entra ID roles; keys in the OS keystore or a hardware token |
| Family map is a fixed small pedigree; side-of-origin logic for parents and siblings only | Full pedigree editor and Bayesian risk (e.g. with counsellor tools) |
| In-memory server storage | Azure Database for PostgreSQL in a UAE region, audit log |
| Arabic written by us | Native-speaker and counsellor review of every template |
| Family invite: a relative who knows few people were tested may guess the sender | Say so on the sender's screen; let the counsellor send the invite instead |
| Family invite counters live in server memory; the owner token is lost if Amina's page reloads | Store the owner token encrypted on the phone |

---

## 7. Exercises to learn by doing

1. **Add a gene.** Add `HBA1` or `MMUT` to `panel_kb.json` and a persona carrying it. Run the tests.
2. **Break a rule on purpose.** Change "25%" to "30%" in the `ar_both_carriers` template and run
   `python -m pytest -q`. Watch the guardrail test fail, then undo it.
3. **Read the AI raw.** In `explainer.py`, print the text before `guardrails.check()` and try
   the three reading levels in both languages. Note what Gemma changes.
4. **Watch the relay.** During a match, open `http://localhost:8000/api/match/<CODE>` and see what
   the server stores: only long hex numbers.
5. **Make Gemma forget something.** In `explainer.py`, delete the line that adds `must_list`
   to the prompt, then call `explain("xl_carrier_female", "G6PD", "en", "simple", {0, 50, 100})`
   a few times. See how often the coverage check now rejects the rewrite, and which facts go missing.
6. **Follow the maths by hand.** Run `python -c "from app import psi_reference as p; a=p.new_key(); print(p.lock([p.hash_to_group('HBB')], a))"`
   twice and see that the same gene gives different locked values with different keys.
