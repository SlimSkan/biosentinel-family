"""Explainable pre-consultation brief for a genetic counsellor.

Two parts, on purpose:
  1. STRUCTURED (rules): reason for referral, risk figures from the risk engine, how well the
     couple understood (quick check), what they want to discuss, relatives marked as tested,
     and a suggested agenda. Always correct, always available.
  2. SUMMARY (Gemma 4): three or four sentences for the specialist, written ONLY from the
     numbered facts of part 1, with a cited fact after every sentence. The citations are
     checked; if anything fails, a rule-written summary is used instead.

Input is de-identified: no name, no contact. The phone then encrypts the brief for the
counsellor's device, so the server stores only ciphertext.
"""
import re

from . import guardrails, knowledge, llm, risk_engine

CONCEPT_LABEL = {"carrier": "what being a carrier means", "partner": "that risk depends on both partners",
                 "autonomy": "that decisions are theirs"}
OPTION_LABEL = {"counselling": "genetic counselling", "confirm": "confirmatory testing",
                "pgt": "IVF with embryo testing (PGT-M)", "prenatal": "testing during pregnancy",
                "newborn": "newborn testing and early care", "none": "no further action"}
FEELING = {"0": "calm", "1": "unsure", "2": "worried"}

SUMMARY_PROMPT = """You write a short pre-consultation summary for a certified genetic counsellor.
Strict rules:
- Use ONLY the numbered FACTS. After EVERY sentence cite the fact(s) it comes from, like [F2] or [F1][F4].
- 3 or 4 sentences, neutral clinical English, no headings, no markdown.
- Numbers only as they appear in the FACTS. No diagnosis beyond the facts, no recommendation about marriage or pregnancy.
- Describe the results as facts ("Both partners carry..."). Do not claim what the couple understands; report the
  quick-check result exactly as the facts give it, and what they want to discuss, if the facts say so."""

_CITE = re.compile(r"\[F(\d+)\]")


def build(data: dict) -> dict:
    """data: shared_genes, findings [{gene, classification, reason}], quiz_score, missed [concepts],
    feeling, picks [option ids], family [str], pregnant ("yes"/"no"/""), language."""
    shared = [g for g in data.get("shared_genes", []) if g in knowledge.kb()["genes"]]
    findings = [f for f in data.get("findings", []) if f.get("gene") in knowledge.kb()["genes"]]
    facts, reasons, risks, agenda = [], [], [], []

    couple = risk_engine.couple_risk(shared)
    for r in couple:
        g = knowledge.gene(r.gene)
        d = r.to_dict()
        line = (f"Both partners carry a pathogenic change in {r.gene} ({g['condition']['en']}, autosomal recessive): "
                f"each pregnancy {d['affected_pct']}% affected, {d['carrier_pct']}% carrier, {d['unaffected_pct']}% neither.")
        reasons.append(f"Shared carrier status: {r.gene}")
        risks.append(line)
        facts.append(line)
        agenda.append(f"Confirm both {r.gene} results; explain the 25% figure and the options.")
    for f in findings:
        g = knowledge.gene(f["gene"])
        if f.get("reason") == "xl_carrier_female":
            line = (f"The woman carries a pathogenic change in {f['gene']} ({g['condition']['en']}, X-linked): "
                    f"each son 50% affected, each daughter 50% carrier, independent of the partner.")
            reasons.append(f"X-linked carrier: {f['gene']}")
            risks.append(line)
            facts.append(line)
            agenda.append(f"Discuss {f['gene']} for sons and daughters, and female relatives on the same side.")
        elif f.get("reason") == "vus":
            line = f"One partner has a variant of uncertain significance in {f['gene']} ({g['condition']['en']}); not a diagnosis."
            reasons.append(f"Uncertain result (VUS): {f['gene']}")
            facts.append(line)
            agenda.append(f"Explain the VUS in {f['gene']} and whether reclassification is expected.")
    if not reasons:
        reasons.append("Questions about screening results")
        facts.append("No shared carrier gene and no escalated finding on this 10-gene panel.")

    q = data.get("quiz_score")
    missed = [CONCEPT_LABEL[c] for c in data.get("missed", []) if c in CONCEPT_LABEL]
    understanding = ("Quick check not shared." if q is None else
                     f"Quick check: {q} of 3 correct." + (f" Needed re-explanation of {', '.join(missed)}." if missed else ""))
    facts.append(understanding)
    if missed:
        agenda.append("Check understanding of: " + ", ".join(missed) + ".")
    picks = [OPTION_LABEL[p] for p in data.get("picks", []) if p in OPTION_LABEL]
    if picks:
        facts.append("The couple wants to discuss: " + ", ".join(picks) + ".")
        agenda.append("Go through the options they picked: " + ", ".join(picks) + ".")
    feeling = FEELING.get(str(data.get("feeling", "")))
    if feeling:
        facts.append(f"Self-reported feeling: {feeling}.")
        if feeling == "worried":
            agenda.append("Allow time for emotional support.")
    family = [x for x in data.get("family", []) if x][:5]
    if family:
        facts.append("Relatives marked as tested (relationships only): " + "; ".join(family) + ".")
        agenda.append("Plan cascade testing for relatives.")
    priority = "urgent" if data.get("pregnant") == "yes" else "routine"
    if priority == "urgent":
        facts.append("The person reports a current pregnancy.")
        agenda.insert(0, "Current pregnancy reported: time-sensitive options; offer an early appointment.")

    allowed = {0, 100} | guardrails._percentages(" ".join(facts))
    summary, sources, source = _summary(facts, allowed)
    if summary is None:
        summary = " ".join([f"Referral for {', '.join(reasons).lower()}.", understanding] +
                           ([f"They want to discuss {', '.join(picks)}."] if picks else []))
        source = "rules"
    return {
        "priority": priority,
        "reasons": reasons, "risks": risks, "understanding": understanding,
        "picks": picks, "feeling": feeling or "", "family": family, "agenda": agenda,
        "facts": [{"id": f"F{i + 1}", "text": t} for i, t in enumerate(facts)],
        "summary": summary, "summary_source": source, "summary_sources": sources,
        "language": data.get("language", "en"),
        "disclaimer": "Educational pre-consultation summary from screening results. Not a diagnosis. "
                      "Verify against the laboratory report.",
    }


def _summary(facts: list[str], allowed: set) -> tuple:
    numbered = "\n".join(f"F{i + 1}: {t}" for i, t in enumerate(facts))
    try:
        raw = llm.ask(SUMMARY_PROMPT, f"FACTS:\n{numbered}", max_tokens=350)
    except Exception:
        return None, [], "rules"
    raw = re.sub(r"[*#`]+", "", raw).strip()
    raw = re.sub(r"([.!?؟])\s*((?:\[F\d+\]\s*)+)", lambda m: " " + m.group(2).strip() + m.group(1) + " ", raw).strip()
    cited = {int(n) for n in _CITE.findall(raw)}
    sentences = [s for s in re.split(r"(?<=[.!?\]])\s+", raw) if s.strip()]
    if not cited or any(n < 1 or n > len(facts) for n in cited):
        return None, [], "rules"
    if any(not _CITE.search(s) and len(s.split()) > 3 for s in sentences):
        return None, [], "rules"
    text = re.sub(r"\s*\[F\d+\]", "", raw).strip()
    if guardrails.check(text, allowed):
        return None, [], "rules"
    return text, [f"F{n}" for n in sorted(cited)], "ai"
