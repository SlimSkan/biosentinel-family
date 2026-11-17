// Shows a pre-consultation brief (from /api/brief). Used by the person's preview and by the
// counsellor console, so both see exactly the same thing. The brief is in English (clinical).

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const list = (xs) => `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;

export function renderBrief(b, extra = {}) {
  const rows = [
    ["Reason for referral", list(b.reasons)],
    b.risks.length && ["Risk figures (genetics rules)", list(b.risks)],
    ["Understanding", esc(b.understanding)],
    b.picks.length && ["Wants to discuss", esc(b.picks.join("; "))],
    b.feeling && ["Self-reported feeling", esc(b.feeling)],
    b.family.length && ["Family (relationships only)", list(b.family)],
    extra.contact && ["Contact", esc(extra.contact)],
    extra.note && ["Message", esc(extra.note)],
  ].filter(Boolean);
  const src = b.summary_source === "ai"
    ? `<span class="badge ai">Gemma 4 · every sentence cites a fact</span>`
    : `<span class="badge">Written by rules</span>`;
  return `<div class="brief">
    <div class="row"><strong>Pre-consultation brief</strong>
      <span class="badge ${b.priority === "urgent" ? "urgent" : ""}">${b.priority === "urgent" ? "Time-sensitive: current pregnancy" : "Routine"}</span></div>
    <table class="imp">${rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join("")}</table>
    <p><strong>Summary for the specialist</strong> ${src}</p><p>${esc(b.summary)}</p>
    <details><summary>Sources: the numbered facts behind the summary</summary><ul>${b.facts.map((f) =>
      `<li${b.summary_sources.includes(f.id) ? ' class="cited"' : ""}><span class="meta">${f.id}</span> ${esc(f.text)}</li>`).join("")}</ul></details>
    <p><strong>Suggested agenda</strong></p>${list(b.agenda)}
    <p class="small">${esc(b.disclaimer)}</p></div>`;
}
