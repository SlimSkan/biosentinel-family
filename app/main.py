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

from . import explainer, knowledge, risk_engine

app = FastAPI(title="BioSentinel Family", version="0.2.0")
WEB = Path(__file__).resolve().parent.parent / "web"

MAX_ITEMS = 64          # sanity limit on a PSI list
SESSION_TTL = 30 * 60   # match sessions expire after 30 minutes
# On a public deployment, set BSF_COUNSELLOR_KEY so only the counsellor can read the inbox.
# Unset (local demo): the inbox is open, as before.
COUNSELLOR_KEY = os.environ.get("BSF_COUNSELLOR_KEY", "")


# ---------------------------------------------------------------- health
@app.get("/api/health")
def health():
    """Is the server up, and can it reach Gemma? Use it to warm the AI before a demo.

    Note: on Azure, calling this also wakes the Gemma container if it was scaled to zero.
    """
    try:
        r = httpx.get(f"{explainer.OLLAMA_URL}/api/tags", timeout=5)
        names = [m["name"] for m in r.json().get("models", [])]
        ai = {"reachable": True, "model_present": explainer.MODEL in names}
    except Exception as e:
        ai = {"reachable": False, "error": type(e).__name__}
    return {"ok": True, "version": app.version, "model": explainer.MODEL, "ai": ai}


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


# ---------------------------------------------------------------- counsellor
CASES: list[dict] = []


class Case(BaseModel):
    shared_genes: list[str] = []
    other_reasons: list[str] = []          # e.g. "vus", "xl_carrier_female", "worried"
    language: str = "en"
    quiz_score: int | None = None
    contact: str = Field("", max_length=120)   # what the couple chose to share
    note: str = Field("", max_length=500)


@app.post("/api/cases")
def create_case(case: Case):
    item = case.model_dump() | {"id": len(CASES) + 1, "received": time.strftime("%Y-%m-%d %H:%M"),
                                "status": "new"}
    CASES.append(item)
    return {"id": item["id"]}


@app.get("/api/cases")
def list_cases(x_counsellor_key: str = Header("")):
    if COUNSELLOR_KEY and not secrets.compare_digest(x_counsellor_key, COUNSELLOR_KEY):
        raise HTTPException(401, "counsellor key required")
    return list(reversed(CASES))


# ---------------------------------------------------------------- web app
@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
