// BioSentinel Family - reads a lab result sent as HL7 FHIR R4 (Genomics Reporting IG), with fixed rules (no AI).
//
// Accepts a Bundle (or a single DiagnosticReport with contained resources). Uses the standard codes:
//   Observation code LOINC 69548-6 "Genetic variant assessment"
//     value: LA9633-4 Present / LA9634-2 Absent
//     component 48018-6 "Gene studied" (HGNC code, display = gene symbol)
//     component 48004-6 "DNA change (c.HGVS)" and 48005-3 "Amino acid change (p.HGVS)"
//     component 53037-8 "Genetic variation clinical significance" (LA6668-3 Pathogenic,
//       LA26332-9 Likely pathogenic, LA26333-7 Uncertain significance, LA26334-5 Likely benign, LA6675-8 Benign)
//   Patient.gender -> sex (it changes what X-linked results mean), Organization -> lab.
// Returns the same shape as parseReportText(), so the confirm screen is shared.
// No browser code here, so the tests can run it in Node.

const LOINC = "http://loinc.org";
const SIGNIFICANCE = {
  "LA6668-3": "Pathogenic", "LA26332-9": "Likely pathogenic", "LA26333-7": "Uncertain significance",
  "LA26334-5": "Likely benign", "LA6675-8": "Benign",
};
const TEXT_SIGNIFICANCE = [
  [/likely\s+pathogenic/i, "Likely pathogenic"], [/likely\s+benign/i, "Likely benign"],
  [/pathogenic/i, "Pathogenic"], [/benign/i, "Benign"], [/uncertain|vus/i, "Uncertain significance"],
];

const codes = (cc) => (cc?.coding || []).map((c) => c.code);
const hasCode = (cc, code) => codes(cc).includes(code);
const comp = (obs, code) => (obs.component || []).find((c) => hasCode(c.code, code));

function significance(cc) {
  for (const c of cc?.coding || []) if (SIGNIFICANCE[c.code]) return SIGNIFICANCE[c.code];
  const text = cc?.text || cc?.coding?.[0]?.display || "";
  for (const [re, label] of TEXT_SIGNIFICANCE) if (re.test(text)) return label;
  return null;
}

function geneOf(obs) {
  const g = comp(obs, "48018-6")?.valueCodeableConcept;
  return (g?.coding?.[0]?.display || g?.text || "").trim().toUpperCase();
}

/** True if this looks like a FHIR resource we can read. */
export function isFhir(json) {
  return !!json && typeof json === "object" && ["Bundle", "DiagnosticReport"].includes(json.resourceType);
}

/**
 * @param {object} json   parsed FHIR JSON (Bundle or DiagnosticReport)
 * @param {string[]} panelGenes  genes this app covers
 */
export function parseFhir(json, panelGenes) {
  if (!isFhir(json)) throw new Error("not a FHIR Bundle or DiagnosticReport");
  const resources = json.resourceType === "Bundle"
    ? (json.entry || []).map((e) => e.resource).filter(Boolean)
    : [json, ...(json.contained || [])];
  const patient = resources.find((r) => r.resourceType === "Patient");
  const org = resources.find((r) => r.resourceType === "Organization");
  const report = resources.find((r) => r.resourceType === "DiagnosticReport");
  const sex = { female: "F", male: "M" }[patient?.gender] || "";
  const name = patient?.name?.[0]?.given?.[0] || "";
  const panel = new Set(panelGenes);
  const out = { lab: org?.name || report?.performer?.[0]?.display || "", name, sex,
                findings: [], notCovered: [], negative: [], format: "HL7 FHIR R4 (Genomics Reporting)" };
  const seen = new Set();
  for (const obs of resources.filter((r) => r.resourceType === "Observation" && hasCode(r.code, "69548-6"))) {
    const gene = geneOf(obs);
    if (!gene) continue;
    if (hasCode(obs.valueCodeableConcept, "LA9634-2")) {          // Absent: the person does not carry it
      if (panel.has(gene) && !out.negative.includes(gene)) out.negative.push(gene);
      continue;
    }
    const cls = significance(comp(obs, "53037-8")?.valueCodeableConcept);
    if (!cls || /benign/i.test(cls)) continue;                    // benign results are not findings
    if (!panel.has(gene)) { if (!out.notCovered.includes(gene)) out.notCovered.push(gene); continue; }
    const c = comp(obs, "48004-6")?.valueCodeableConcept;
    const p = comp(obs, "48005-3")?.valueCodeableConcept;
    const cText = c?.coding?.[0]?.display || c?.text || "";
    const pText = p?.coding?.[0]?.display || p?.text || "";
    const variant = [cText, pText && `(${pText})`].filter(Boolean).join(" ");
    const key = `${gene}|${variant}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.findings.push({ gene, variant, classification: cls });
  }
  return out;
}
