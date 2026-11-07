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
    monkeypatch.setattr(explainer, "OLLAMA_URL", "http://127.0.0.1:9")    # nothing listens here
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
