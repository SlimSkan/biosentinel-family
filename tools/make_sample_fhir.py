"""Writes web/samples/<person>_report.fhir.json: the fictional demo results as HL7 FHIR R4
Genomics Reporting Bundles (what a lab system would send instead of a PDF).

Run: python tools/make_sample_fhir.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = ["HBB", "CFTR", "GJB2", "SMN1", "PAH", "HEXA", "BTD", "CYP21A2", "G6PD", "DMD"]
HGNC = {"HBB": "HGNC:4827", "CFTR": "HGNC:1884", "GJB2": "HGNC:4284", "SMN1": "HGNC:11117", "PAH": "HGNC:8582",
        "HEXA": "HGNC:4878", "BTD": "HGNC:1122", "CYP21A2": "HGNC:2600", "G6PD": "HGNC:4057", "DMD": "HGNC:2928"}
SIG = {"Pathogenic": "LA6668-3", "Likely pathogenic": "LA26332-9", "Uncertain significance": "LA26333-7"}
LOINC = "http://loinc.org"


def cc(code, display, system=LOINC):
    return {"coding": [{"system": system, "code": code, "display": display}]}


def variant_obs(i, gene, variant, cls, present=True):
    comps = [{"code": cc("48018-6", "Gene studied [ID]"),
              "valueCodeableConcept": cc(HGNC[gene], gene, "http://www.genenames.org/geneId")}]
    if present:
        m_c = re.search(r"c\.[^\s(]+", variant)
        m_p = re.search(r"p\.[A-Za-z0-9_*]+", variant)
        if m_c:
            comps.append({"code": cc("48004-6", "DNA change (c.HGVS)"), "valueCodeableConcept": {"text": m_c.group(0)}})
        if m_p:
            comps.append({"code": cc("48005-3", "Amino acid change (pHGVS)"), "valueCodeableConcept": {"text": m_p.group(0)}})
        if not m_c and not m_p:
            comps.append({"code": cc("48004-6", "DNA change (c.HGVS)"), "valueCodeableConcept": {"text": variant}})
        comps.append({"code": cc("53034-5", "Allelic state"), "valueCodeableConcept": cc("LA6706-1", "Heterozygous")})
        comps.append({"code": cc("53037-8", "Genetic variation clinical significance"),
                      "valueCodeableConcept": cc(SIG[cls], cls)})
    return {"resourceType": "Observation", "id": f"variant-{i}", "status": "final",
            "meta": {"profile": ["http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/variant"]},
            "category": [cc("laboratory", "Laboratory", "http://terminology.hl7.org/CodeSystem/observation-category")],
            "code": cc("69548-6", "Genetic variant assessment"),
            "subject": {"reference": "Patient/p1"},
            "valueCodeableConcept": cc("LA9633-4", "Present") if present else cc("LA9634-2", "Absent"),
            "component": comps}


def bundle(pid, person):
    obs = [variant_obs(i, v["gene"], v["variant"], v["classification"]) for i, v in enumerate(person["variants"], 1)]
    carried = {v["gene"] for v in person["variants"]}
    obs += [variant_obs(100 + i, g, "", "", present=False) for i, g in enumerate(PANEL) if g not in carried]
    report = {"resourceType": "DiagnosticReport", "id": "r1", "status": "final",
              "meta": {"profile": ["http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/genomic-report"]},
              "code": cc("51969-4", "Genetic analysis report"),
              "subject": {"reference": "Patient/p1"}, "performer": [{"reference": "Organization/lab"}],
              "conclusion": "Fictional demo result. Carrier screening, 10-gene premarital panel.",
              "result": [{"reference": f"Observation/{o['id']}"} for o in obs]}
    entries = [{"resourceType": "Patient", "id": "p1", "name": [{"given": [person["name"]]}],
                "gender": "female" if person["sex"] == "F" else "male"},
               {"resourceType": "Organization", "id": "lab", "name": person["lab"]}, report] + obs
    return {"resourceType": "Bundle", "type": "collection", "meta": {"tag": [{"code": "fictional-demo"}]},
            "entry": [{"fullUrl": f"urn:uuid:{pid}-{e['resourceType'].lower()}-{e['id']}", "resource": e} for e in entries]}


if __name__ == "__main__":
    personas = json.loads((ROOT / "data" / "personas.json").read_text(encoding="utf-8"))["personas"]
    for pid, person in personas.items():
        out = ROOT / "web" / "samples" / f"{pid}_report.fhir.json"
        out.write_text(json.dumps(bundle(pid, person), indent=1) + "\n", encoding="utf-8")
        print("wrote", out.name)
