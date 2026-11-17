"""BioSentinel Family - web server (FastAPI).

What the server does:
  - serves the web app (folder web/)
  - simulates the lab: hands a demo person's report to their own phone
  - explains findings (risk engine + Gemma + guardrails)
  - relays the private-matching messages between two phones (sees only locked values)
  - keeps the counsellor inbox (only summaries a couple chose to send)
  - hosts anonymous family invites (one gene, no sender identity, two counters)

What the server never does: store a carrier result, see a secret PSI key,
or learn genes that are not shared. Everything is in memory: restart = wiped.

Run:  uvicorn app.main:app --reload --port 8000
"""
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field

from . import brief, explainer, knowledge, llm, risk_engine, tutor

app = FastAPI(title="BioSentinel Family", version="0.3.0")
WEB = Path(__file__).resolve().parent.parent / "web"

MAX_ITEMS = 64          # sanity limit on a PSI list
SESSION_TTL = 30 * 60   # match sessions expire after 30 minutes
# On a public deployment, set BSF_COUNSELLOR_KEY so only the counsellor can read the inbox.
# Unset (local demo): the inbox is open, as before.
COUNSELLOR_KEY = os.environ.get("BSF_COUNSELLOR_KEY", "")


# ---------------------------------------------------------------- health
@app.get("/api/health")
def health(probe: int = 0):
    """Is the server up, and can it reach Gemma? Use it to warm the AI before a demo.

    Note: on Azure, calling this also wakes the Gemma container if it was scaled to zero.
    """
    ai = llm.status()
    out = {"ok": True, "version": app.version, "provider": llm.provider(), "model": llm.model_name(), "ai": ai}
    if probe:
        out["probe"] = llm.probe()
    return out


# ---------------------------------------------------------------- lab (demo)
@app.get("/api/personas")
def list_personas():
    return [{"id": k, "name": v["name"]} for k, v in knowledge.personas().items()]


@app.get("/api/personas/{pid}")
def get_persona(pid: str):
    """Simulates the screening lab delivering a report to the person's phone."""
    p = knowledge.personas().get(pid)
    if not p:
        raise HTTPException(404, "unknown persona")
    return p


@app.get("/api/panel")
def get_panel():
    """The genes this app covers (public). Used by the phone to read an imported report."""
    genes = knowledge.kb()["genes"]
    return {"genes": list(genes), "inheritance": {g: v["inheritance"] for g, v in genes.items()}}


# ---------------------------------------------------------------- explain
class ExplainOne(BaseModel):
    gene: str
    classification: str
    sex: str = Field(pattern="^(F|M)$")
    lang: str = Field("en", pattern="^(en|ar)$")
    level: str = Field("standard", pattern="^(simple|standard|detailed)$")
    ai: bool = False


@app.post("/api/explain/finding")
def explain_finding(req: ExplainOne):
    """Explain ONE gene from a person's own report. No name, no other genes."""
    if req.gene not in knowledge.kb()["genes"]:
        raise HTTPException(400, "gene not on panel")
    variant = {"gene": req.gene, "variant": "", "classification": req.classification}
    finding = risk_engine.individual_findings([variant], req.sex)[0]
    key = {"vus": "vus", "xl_carrier_female": "xl_carrier_female"}.get(finding["reason"], "carrier_self")
    allowed = risk_engine.allowed_numbers([], [finding])
    out = explainer.explain(key, req.gene, req.lang, req.level, allowed, req.ai)
    condition = knowledge.gene(req.gene)["condition"][req.lang]
    return {"finding": finding, "key": key, "condition": condition, **out}


class ExplainCouple(BaseModel):
    shared_genes: list[str]
    lang: str = Field("en", pattern="^(en|ar)$")
    level: str = Field("standard", pattern="^(simple|standard|detailed)$")
    ai: bool = False


@app.post("/api/explain/couple")
def explain_couple(req: ExplainCouple):
    """Explain the result of private matching. Receives only the shared genes."""
    for g in req.shared_genes:
        if g not in knowledge.kb()["genes"]:
            raise HTTPException(400, f"gene not on panel: {g}")
    risks = risk_engine.couple_risk(req.shared_genes)
    if not risks:
        out = explainer.explain("no_shared", None, req.lang, req.level, {0, 100}, req.ai)
        return {"risks": [], "explanations": [{"gene": None, **out}]}
    allowed = risk_engine.allowed_numbers(risks)
    explanations = [{"gene": r.gene, **explainer.explain(r.explanation_key, r.gene, req.lang, req.level, allowed, req.ai)}
                    for r in risks]
    return {"risks": [r.to_dict() for r in risks], "explanations": explanations}


# ---------------------------------------------------------------- family-tree carrier map
class FamilyMap(BaseModel):
    gene: str = Field(max_length=12)
    sex: str = Field("F", pattern="^(F|M)$")
    tested: dict[str, str] = Field(default_factory=dict, max_length=20)


@app.post("/api/family-map")
def get_family_map(req: FamilyMap):
    """Each relative's chance of carrying the same change (relationships only, no names)."""
    if req.gene not in knowledge.kb()["genes"]:
        raise HTTPException(400, "gene not on panel")
    return risk_engine.family_map(req.gene, req.tested, req.sex)


# ---------------------------------------------------------------- adaptive teaching (live AI)
class TeachBack(BaseModel):
    concept: str = Field(pattern="^(carrier|partner|autonomy)$")
    question: str = Field("", max_length=300)
    wrong_answer: str = Field("", max_length=200)
    lang: str = Field("en", pattern="^(en|ar)$")
    level: str = Field("simple", pattern="^(simple|standard|detailed)$")
    ai: bool = False


@app.post("/api/teachback")
def teachback(req: TeachBack):
    """Re-explain one idea the reader got wrong in the quick check, starting from their answer."""
    if not req.ai:
        return {"text": tutor.CONCEPTS[req.concept][req.lang], "source": "template", "problems": []}
    return tutor.reexplain(req.concept, req.wrong_answer, req.question, req.lang, req.level)


class Finding(BaseModel):
    gene: str = Field(max_length=12)
    classification: str = Field(max_length=40)


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=300)
    findings: list[Finding] = Field(default_factory=list, max_length=12)
    shared: list[str] = Field(default_factory=list, max_length=12)
    lang: str = Field("en", pattern="^(en|ar)$")
    level: str = Field("standard", pattern="^(simple|standard|detailed)$")


@app.post("/api/ask")
def ask(req: Ask):
    """Answer a free question from numbered facts about the reader's own results, with sources.
    Receives gene names and classifications only: no name, no lab, no contact."""
    return tutor.answer(req.question, [f.model_dump() for f in req.findings],
                        [g for g in req.shared if g in knowledge.kb()["genes"]], req.lang, req.level)


# ---------------------------------------------------------------- PSI relay
# A "mailbox" for the four PSI messages. Values are hex strings of locked numbers.
SESSIONS: dict[str, dict] = {}


def _session(code: str) -> dict:
    s = SESSIONS.get(code.upper())
    if not s or time.time() - s["created"] > SESSION_TTL:
        raise HTTPException(404, "match code not found or expired")
    return s


class Locked(BaseModel):
    values: list[str] = Field(max_length=MAX_ITEMS)


class B1(BaseModel):
    a_double: list[str] = Field(max_length=MAX_ITEMS)
    b_locked: list[str] = Field(max_length=MAX_ITEMS)


@app.post("/api/match")
def match_create():
    code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))
    SESSIONS[code] = {"created": time.time(), "a_locked": None, "a_double": None,
                      "b_locked": None, "b_double": None}
    return {"code": code}


@app.post("/api/match/{code}/a1")
def match_a1(code: str, body: Locked):
    _session(code)["a_locked"] = body.values
    return {"ok": True}


@app.post("/api/match/{code}/b1")
def match_b1(code: str, body: B1):
    s = _session(code)
    if s["a_locked"] is None:
        raise HTTPException(409, "partner has not started yet")
    s["a_double"], s["b_locked"] = body.a_double, body.b_locked
    return {"ok": True}


@app.post("/api/match/{code}/a2")
def match_a2(code: str, body: Locked):
    _session(code)["b_double"] = body.values
    return {"ok": True}


@app.get("/api/match/{code}")
def match_state(code: str):
    s = _session(code)
    return {k: v for k, v in s.items() if k != "created"}


# ---------------------------------------------------------------- family invites
# An invite is a random id pointing to ONE gene. It stores no name, no variant,
# no sex and no other result. The sender keeps a second secret ("owner") that
# lets them see two counters, never who opened the page.
INVITES: dict[str, dict] = {}
INVITE_TTL = 30 * 24 * 3600   # 30 days


def _invite(iid: str) -> dict:
    inv = INVITES.get(iid)
    if not inv or time.time() - inv["created"] > INVITE_TTL:
        raise HTTPException(404, "invite not found or expired")
    return inv


class InviteCreate(BaseModel):
    gene: str
    classification: str


@app.post("/api/invites")
def invite_create(req: InviteCreate):
    if req.gene not in knowledge.kb()["genes"]:
        raise HTTPException(400, "gene not on panel")
    if not risk_engine.can_invite(req.classification):
        raise HTTPException(400, "uncertain results are not shared with family")
    iid, owner = secrets.token_urlsafe(9), secrets.token_urlsafe(18)
    INVITES[iid] = {"gene": req.gene, "owner": owner, "created": time.time(), "opened": 0, "next_step": 0}
    return {"id": iid, "owner": owner}


@app.get("/api/invites/{iid}")
def invite_read(iid: str):
    """What the relative's page needs: the gene and its condition name. Nothing about the sender."""
    g = knowledge.gene(_invite(iid)["gene"])
    return {"gene": _invite(iid)["gene"], "inheritance": g["inheritance"], "condition": g["condition"],
            "relations": risk_engine.RELATIONS}


class InviteEvent(BaseModel):
    event: str = Field(pattern="^(opened|next_step)$")


@app.post("/api/invites/{iid}/event")
def invite_event(iid: str, body: InviteEvent):
    _invite(iid)[body.event] += 1
    return {"ok": True}


class InviteExplain(BaseModel):
    relation: str
    lang: str = Field("en", pattern="^(en|ar)$")
    level: str = Field("standard", pattern="^(simple|standard|detailed)$")
    ai: bool = False


@app.post("/api/invites/{iid}/explain")
def invite_explain(iid: str, req: InviteExplain):
    """Explain the invite to the relative. The relation is used, then forgotten (not stored)."""
    gene = _invite(iid)["gene"]
    if req.relation not in risk_engine.RELATIONS:
        raise HTTPException(400, "unknown relation")
    rc = risk_engine.relative_chance(gene, req.relation)
    allowed = {0, 100} | ({rc["chance_pct"]} if rc["chance_pct"] is not None else set())
    out = explainer.explain(rc["key"], gene, req.lang, req.level, allowed, req.ai, pct=rc["chance_pct"])
    return {"key": rc["key"], "chance_pct": rc["chance_pct"], **out}


@app.get("/api/invites/{iid}/status")
def invite_status(iid: str, x_invite_owner: str = Header("")):
    """For the sender only (needs the owner secret): two counters, nothing else."""
    inv = _invite(iid)
    if not secrets.compare_digest(x_invite_owner, inv["owner"]):
        raise HTTPException(403, "not the owner of this invite")
    return {"opened": inv["opened"], "next_step": inv["next_step"]}


# ---------------------------------------------------------------- counsellor referral
# Referral pathway: the person picks a certified counselling service, the phone builds an
# explainable brief (/api/brief), ENCRYPTS it for the counsellor's devices (web/seal.js) and
# sends only ciphertext. The person keeps a private token to follow the status.
CASES: list[dict] = []
DEVICES: list[dict] = []          # counsellor devices: public keys only (private keys stay in their browser)
MAX_DEVICES = 20
STATUSES = ("new", "seen", "contacted", "appointment_offered", "closed")
SERVICES = [   # demo listings: fictional services, clearly labelled
    {"id": "clinic", "name": "Demo Genetic Counselling Clinic", "mode": "In person or video",
     "languages": "Arabic, English", "wait": "Usually within 2 weeks", "certified": True},
    {"id": "tele", "name": "Demo Tele-genetics Service", "mode": "Video",
     "languages": "Arabic, English, Urdu", "wait": "Usually within 1 week", "certified": True},
    {"id": "hospital", "name": "Demo Hospital Genetics Department", "mode": "In person",
     "languages": "Arabic, English", "wait": "Usually within 3 weeks", "certified": True},
]


def _counsellor(key: str):
    if COUNSELLOR_KEY and not secrets.compare_digest(key, COUNSELLOR_KEY):
        raise HTTPException(401, "counsellor key required")


@app.get("/api/services")
def list_services():
    return SERVICES


class BriefIn(BaseModel):
    shared_genes: list[str] = Field(default_factory=list, max_length=12)
    findings: list[dict] = Field(default_factory=list, max_length=12)
    quiz_score: int | None = None
    missed: list[str] = Field(default_factory=list, max_length=3)
    feeling: str = Field("", max_length=2)
    picks: list[str] = Field(default_factory=list, max_length=6)
    family: list[str] = Field(default_factory=list, max_length=5)
    pregnant: str = Field("", pattern="^(yes|no|)$")
    language: str = Field("en", pattern="^(en|ar)$")


@app.post("/api/brief")
def make_brief(req: BriefIn):
    """Build the pre-consultation brief. De-identified input (no name, no contact); nothing stored."""
    clean = [{"gene": str(f.get("gene", ""))[:12], "classification": str(f.get("classification", ""))[:40],
              "reason": str(f.get("reason", ""))[:24]} for f in req.findings]
    return brief.build(req.model_dump() | {"findings": clean})


class Device(BaseModel):
    kid: str = Field(pattern="^[0-9a-f]{16}$")
    jwk: dict


@app.post("/api/counsellor/devices")
def register_device(d: Device, x_counsellor_key: str = Header("")):
    """A counsellor's browser registers its PUBLIC key, so new cases are sealed for it."""
    _counsellor(x_counsellor_key)
    jwk = {k: str(d.jwk.get(k, "")) for k in ("kty", "crv", "x", "y")}
    if jwk["kty"] != "EC" or jwk["crv"] != "P-256" or not jwk["x"] or not jwk["y"]:
        raise HTTPException(400, "expected an EC P-256 public key")
    if not any(x["kid"] == d.kid for x in DEVICES):
        DEVICES.append({"kid": d.kid, "jwk": jwk, "added": time.strftime("%Y-%m-%d %H:%M")})
        del DEVICES[:-MAX_DEVICES]
    return {"ok": True, "devices": len(DEVICES)}


@app.get("/api/counsellor/devices")
def list_devices():
    """Public keys only: anyone may encrypt for the counsellors; only they can decrypt."""
    return [{"kid": d["kid"], "jwk": d["jwk"]} for d in DEVICES]


class Sealed(BaseModel):
    v: int
    alg: str = Field(max_length=64)
    epk: dict
    iv: str = Field(max_length=64)
    ct: str = Field(max_length=200_000)
    keys: list[dict] = Field(max_length=MAX_DEVICES)


class Case(BaseModel):
    service: str = Field("clinic", max_length=20)
    priority: str = Field("routine", pattern="^(routine|urgent)$")   # routing only: "urgent" = current pregnancy
    sealed: Sealed | None = None
    # older, unencrypted form (kept for the family-invite page and old clients)
    shared_genes: list[str] = []
    other_reasons: list[str] = []
    language: str = "en"
    quiz_score: int | None = None
    contact: str = Field("", max_length=120)
    note: str = Field("", max_length=500)


@app.post("/api/cases")
def create_case(case: Case):
    token = secrets.token_urlsafe(16)
    item = case.model_dump() | {"id": len(CASES) + 1, "received": time.strftime("%Y-%m-%d %H:%M"),
                                "status": "new", "updated": time.strftime("%Y-%m-%d %H:%M"),
                                "_token": token}
    if case.sealed:      # drop the empty plaintext fields: the server keeps ciphertext only
        for k in ("shared_genes", "other_reasons", "quiz_score", "contact", "note"):
            item.pop(k, None)
    CASES.append(item)
    return {"id": item["id"], "token": token}


@app.get("/api/cases")
def list_cases(x_counsellor_key: str = Header("")):
    _counsellor(x_counsellor_key)
    return [{k: v for k, v in c.items() if k != "_token"} for c in reversed(CASES)]


def _case(cid: int) -> dict:
    for c in CASES:
        if c["id"] == cid:
            return c
    raise HTTPException(404, "case not found")


class StatusIn(BaseModel):
    status: str


@app.post("/api/cases/{cid}/status")
def set_status(cid: int, body: StatusIn, x_counsellor_key: str = Header("")):
    _counsellor(x_counsellor_key)
    if body.status not in STATUSES:
        raise HTTPException(400, "unknown status")
    c = _case(cid)
    c["status"], c["updated"] = body.status, time.strftime("%Y-%m-%d %H:%M")
    return {"ok": True}


@app.get("/api/cases/{cid}/status")
def case_status(cid: int, x_case_token: str = Header("")):
    """The person follows their own referral with the token their phone received."""
    c = _case(cid)
    if not secrets.compare_digest(x_case_token, c["_token"]):
        raise HTTPException(403, "wrong token")
    svc = next((x["name"] for x in SERVICES if x["id"] == c.get("service")), "")
    return {"id": cid, "status": c["status"], "updated": c["updated"], "service": svc, "priority": c["priority"]}


# ---------------------------------------------------------------- web app
@app.middleware("http")
async def always_check_for_updates(request, call_next):
    """Tell browsers to check for a newer file every time (a cheap 'not modified' reply if
    nothing changed). Without this header a browser may reuse an old app.js for hours
    after a new version is deployed."""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
