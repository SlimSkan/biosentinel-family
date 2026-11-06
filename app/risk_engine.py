"""Deterministic Mendelian risk engine.

Design rule: every number a user sees comes from THIS file, never from the AI.
The rules are textbook genetics, so they can be checked by any geneticist.

Inheritance types on our panel
  AR = autosomal recessive. A child is affected only if it inherits a
       pathogenic variant from BOTH parents. So risk exists only when both
       partners carry a variant in the SAME gene.
  XL = X-linked. The gene is on the X chromosome. A carrier mother can pass
       it to sons (who have one X) regardless of the father's result.
"""
from dataclasses import dataclass, asdict

from . import knowledge

PATHOGENIC = {"Pathogenic", "Likely pathogenic"}
VUS = "Uncertain significance"


@dataclass
class Risk:
    gene: str
    inheritance: str
    # chances per pregnancy, as fractions (0.25 = 25%)
    affected: float
    carrier: float
    unaffected: float
    explanation_key: str      # which explanation template applies
    escalation: str           # "required" | "recommended" | "none"
    escalation_reason: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["affected_pct"] = round(self.affected * 100)
        d["carrier_pct"] = round(self.carrier * 100)
        d["unaffected_pct"] = round(self.unaffected * 100)
        return d


def individual_findings(variants: list[dict], sex: str) -> list[dict]:
    """What one person should know about their OWN result, before any matching.

    Only X-linked findings in a woman carry a risk that does not depend on the
    partner, so only those get a number here. A variant of uncertain
    significance (VUS) always goes to a counsellor: we must not interpret it.
    """
    out = []
    for v in variants:
        g = knowledge.gene(v["gene"])
        item = {"gene": v["gene"], "variant": v["variant"], "classification": v["classification"],
                "inheritance": g["inheritance"], "escalation": "none", "reason": ""}
        if v["classification"] == VUS:
            item["escalation"] = "required"
            item["reason"] = "vus"
        elif g["inheritance"] == "XL" and sex == "F":
            # Carrier mother: each son 50% affected, each daughter 50% carrier.
            item["xl_son_affected_pct"] = 50
            item["xl_daughter_carrier_pct"] = 50
            item["escalation"] = "recommended"
            item["reason"] = "xl_carrier_female"
        out.append(item)
    return out


def couple_risk(shared_genes: list[str]) -> list[Risk]:
    """Risk for each gene in which BOTH partners carry a pathogenic variant.

    `shared_genes` is the output of the private matching (PSI) step, so this
    function never sees either partner's full result.
    """
    risks = []
    for symbol in sorted(set(shared_genes)):
        g = knowledge.gene(symbol)
        if g["inheritance"] == "AR":
            # Punnett square: carrier x carrier -> 1/4 affected, 1/2 carrier, 1/4 neither.
            risks.append(Risk(symbol, "AR", 0.25, 0.50, 0.25, "ar_both_carriers",
                              "required", "shared_carrier"))
        # XL genes are handled per person in individual_findings(): for X-linked
        # conditions the father's carrier status does not create a shared risk
        # in the same way, so they are never "couple" findings here.
    return risks


def allowed_numbers(risks: list[Risk], findings: list[dict] | None = None) -> set[int]:
    """Every percentage the AI is allowed to mention. Used by the guardrails."""
    nums = {0, 100}
    for r in risks:
        nums |= {round(r.affected * 100), round(r.carrier * 100), round(r.unaffected * 100)}
    for f in findings or []:
        for k in ("xl_son_affected_pct", "xl_daughter_carrier_pct"):
            if k in f:
                nums.add(f[k])
    return nums


# ---------------------------------------------------------------- family (cascade)
# If you carry a variant, you inherited it from one parent. A relative's chance of
# carrying the SAME variant is the chance they inherited that copy too, which halves
# with each step of relationship. These are minimums from your side of the family:
# the general population chance comes on top, and it is higher when parents are related.
RELATIVE_SHARE = {
    "parent": 0.5, "child": 0.5, "sibling": 0.5,                          # 1st degree
    "half_sibling": 0.25, "grandparent": 0.25, "grandchild": 0.25,        # 2nd degree
    "aunt_uncle": 0.25, "niece_nephew": 0.25,
    "first_cousin": 0.125,                                                # 3rd degree
}
RELATIONS = list(RELATIVE_SHARE) + ["unsure"]


def can_invite(classification: str) -> bool:
    """Only clear results are shared with family. An uncertain variant (VUS) is not."""
    return classification in PATHOGENIC


def relative_chance(gene_symbol: str, relation: str) -> dict:
    """What a relative is told, given the gene and how they are related.

    Autosomal recessive + known relation -> a number ("relative_ar").
    X-linked -> no number: it depends on which side of the family, and on sex,
    which only a counsellor can work out ("relative_xl").
    Relation unknown -> no number ("relative_general").
    """
    if relation not in RELATIONS:
        raise ValueError(f"unknown relation: {relation}")
    g = knowledge.gene(gene_symbol)
    if g["inheritance"] == "XL":
        return {"key": "relative_xl", "chance_pct": None}
    if relation == "unsure":
        return {"key": "relative_general", "chance_pct": None}
    pct = RELATIVE_SHARE[relation] * 100
    return {"key": "relative_ar", "chance_pct": int(pct) if pct == int(pct) else pct}
