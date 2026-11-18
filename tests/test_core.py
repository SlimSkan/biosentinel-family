"""Tests for the safety-critical parts: risk numbers, guardrails, private matching.

Run:  python -m pytest -q
"""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import explainer, guardrails, knowledge, psi_reference as psi, risk_engine
from app.main import app

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ risk engine
def test_two_carriers_same_recessive_gene_gives_textbook_numbers():
    [r] = risk_engine.couple_risk(["HBB"])
    assert (r.affected, r.carrier, r.unaffected) == (0.25, 0.50, 0.25)
    assert r.escalation == "required"


def test_no_shared_gene_means_no_couple_risk():
    assert risk_engine.couple_risk([]) == []


def test_x_linked_is_never_a_couple_finding_but_flags_the_woman():
    assert risk_engine.couple_risk(["G6PD"]) == []
    [f] = risk_engine.individual_findings([{"gene": "G6PD", "variant": "", "classification": "Pathogenic"}], "F")
    assert f["xl_son_affected_pct"] == 50 and f["escalation"] == "recommended"
    [m] = risk_engine.individual_findings([{"gene": "G6PD", "variant": "", "classification": "Pathogenic"}], "M")
    assert "xl_son_affected_pct" not in m


def test_vus_always_goes_to_a_counsellor():
    [f] = risk_engine.individual_findings([{"gene": "BTD", "variant": "", "classification": "Uncertain significance"}], "M")
    assert f["escalation"] == "required" and f["reason"] == "vus"


def test_every_persona_gene_is_on_the_panel():
    for p in knowledge.personas().values():
        for v in p["variants"]:
            assert v["gene"] in knowledge.panel()


# ------------------------------------------------------------------ guardrails
@pytest.mark.parametrize("key", list(explainer.TEMPLATES))
@pytest.mark.parametrize("lang", ["en", "ar"])
@pytest.mark.parametrize("level", ["simple", "standard"])
def test_every_reviewed_template_passes_the_guardrails(key, lang, level):
    gene = {"ar_both_carriers": "HBB", "xl_carrier_female": "G6PD", "vus": "BTD", "carrier_self": "CFTR"}.get(key)
    allowed = {"ar_both_carriers": {0, 100, 25, 50}, "xl_carrier_female": {0, 100, 50}}.get(key, {0, 100})
    text = explainer.template_text(key, gene, lang, level)
    assert guardrails.check(text, allowed) == []


@pytest.mark.parametrize("bad", [
    "There is a 30% chance your child is affected.",          # invented number
    "There is a 1 in 3 chance.",                               # invented number, other format
    "You should not marry each other.",                        # directive
    "You are not compatible.",                                 # directive
    "يجب عليكما عدم الزواج.",                                  # directive, Arabic
    "You have sickle cell disease.",                           # diagnosis of a carrier
    "احتمال ٣٠٪ أن يتأثر الطفل.",                              # invented number, Arabic digits
])
def test_guardrails_reject_unsafe_text(bad):
    assert guardrails.check(bad, {0, 25, 50, 100})


def test_explainer_falls_back_to_template_when_ai_is_down(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError
    monkeypatch.setattr(explainer, "_ask_gemma", boom)
    out = explainer.explain("ar_both_carriers", "HBB", "en", "standard", {0, 25, 50, 100}, use_ai=True)
    assert out["source"] == "template"


def test_explainer_rejects_unsafe_ai_text(monkeypatch):
    monkeypatch.setattr(explainer, "_ask_gemma", lambda *a: "You should not marry. The risk is 40%.")
    out = explainer.explain("ar_both_carriers", "HBB", "en", "standard", {0, 25, 50, 100}, use_ai=True)
    assert out["source"] == "template" and out["problems"]


# ------------------------------------------------------------------ fact coverage
@pytest.mark.parametrize("gene", list(knowledge.panel()))
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_every_template_covers_its_own_key_facts(gene, lang):
    """The reviewed texts must pass the coverage check, for every gene on the panel."""
    inh = knowledge.gene(gene)["inheritance"]
    keys = ["carrier_self", "ar_both_carriers", "vus"] if inh == "AR" else ["xl_carrier_female", "vus"]
    for key in keys:
        for level in ("simple", "standard"):
            facts = explainer.required_facts(key, gene, lang, level)
            text = explainer.template_text(key, gene, lang, level)
            assert guardrails.missing_facts(text, facts, lang) == [], (key, level)


def test_every_panel_gene_has_key_facts_in_both_languages():
    for sym in knowledge.panel():
        facts = knowledge.gene(sym)["key_facts"]
        assert facts and all(f["en"] and f["ar"] and f["say"] for f in facts), sym


def test_dropping_the_fava_bean_trigger_is_caught(monkeypatch):
    """The real failure seen with Gemma: a short rewrite that forgot the trigger."""
    short = ("You carry a change in the G6PD gene, on the X chromosome. You are usually healthy. "
             "Each son has a 50% chance of being affected and each daughter a 50% chance of being a carrier, "
             "whatever your partner's result. Some medicines can be a trigger. A genetic counsellor can help.")
    monkeypatch.setattr(explainer, "_ask_gemma", lambda *a: short)
    out = explainer.explain("xl_carrier_female", "G6PD", "en", "simple", {0, 50, 100}, use_ai=True)
    assert out["source"] == "template"
    assert "fava" in out["problems"][0] and "fava" in out["text"]


def test_dropping_a_number_is_caught(monkeypatch):
    text = ("You are both healthy carriers of a change in HBB. In each pregnancy there is a 25% chance the child "
            "is affected. The choice is yours, and a genetic counsellor can help.")  # 50% carrier chance dropped
    monkeypatch.setattr(explainer, "_ask_gemma", lambda *a: text)
    out = explainer.explain("ar_both_carriers", "HBB", "en", "standard", {0, 25, 50, 100}, use_ai=True)
    assert out["source"] == "template" and any("missing numbers: [50]" in p for p in out["problems"])


def test_a_complete_rewrite_is_accepted(monkeypatch):
    text = ("You both carry a change in HBB, which affects haemoglobin in red blood cells. You are both healthy "
            "carriers. In each pregnancy, the chance is 25% that the child is affected, 50% that the child is a "
            "healthy carrier, and 25% that the child does not carry it. The choice is yours. "
            "A genetic counsellor can help you.")
    monkeypatch.setattr(explainer, "_ask_gemma", lambda *a: text)
    out = explainer.explain("ar_both_carriers", "HBB", "en", "standard", {0, 25, 50, 100}, use_ai=True)
    assert out == {"text": text, "source": "ai", "problems": []}


def test_feminine_arabic_form_is_not_a_false_alarm():
    """Seen with Gemma: 'ليست تشخيصاً' (feminine) was first rejected."""
    [nd] = [f for f in explainer.TEMPLATE_FACTS["vus"] if f["id"] == "not_diagnosis"]
    assert guardrails.missing_facts("هذه النتيجة ليست تشخيصاً.", [nd], "ar") == []


def test_arabic_spelling_variants_still_match():
    fava = knowledge.gene("G6PD")["key_facts"][1]   # medicines
    assert guardrails.missing_facts("تجنّبي بعض الأدوية", [fava], "ar") == []
    assert guardrails.missing_facts("تجنبي بعض الادوية", [fava], "ar") == []


# ------------------------------------------------------------------ PSI maths
def _is_probable_prime(n, rounds=20):
    if n % 2 == 0:
        return False
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for _ in range(rounds):
        x = pow(random.randrange(2, n - 2), d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def test_group_is_a_safe_prime():
    # catches any typo in the 2048-bit constant
    assert psi.P.bit_length() == 2048
    assert _is_probable_prime(psi.P) and _is_probable_prime(psi.Q)


def test_psi_finds_exactly_the_shared_genes():
    amina, khalid = ["HBB", "G6PD", "GJB2"], ["CFTR", "HBB"]
    a, b = psi.new_key(), psi.new_key()
    a_locked = psi.lock([psi.hash_to_group(x) for x in amina], a)
    b_locked = psi.lock([psi.hash_to_group(y) for y in khalid], b)
    a_double, b_double = psi.lock(a_locked, b), psi.lock(b_locked, a)
    assert psi.shared_items(amina, a_double, b_double) == ["HBB"]
    assert psi.shared_items(khalid, b_double, a_double) == ["HBB"]
    # a locked value reveals nothing obvious: it is not the plain hash
    assert a_locked[0] != psi.hash_to_group("HBB")


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_browser_and_python_implementations_agree():
    script = (f"import {{PSI}} from '{(ROOT / 'web' / 'psi.js').as_uri()}';"
              "const v = await PSI.lockItems(['HBB','CFTR'], 123456789n); console.log(JSON.stringify(v));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    py = [format(v, "x") for v in psi.lock([psi.hash_to_group("HBB"), psi.hash_to_group("CFTR")], 123456789)]
    assert js == py


# ------------------------------------------------------------------ the API, end to end
def test_full_flow_through_the_api():
    c = TestClient(app)
    amina, khalid = c.get("/api/personas/amina").json(), c.get("/api/personas/khalid").json()
    genes = lambda p: [v["gene"] for v in p["variants"] if v["classification"] != "Uncertain significance"]

    # Amina starts a match; the relay only ever receives hex strings of locked numbers
    code = c.post("/api/match").json()["code"]
    a = psi.new_key()
    a_items = genes(amina)
    c.post(f"/api/match/{code}/a1", json={"values": [format(v, "x") for v in psi.lock([psi.hash_to_group(x) for x in a_items], a)]})

    # Khalid joins
    b = psi.new_key()
    b_items = genes(khalid)
    st = c.get(f"/api/match/{code}").json()
    a_double = [format(pow(int(h, 16), b, psi.P), "x") for h in st["a_locked"]]
    b_locked = [format(v, "x") for v in psi.lock([psi.hash_to_group(y) for y in b_items], b)]
    c.post(f"/api/match/{code}/b1", json={"a_double": a_double, "b_locked": b_locked})

    # Amina finishes
    st = c.get(f"/api/match/{code}").json()
    b_double = [format(pow(int(h, 16), a, psi.P), "x") for h in st["b_locked"]]
    c.post(f"/api/match/{code}/a2", json={"values": b_double})
    assert psi.shared_items(a_items, [int(x, 16) for x in st["a_double"]], [int(x, 16) for x in b_double]) == ["HBB"]

    # The relay never saw a gene name
    assert "HBB" not in json.dumps(c.get(f"/api/match/{code}").json())

    # Couple explanation
    res = c.post("/api/explain/couple", json={"shared_genes": ["HBB"], "lang": "ar"}).json()
    assert res["risks"][0]["affected_pct"] == 25
    assert res["explanations"][0]["source"] == "template"

    # Hand-off: the counsellor sees only what was sent
    c.post("/api/cases", json={"shared_genes": ["HBB"], "contact": "by phone"})
    assert c.get("/api/cases").json()[0]["shared_genes"] == ["HBB"]


# ------------------------------------------------------------------ family invites
@pytest.mark.parametrize("relation,pct", [("sibling", 50), ("parent", 50), ("child", 50), ("aunt_uncle", 25),
                                          ("half_sibling", 25), ("niece_nephew", 25), ("first_cousin", 12.5)])
def test_relative_chance_halves_with_each_step_of_relationship(relation, pct):
    assert risk_engine.relative_chance("HBB", relation) == {"key": "relative_ar", "chance_pct": pct}


def test_x_linked_or_unknown_relation_gets_no_number():
    assert risk_engine.relative_chance("G6PD", "sibling")["chance_pct"] is None
    assert risk_engine.relative_chance("HBB", "unsure") == {"key": "relative_general", "chance_pct": None}


def test_uncertain_results_are_never_shared_with_family():
    assert not risk_engine.can_invite("Uncertain significance")
    assert risk_engine.can_invite("Pathogenic")


def test_decimal_percentages_are_read_correctly():
    assert guardrails._percentages("about a 12.5% chance") == {12.5}
    assert guardrails._percentages("١٢٫٥٪") == {12.5}
    assert guardrails._percentages("1 in 8") == {12.5}
    assert guardrails.check("about a 12.5% chance", {0, 100, 50})          # not allowed here -> problem
    assert guardrails._percentages("a 15% chance") == {15}                 # not mistaken for 12.5


@pytest.mark.parametrize("gene,relation", [("HBB", "sibling"), ("HBB", "first_cousin"), ("CFTR", "unsure"),
                                           ("G6PD", "parent"), ("DMD", "unsure")])
@pytest.mark.parametrize("lang", ["en", "ar"])
@pytest.mark.parametrize("level", ["simple", "standard"])
def test_relative_templates_pass_every_check(gene, relation, lang, level):
    rc = risk_engine.relative_chance(gene, relation)
    allowed = {0, 100} | ({rc["chance_pct"]} if rc["chance_pct"] is not None else set())
    text = explainer.template_text(rc["key"], gene, lang, level, rc["chance_pct"])
    facts = explainer.required_facts(rc["key"], gene, lang, level)
    assert "{" not in text
    assert guardrails.check(text, allowed, facts=facts, lang=lang) == []
    if rc["chance_pct"] is not None:
        assert guardrails._percentages(text) == {rc["chance_pct"]}


def test_invite_flow_keeps_the_sender_anonymous():
    c = TestClient(app)
    assert c.post("/api/invites", json={"gene": "BTD", "classification": "Uncertain significance"}).status_code == 400
    inv = c.post("/api/invites", json={"gene": "HBB", "classification": "Pathogenic"}).json()
    iid, owner = inv["id"], inv["owner"]
    assert len(iid) >= 12 and "HBB" not in iid

    # What the relative's page receives: the gene, nothing about the sender.
    seen = c.get(f"/api/invites/{iid}").json()
    assert seen["gene"] == "HBB" and set(seen) == {"gene", "inheritance", "condition", "relations"}
    assert "owner" not in json.dumps(seen)

    c.post(f"/api/invites/{iid}/event", json={"event": "opened"})
    out = c.post(f"/api/invites/{iid}/explain", json={"relation": "first_cousin", "lang": "en"}).json()
    assert out["chance_pct"] == 12.5 and "12.5%" in out["text"] and out["source"] == "template"
    c.post(f"/api/invites/{iid}/event", json={"event": "next_step"})

    # The sender sees counters only, and only with the owner secret.
    assert c.get(f"/api/invites/{iid}/status").status_code == 403
    assert c.get(f"/api/invites/{iid}/status", headers={"X-Invite-Owner": "guess"}).status_code == 403
    assert c.get(f"/api/invites/{iid}/status", headers={"X-Invite-Owner": owner}).json() == {"opened": 1, "next_step": 1}
    # The relation the relative chose is not stored anywhere.
    from app import main
    assert "first_cousin" not in json.dumps(main.INVITES[iid])
    assert c.post(f"/api/invites/{iid}/explain", json={"relation": "boss", "lang": "en"}).status_code == 400
    assert c.get("/api/invites/doesnotexist").status_code == 404


def test_arabic_choice_with_a_suffix_is_not_a_false_alarm():
    """Seen with Gemma: 'قرار إجراء الفحص هو اختيارك' was first rejected."""
    [choice] = [f for f in explainer.TEMPLATE_FACTS["relative_general"] if f["id"] == "choice"]
    assert guardrails.missing_facts("قرار إجراء الفحص هو اختيارك.", [choice], "ar") == []


def test_rewrite_must_not_assume_the_reader_is_a_woman(monkeypatch):
    """Seen with Gemma: 'قد تحملين أنتِ أيضاً' on a page for a relative of unknown sex."""
    base = explainer.template_text("relative_ar", "HBB", "ar", "simple", 50)
    fem = base.replace("قد تحمله أنت أيضاً", "قد تحملينه أنتِ أيضاً")
    assert fem != base
    monkeypatch.setattr(explainer, "_ask_gemma", lambda *a: fem)
    out = explainer.explain("relative_ar", "HBB", "ar", "simple", {0, 50, 100}, True, pct=50)
    assert out["source"] == "template" and "assumed the reader is a woman" in out["problems"]


def test_feminine_forms_are_fine_when_the_reviewed_text_uses_them():
    base = explainer.template_text("xl_carrier_female", "G6PD", "ar", "standard")
    assert "أنتِ" in base and not guardrails.changes_gender(base, base)


def test_a_sentence_repeated_word_for_word_is_dropped():
    """Seen with Gemma: the closing counsellor sentence appeared twice."""
    assert explainer._clean("A test can tell you. A counsellor can help. A counsellor can help.") == \
        "A test can tell you. A counsellor can help."


# ------------------------------------------------------------------ deployment
def test_counsellor_inbox_needs_the_key_when_one_is_set(monkeypatch):
    from app import main
    c = TestClient(app)
    monkeypatch.setattr(main, "COUNSELLOR_KEY", "s3cret")
    assert c.get("/api/cases").status_code == 401
    assert c.get("/api/cases", headers={"X-Counsellor-Key": "wrong"}).status_code == 401
    assert c.get("/api/cases", headers={"X-Counsellor-Key": "s3cret"}).status_code == 200
    assert c.post("/api/cases", json={"contact": "x"}).status_code == 200      # couples can still send


def test_health_reports_when_the_ai_is_unreachable(monkeypatch):
    from app import llm
    monkeypatch.setattr(llm, "GEMINI_KEY", "")
    monkeypatch.setattr(llm, "OLLAMA_URL", "http://127.0.0.1:9")          # nothing listens here
    h = TestClient(app).get("/api/health").json()
    assert h["ok"] is True and h["ai"]["reachable"] is False


# ------------------------------------------------------------------ installable app (PWA)
def _png_size(data: bytes) -> tuple[int, int]:
    """Width and height from a PNG header (bytes 16-24), without an image library."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def test_manifest_makes_the_app_installable():
    c = TestClient(app)
    m = c.get("/manifest.json").json()
    assert m["name"] and m["start_url"] == "/" and m["display"] == "standalone"
    sizes = {(i["sizes"], i["purpose"]) for i in m["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("192x192", "maskable"), ("512x512", "maskable")} <= sizes
    for icon in m["icons"]:
        r = c.get(icon["src"])
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        w, h = _png_size(r.content)
        assert f"{w}x{h}" == icon["sizes"], icon["src"]


def test_service_worker_is_served_and_never_caches_the_api():
    r = TestClient(app).get("/sw.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert 'startsWith("/api/")' in r.text          # API answers are never stored on the phone


@pytest.mark.parametrize("page", ["index.html", "partner.html", "invite.html", "counsellor.html"])
def test_every_page_links_the_manifest_and_registers_the_service_worker(page):
    html = (ROOT / "web" / page).read_text(encoding="utf-8")
    assert 'rel="manifest"' in html and 'register("/sw.js")' in html and "apple-touch-icon" in html


# ------------------------------------------------------------------ import a lab report (PDF)
def _parse_reports(texts: list[str]) -> list[dict]:
    """Run the browser's report parser (web/report_parser.js) in Node on several texts."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    url = (ROOT / "web" / "report_parser.js").as_uri()
    script = ("import { parseReportText } from '%s';"
              "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{"
              "const {texts,panel}=JSON.parse(d);"
              "console.log(JSON.stringify(texts.map(t=>parseReportText(t,panel))));});" % url)
    panel = list(knowledge.kb()["genes"])
    r = subprocess.run([node, "--input-type=module", "-e", script], input=json.dumps({"texts": texts, "panel": panel}),
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def _report_text(pid: str) -> str:
    """The text pdf.js gives for a sample report: one line per row, cells joined by two spaces."""
    p = knowledge.personas()[pid]
    sex = "Female" if p["sex"] == "F" else "Male"
    rows = [f"{v['gene']}  {v['variant']}  {v['classification']}  Carrier" for v in p["variants"]]
    negatives = [g for g in knowledge.kb()["genes"] if g not in {v["gene"] for v in p["variants"]}]
    return "\n".join(["DEMO PREMARITAL SCREENING LAB",
                      "Expanded carrier screening report - FICTIONAL DEMO, NOT A REAL PERSON",
                      f"Name: {p['name']} (demo)  Sex: {sex}  Date of birth: 01/01/1997",
                      "RESULTS", "Gene  Variant  Classification  Status", *rows,
                      "No pathogenic variants detected in: " + ", ".join(negatives) + ".",
                      "A child can be affected only if both parents carry a change in the same gene."])


def test_report_parser_reads_every_sample_report_exactly():
    pids = list(knowledge.personas())
    for pid, got in zip(pids, _parse_reports([_report_text(p) for p in pids])):
        want = knowledge.personas()[pid]
        assert got["sex"] == want["sex"] and got["name"] == want["name"], pid
        assert [(f["gene"], f["classification"]) for f in got["findings"]] == \
               [(v["gene"], v["classification"]) for v in want["variants"]], pid
        # genes listed as "not detected" must never become findings
        assert not set(got["negative"]) & {f["gene"] for f in got["findings"]}, pid


def test_report_parser_handles_tricky_lines():
    texts = [
        "LAB\nsex: m\nCFTR  c.1521_1523del (p.Phe508del)  Likely pathogenic  Carrier",   # likely pathogenic, lower case
        "LAB\nHBB  c.9C>T  Benign\nGJB2  c.101T>C  VUS",                                 # benign ignored, VUS kept
        "LAB\nMEFV  c.2080A>G (p.Met694Val)  Pathogenic  Carrier",                       # gene not covered by the app
        "LAB\nHBB and CFTR  Pathogenic",                                                 # ambiguous: two genes on one line
        "Holiday photo, no lab results here",                                            # not a report
    ]
    likely, vus, uncovered, ambiguous, nothing = _parse_reports(texts)
    assert likely["sex"] == "M" and likely["findings"] == [
        {"gene": "CFTR", "variant": "c.1521_1523del (p.Phe508del)", "classification": "Likely pathogenic"}]
    assert [f["gene"] for f in vus["findings"]] == ["GJB2"] and vus["findings"][0]["classification"] == "Uncertain significance"
    assert uncovered["findings"] == [] and uncovered["notCovered"] == ["MEFV"]
    assert ambiguous["findings"] == []
    assert nothing["findings"] == [] and nothing["negative"] == [] and nothing["notCovered"] == []


def test_sample_reports_exist_and_panel_endpoint_lists_the_genes():
    c = TestClient(app)
    panel = c.get("/api/panel").json()
    assert panel["genes"] == list(knowledge.kb()["genes"]) and panel["inheritance"]["G6PD"] == "XL"
    for pid in knowledge.personas():
        r = c.get(f"/samples/{pid}_report.pdf")
        assert r.status_code == 200 and r.content.startswith(b"%PDF-") and b"FICTIONAL DEMO" in r.content


# ------------------------------------------------------------------ Colab notebook for the jury
def test_colab_notebook_is_valid_and_its_python_compiles():
    nb = json.loads((ROOT / "notebooks" / "gemma_live.ipynb").read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4 and nb["metadata"]["accelerator"] == "GPU"
    text = json.dumps(nb)
    assert "github.com/SlimSkan/biosentinel-family" in text and "gemma4:e4b" in text
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        # Lines starting with ! or % are Colab shell/magic commands, not Python.
        python = "\n".join("" if line.lstrip().startswith(("!", "%")) else line for line in src.splitlines())
        compile(python, "notebook cell", "exec")


def test_browsers_always_check_for_a_new_version():
    """A redeploy must reach phones at once: no file may be reused without asking the server."""
    c = TestClient(app)
    for path in ["/", "/partner.html", "/app.js", "/sw.js", "/api/health"]:
        assert c.get(path).headers.get("cache-control") == "no-cache", path


# ------------------------------------------------------------------ Gemma 4 through the Gemini API
class _FakeResponse:
    def __init__(self, data, code=200):
        self._data, self.status_code = data, code
    def json(self):
        return self._data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_gemini_provider_sends_the_key_in_a_header_and_skips_thought_parts(monkeypatch):
    from app import llm
    monkeypatch.setattr(llm, "GEMINI_KEY", "test-key")
    monkeypatch.delenv("BSF_LLM", raising=False)
    seen = {}
    def fake_post(url, **kw):
        seen.update(url=url, **kw)
        return _FakeResponse({"candidates": [{"content": {"parts": [
            {"text": "thinking...", "thought": True}, {"text": "Hello "}, {"text": "reader."}]}}]})
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.provider() == "gemini"
    assert llm.ask("SYSTEM", "USER") == "Hello reader."
    assert "gemma-4" in seen["url"] and "key=" not in seen["url"]          # key never in the URL
    assert seen["headers"]["x-goog-api-key"] == "test-key"
    assert "SYSTEM" in seen["json"]["contents"][0]["parts"][0]["text"]


def test_without_a_key_the_app_uses_local_ollama(monkeypatch):
    from app import llm
    monkeypatch.setattr(llm, "GEMINI_KEY", "")
    monkeypatch.delenv("BSF_LLM", raising=False)
    assert llm.provider() == "ollama"


# ------------------------------------------------------------------ helpers for the new features
def _node(script: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    return subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True,
                          check=True).stdout


def _fake_llm(monkeypatch, text):
    from app import llm
    monkeypatch.setattr(llm, "ask", lambda *a, **k: text)


# ------------------------------------------------------------------ family-tree carrier map
def test_family_map_halves_with_each_step_of_relationship():
    m = {n["id"]: n["pct"] for n in risk_engine.family_map("HBB")["nodes"]}
    assert m["me"] == 100 and m["mother"] == m["father"] == m["brother"] == m["son"] == 50
    assert m["pgm"] == m["m_aunt"] == m["nephew"] == 25
    assert m["p_cousin"] == m["m_cousin"] == 12.5


def test_family_map_side_of_origin_when_a_parent_is_tested():
    m = {n["id"]: n["pct"] for n in risk_engine.family_map("HBB", {"mother": "not_carrier"})["nodes"]}
    assert m["father"] == 100 and m["p_uncle"] == 50 and m["p_cousin"] == 25      # father's side doubles
    assert m["mother"] == m["mgm"] == m["m_aunt"] == m["m_cousin"] == 0           # not from the mother's side
    m = {n["id"]: n["pct"] for n in risk_engine.family_map("HBB", {"brother": "carrier"})["nodes"]}
    assert m["brother"] == 100 and m["nephew"] == 50 and m["niece"] == 25


def test_family_map_x_linked_gives_children_only_and_ignores_unknown_ids():
    nodes = risk_engine.family_map("G6PD", {"hacker": "carrier", "me": "not_carrier"})["nodes"]
    m = {n["id"]: n["pct"] for n in nodes}
    assert m["son"] == m["daughter"] == 50 and m["me"] == 100 and m["m_aunt"] is None
    assert TestClient(app).post("/api/family-map", json={"gene": "NOPE"}).status_code == 400


# ------------------------------------------------------------------ adaptive teaching and questions
def test_teachback_without_ai_returns_the_reviewed_text():
    r = TestClient(app).post("/api/teachback", json={"concept": "carrier", "lang": "ar", "ai": False}).json()
    assert r["source"] == "template" and "بصحة" in r["text"]


def test_teachback_rejects_an_unsafe_rewrite(monkeypatch):
    from app import tutor
    _fake_llm(monkeypatch, "You have the disease, so you should not marry.")
    r = tutor.reexplain("carrier", "I have the disease", "Being a carrier means...")
    assert r["source"] == "template" and r["problems"]


def test_answer_keeps_cited_sentences_and_lists_the_sources(monkeypatch):
    from app import tutor
    _fake_llm(monkeypatch, "A carrier is healthy and has one changed copy of a gene. [F3] "
                           "This app gives educational information. [F8]")
    r = tutor.answer("Am I ill?", [{"gene": "HBB", "classification": "Pathogenic"}], [])
    assert r["source"] == "ai" and "[F" not in r["text"]
    assert [s["id"] for s in r["sources"]] == ["F3", "F8"]


@pytest.mark.parametrize("reply", [
    "A carrier is healthy and has one changed copy of a gene.",                 # no citation
    "A carrier is healthy. [F99]",                                              # cites a fact that does not exist
    "There is a 30% chance your child is affected. [F3]",                       # number not in the facts
    "You should not marry each other. [F3]",                                    # directive
    "NO_ANSWER",                                                                # model declined
])
def test_answer_falls_back_to_the_referral_text(monkeypatch, reply):
    from app import tutor
    _fake_llm(monkeypatch, reply)
    r = tutor.answer("Should we marry?", [{"gene": "HBB", "classification": "Pathogenic"}], [])
    assert r["source"] == "template" and "counsellor" in r["text"] and r["sources"] == []


def test_ask_endpoint_limits_the_question_and_ignores_unknown_genes(monkeypatch):
    c = TestClient(app)
    assert c.post("/api/ask", json={"question": "x" * 301}).status_code == 422
    _fake_llm(monkeypatch, "NO_ANSWER")
    assert c.post("/api/ask", json={"question": "What is this?", "shared": ["EVIL"]}).json()["source"] == "template"


# ------------------------------------------------------------------ pre-consultation brief
def test_brief_is_built_from_rules_and_the_summary_cites_facts(monkeypatch):
    from app import brief
    _fake_llm(monkeypatch, "Both partners carry a pathogenic change in HBB. [F1] They want to discuss PGT-M. [F3]")
    b = brief.build({"shared_genes": ["HBB"], "findings": [], "quiz_score": 2, "missed": ["carrier"],
                     "picks": ["pgt"], "pregnant": "yes"})
    assert b["priority"] == "urgent" and b["agenda"][0].startswith("Current pregnancy")
    assert "25% affected" in b["risks"][0] and "what being a carrier means" in b["understanding"]
    assert b["summary_source"] == "ai" and b["summary_sources"] == ["F1", "F3"]


def test_brief_falls_back_to_rules_when_the_summary_is_not_cited(monkeypatch):
    from app import brief
    _fake_llm(monkeypatch, "They are fine and should go ahead.")
    b = brief.build({"shared_genes": ["HBB"]})
    assert b["summary_source"] == "rules" and b["summary"].startswith("Referral for")


# ------------------------------------------------------------------ encrypted referral and tracking
def test_sealed_cases_store_no_plaintext_and_need_the_token_to_follow():
    from app import main
    c = TestClient(app)
    sealed = {"v": 1, "alg": "ECDH-P256+HKDF-SHA256+A256GCM", "epk": {"kty": "EC"}, "iv": "aa", "ct": "bb",
              "keys": [{"kid": "0123456789abcdef", "iv": "cc", "wk": "dd"}]}
    r = c.post("/api/cases", json={"service": "tele", "priority": "urgent", "sealed": sealed,
                                   "contact": "should be dropped"}).json()
    stored = next(x for x in main.CASES if x["id"] == r["id"])
    assert "contact" not in stored and stored["sealed"]["ct"] == "bb"
    assert c.get(f"/api/cases/{r['id']}/status", headers={"X-Case-Token": "wrong"}).status_code == 403
    s = c.get(f"/api/cases/{r['id']}/status", headers={"X-Case-Token": r["token"]}).json()
    assert s["status"] == "new" and s["priority"] == "urgent" and "Tele" in s["service"]
    assert all("_token" not in x for x in c.get("/api/cases").json())          # never in the counsellor list


def test_counsellor_devices_and_status_need_the_key(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "COUNSELLOR_KEY", "k3y")
    c = TestClient(app)
    dev = {"kid": "00112233aabbccdd", "jwk": {"kty": "EC", "crv": "P-256", "x": "AAA", "y": "BBB", "d": "SECRET"}}
    assert c.post("/api/counsellor/devices", json=dev).status_code == 401
    assert c.post("/api/counsellor/devices", json=dev, headers={"X-Counsellor-Key": "k3y"}).status_code == 200
    listed = c.get("/api/counsellor/devices").json()
    mine = next(d for d in listed if d["kid"] == "00112233aabbccdd")
    assert mine["jwk"] == {"kty": "EC", "crv": "P-256", "x": "AAA", "y": "BBB"}
    assert "SECRET" not in json.dumps(listed)                                     # a private part is never kept
    cid = c.post("/api/cases", json={"note": "x"}).json()["id"]
    assert c.post(f"/api/cases/{cid}/status", json={"status": "seen"}).status_code == 401
    assert c.post(f"/api/cases/{cid}/status", json={"status": "bogus"}, headers={"X-Counsellor-Key": "k3y"}).status_code == 400
    assert c.post(f"/api/cases/{cid}/status", json={"status": "seen"}, headers={"X-Counsellor-Key": "k3y"}).status_code == 200


def test_browser_encryption_round_trip_wrong_device_and_tampering():
    seal = (ROOT / "web" / "seal.js").as_uri()
    script = (
        f"import {{newDevice, seal, open}} from '{seal}';"
        "const a = await newDevice(), b = await newDevice();"
        "const env = await seal({brief: 'HBB secret'}, [{kid: a.kid, jwk: a.publicJwk}]);"
        "let wrong = 'opened'; try { await open(env, b); } catch (e) { wrong = 'refused'; }"
        "const ok = (await open(env, a)).brief;"
        "const leak = JSON.stringify(env).includes('HBB');"
        "env.ct = env.ct.slice(0, -4) + 'AAAA';"
        "let tampered = 'opened'; try { await open(env, a); } catch (e) { tampered = 'refused'; }"
        "console.log(JSON.stringify({ok, wrong, tampered, leak}));"
    )
    assert json.loads(_node(script)) == {"ok": "HBB secret", "wrong": "refused", "tampered": "refused", "leak": False}


# ------------------------------------------------------------------ standard lab results (HL7 FHIR)
def test_fhir_samples_are_read_like_the_lab_reports():
    parser = (ROOT / "web" / "fhir_parser.js").as_uri()
    panel = list(knowledge.kb()["genes"])
    samples = (ROOT / "web" / "samples").as_posix()
    script = (
        f"import {{parseFhir}} from '{parser}'; import fs from 'fs';"
        "const r = {};"
        "for (const p of ['amina', 'khalid', 'sara', 'omar'])"
        f"  r[p] = parseFhir(JSON.parse(fs.readFileSync('{samples}/' + p + '_report.fhir.json', 'utf8')), {json.dumps(panel)});"
        "console.log(JSON.stringify(r));"
    )
    r = json.loads(_node(script))
    personas = json.loads((ROOT / "data" / "personas.json").read_text(encoding="utf-8"))["personas"]
    for pid, person in personas.items():
        assert [(f["gene"], f["classification"]) for f in r[pid]["findings"]] == \
               [(v["gene"], v["classification"]) for v in person["variants"]]
        assert r[pid]["sex"] == person["sex"] and r[pid]["format"].startswith("HL7 FHIR")
        assert set(r[pid]["negative"]) == set(panel) - {v["gene"] for v in person["variants"]}


def test_fhir_parser_skips_benign_and_flags_genes_outside_the_panel():
    parser = (ROOT / "web" / "fhir_parser.js").as_uri()

    def obs(gene, sig):
        return {"resourceType": "Observation", "code": {"coding": [{"code": "69548-6"}]},
                "valueCodeableConcept": {"coding": [{"code": "LA9633-4"}]},
                "component": [{"code": {"coding": [{"code": "48018-6"}]}, "valueCodeableConcept": {"coding": [{"display": gene}]}},
                              {"code": {"coding": [{"code": "53037-8"}]}, "valueCodeableConcept": {"coding": [{"code": sig}]}}]}
    bundle = {"resourceType": "Bundle", "entry": [{"resource": obs("HBB", "LA6675-8")}, {"resource": obs("BRCA1", "LA6668-3")},
                                                 {"resource": obs("CFTR", "LA26332-9")}]}
    r = json.loads(_node(f"import {{parseFhir}} from '{parser}'; "
                         f"console.log(JSON.stringify(parseFhir({json.dumps(bundle)}, ['HBB','CFTR'])));"))
    assert r["findings"] == [{"gene": "CFTR", "variant": "", "classification": "Likely pathogenic"}]
    assert r["notCovered"] == ["BRCA1"]


def test_gemini_retries_when_busy_then_tries_the_other_gemma_model(monkeypatch):
    from app import llm
    monkeypatch.setattr(llm, "GEMINI_KEY", "k")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.delenv("BSF_LLM", raising=False)
    calls = []
    class R:
        def __init__(self, code, data):
            self.status_code, self._d, self.headers = code, data, {"content-type": "application/json"}
        def json(self):
            return self._d
    def fake_post(url, **kw):
        calls.append(url.split("/models/")[1].split(":")[0])
        if len(calls) < 3:
            return R(503, {"error": {"message": "high demand"}})
        return R(200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.ask("s", "u") == "ok"
    assert calls == ["gemma-4-26b-a4b-it", "gemma-4-26b-a4b-it", "gemma-4-31b-it"]



# ------------------------------------------------------------------ v0.3.1: variant-level match, residual risk, controls
def test_psi_items_include_exact_variants_and_never_a_vus():
    mod = (ROOT / "web" / "match_items.js").as_uri()
    script = (f"import {{psiItems, readMatch, variantKey}} from '{mod}';"
              "const amina = psiItems([{gene:'HBB', variant:'c.20A>T (p.Glu7Val, HbS)', classification:'Pathogenic'},"
              "  {gene:'BTD', variant:'c.1A>G', classification:'Uncertain significance'},"
              "  {gene:'CFTR', variant:'c.1521_1523del', classification:'Likely benign'}]);"
              "const same = readMatch(['HBB', 'HBB|c.20A>T']);"
              "const diff = readMatch(['HBB']);"
              "console.log(JSON.stringify({amina, same, diff, k: variantKey('c.20A>T (p.Glu7Val)'), ex: variantKey('Exon 7 deletion (1 copy)')}));")
    r = json.loads(_node(script))
    assert sorted(r["amina"]) == ["HBB", "HBB|c.20A>T"]                         # no VUS, no benign
    assert r["same"] == {"shared": ["HBB"], "sameVariant": ["HBB"]}
    assert r["diff"] == {"shared": ["HBB"], "sameVariant": []}
    assert r["k"] == "c.20A>T" and r["ex"] == "exon 7 deletion (1 copy)"


def test_couple_risk_records_same_or_different_variant_and_keeps_25_percent():
    same = risk_engine.couple_risk(["HBB"], ["HBB"])[0].to_dict()
    diff = risk_engine.couple_risk(["HBB"], [])[0].to_dict()
    old = risk_engine.couple_risk(["HBB"])[0].to_dict()
    assert (same["variant_match"], diff["variant_match"], old["variant_match"]) == ("same", "different", "unknown")
    assert same["affected_pct"] == diff["affected_pct"] == 25


def test_brief_states_variant_match_residual_risk_and_simulator_check(monkeypatch):
    from app import brief
    _fake_llm(monkeypatch, "no citations")
    b = brief.build({"shared_genes": ["HBB"], "same_variant": [], "quiz_score": 3, "sim_check": "wrong"})
    assert "compound heterozygous" in b["risks"][0]
    assert b["residual"].startswith("Residual risk remains") and "does not remove risk" in b["residual"]
    assert "Simulator check" in b["understanding"] and any("independent" in a for a in b["agenda"])


def test_person_can_withdraw_and_the_case_is_deleted():
    c = TestClient(app)
    r = c.post("/api/cases", json={"note": "x"}).json()
    hdr = {"X-Case-Token": r["token"]}
    assert c.get(f"/api/cases/{r['id']}/status", headers=hdr).json()["events"][0]["what"].startswith("sent")
    assert c.delete(f"/api/cases/{r['id']}", headers={"X-Case-Token": "nope"}).status_code == 403
    assert c.delete(f"/api/cases/{r['id']}", headers=hdr).status_code == 200
    assert c.get(f"/api/cases/{r['id']}/status", headers=hdr).status_code == 404


def test_audit_trail_records_the_counsellor_device(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "COUNSELLOR_KEY", "")
    c = TestClient(app)
    r = c.post("/api/cases", json={"note": "x"}).json()
    c.post(f"/api/cases/{r['id']}/status", json={"status": "seen"}, headers={"X-Device-Kid": "abcdef0123456789"})
    case = next(x for x in main.CASES if x["id"] == r["id"])
    assert case["events"][-1]["what"] == "seen" and "abcdef0123456789" in case["events"][-1]["by"]


def test_devices_can_be_revoked_and_keys_can_expire(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "COUNSELLOR_KEY", "k")
    c = TestClient(app)
    h = {"X-Counsellor-Key": "k"}
    c.post("/api/counsellor/devices", json={"kid": "ffffeeeeddddcccc", "jwk": {"kty": "EC", "crv": "P-256", "x": "1", "y": "2"}}, headers=h)
    assert c.delete("/api/counsellor/devices/ffffeeeeddddcccc").status_code == 401
    assert c.delete("/api/counsellor/devices/ffffeeeeddddcccc", headers=h).status_code == 200
    assert all(d["kid"] != "ffffeeeeddddcccc" for d in c.get("/api/counsellor/devices").json())
    monkeypatch.setattr(main, "COUNSELLOR_KEY_EXPIRES", "2000-01-01")
    assert c.get("/api/cases", headers=h).status_code == 401


def test_a_question_in_arabic_is_answered_in_arabic(monkeypatch):
    from app import tutor
    _fake_llm(monkeypatch, "NO_ANSWER")
    r = tutor.answer("شو يعني اني حاملة؟", [{"gene": "HBB", "classification": "Pathogenic"}], [], lang="en")
    assert "مستشار" in r["text"]


def test_simulator_draws_follow_the_mendelian_shares():
    mod = (ROOT / "web" / "simulator.js").as_uri()
    script = (f"import {{draw}} from '{mod}'; const n = 20000, c = {{}};"
              "for (let i = 0; i < n; i++) { const o = draw('AR'); c[o] = (c[o] || 0) + 1; }"
              "console.log(JSON.stringify(Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v / n]))));")
    r = json.loads(_node(script))
    assert abs(r["affected"] - 0.25) < 0.02 and abs(r["carrier"] - 0.5) < 0.02 and abs(r["neither"] - 0.25) < 0.02


def test_concordance_benchmark_is_100_percent():
    if not shutil.which("node"):
        pytest.skip("node not installed")
    import importlib.util
    spec = importlib.util.spec_from_file_location("benchmark", ROOT / "tools" / "benchmark.py")
    bm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bm)
    res = bm.run()
    assert res["agree"] == res["couples"] == 100 and res["at_risk"] > 0 and res["overlap_not_flagged"] > 0
    assert res["family_agree"] == len(res["family"]) and res["sim_ok"]
