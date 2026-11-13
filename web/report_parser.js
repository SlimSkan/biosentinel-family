// BioSentinel Family - reads the findings out of a lab report's TEXT, with fixed rules (no AI).
//
// Why rules and not AI: a missed or invented gene would change a couple's risk. Rules are
// predictable and testable, and the person always checks the result before it is used.
// This file has no browser code, so the tests can run it in Node.

// Order matters: "Likely pathogenic" must be matched before "Pathogenic".
const CLASSES = [
  [/likely\s+pathogenic/i, "Likely pathogenic"],
  [/pathogenic/i, "Pathogenic"],
  [/uncertain\s+significance|\bVUS\b/i, "Uncertain significance"],
];
const BENIGN = /\b(likely\s+)?benign\b/i;
// Lines that NAME genes the person does not carry, e.g. "No pathogenic variants detected in: CFTR".
const NEGATIVE = /\bno\s+(likely\s+)?(pathogenic\s+)?variants?\b|\bnot\s+detected\b|\bnegative\b/i;
// Variant notation: c.20A>T (p.Glu7Val), p.Phe508del, "Exon 7 deletion (1 copy)", or a described variant.
const VARIANT = /(c\.[^\s,;]+(?:\s*\([^)]*\))?|p\.\(?[A-Za-z0-9_*]+\)?|exon\s+\d+\s+(?:deletion|duplication)(?:\s*\([^)]*\))?)/i;

/**
 * @param {string} text   the report text, one line per row (see report_reader.js)
 * @param {string[]} panel gene symbols this app covers, e.g. ["HBB", "CFTR", ...]
 * @returns {{lab, name, sex, findings: {gene, variant, classification}[], notCovered: string[], negative: string[]}}
 */
export function parseReportText(text, panel) {
  const lines = text.split(/\r?\n/).map((l) => l.replace(/\s+/g, " ").trim()).filter(Boolean);
  const out = { lab: lines[0] || "", name: "", sex: "", findings: [], notCovered: [], negative: [] };
  const genePattern = new RegExp(`\\b(${panel.join("|")})\\b`, "g");

  for (const line of lines) {
    const sex = line.match(/\b(?:sex|gender)\s*[:\-]\s*(female|male|f|m)\b/i);
    if (sex && !out.sex) out.sex = sex[1][0].toUpperCase();
    const name = line.match(/\bname\s*:\s*(.+?)(?=\s+(?:sex|gender|date of birth|dob)\b|$)/i);
    if (name && !out.name) out.name = name[1].replace(/\(demo\)/i, "").trim();

    const genes = [...new Set(line.match(genePattern) || [])];
    if (NEGATIVE.test(line)) { out.negative.push(...genes); continue; }   // named, but NOT carried
    if (BENIGN.test(line)) continue;                                       // benign: nothing to report

    const cls = CLASSES.find(([re]) => re.test(line));
    if (!cls) continue;                                   // no classification on this line: not a result row
    const variant = (line.match(VARIANT) || [])[1] || "";

    if (genes.length === 1) {
      const gene = genes[0];
      if (!out.findings.some((f) => f.gene === gene)) out.findings.push({ gene, variant, classification: cls[1] });
    } else if (genes.length === 0) {
      // A result row for a gene this app does not cover: show it, never drop it silently.
      const g = line.match(/^([A-Z][A-Z0-9]{1,9})\b/);
      if (g && !/^(RESULTS?|GENE|NAME|SEX|PANEL)$/.test(g[1])) out.notCovered.push(g[1]);
    }
    // Two panel genes on one result line is ambiguous: skip it (the person sees the paper report).
  }
  out.negative = [...new Set(out.negative)];
  return out;
}
