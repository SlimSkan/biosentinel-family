// What goes into the private match (PSI), and how to read its result. No browser code: tested in Node.
//
// Two kinds of item, compared in ONE private set intersection:
//   "HBB"            the gene     -> reveals genes both partners carry
//   "HBB|c.20A>T"    the variant  -> reveals, for a shared gene, whether it is the SAME change
// A variant that differs is never revealed to the other partner (it simply does not match).
//
// Clinical safety rule: a variant of uncertain significance (VUS), or anything benign, is NEVER
// put in the match, so it can never create a couple risk or an alert.

const COUNTED = new Set(["Pathogenic", "Likely pathogenic"]);

/** Normalised variant id: the c.HGVS change if present (e.g. "c.20A>T"), else the lower-cased text. */
export function variantKey(text) {
  const t = String(text || "").trim();
  const c = t.match(/c\.[^\s(),;]+/i);
  if (c) return c[0].replace(/^C\./, "c.");
  return t.toLowerCase().replace(/\s+/g, " ");
}

/** Items for the PSI from one person's variants [{gene, variant, classification}]. */
export function psiItems(variants) {
  const items = new Set();
  for (const v of variants || []) {
    if (!COUNTED.has(v.classification)) continue;          // VUS / benign: never matched
    items.add(v.gene);
    const k = variantKey(v.variant);
    if (k) items.add(`${v.gene}|${k}`);
  }
  return [...items];
}

/** Read the intersection: {shared: genes both carry, sameVariant: shared genes with the identical change}. */
export function readMatch(sharedItems) {
  const genes = sharedItems.filter((x) => !x.includes("|"));
  const same = new Set(sharedItems.filter((x) => x.includes("|")).map((x) => x.split("|")[0]));
  return { shared: genes.sort(), sameVariant: genes.filter((g) => same.has(g)).sort() };
}
