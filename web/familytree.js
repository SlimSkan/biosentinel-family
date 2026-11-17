// Interactive family-tree carrier map. The chances come from the server's genetics rules
// (/api/family-map); this file only draws them and lets the person mark relatives as tested.
// Relationships only: no names are ever entered or stored. Everything stays in page memory.

const POS = {   // x, y in a 640 x 420 drawing
  pgf: [50, 45], pgm: [150, 45], mgf: [490, 45], mgm: [590, 45],
  p_uncle: [50, 155], father: [230, 155], mother: [410, 155], m_aunt: [590, 155],
  p_cousin: [50, 265], brother: [180, 265], me: [320, 265], sister: [460, 265], m_cousin: [590, 265],
  nephew: [180, 370], son: [280, 370], daughter: [360, 370], niece: [460, 370],
};
const SEX = { pgf: "M", pgm: "F", mgf: "M", mgm: "F", p_uncle: "M", father: "M", mother: "F", m_aunt: "F",
  p_cousin: "F", brother: "M", sister: "F", m_cousin: "M", nephew: "M", son: "M", daughter: "F", niece: "F" };

const L = {
  en: {
    title: "Family carrier map", gene: "Gene",
    intro: "Each relative's chance of carrying the same change, from the rules of inheritance. Tap a relative to see why, or to mark them as tested. No names are used, and nothing is saved.",
    fside: "Father's side", mside: "Mother's side",
    rel: { pgf: "Grandfather", pgm: "Grandmother", mgf: "Grandfather", mgm: "Grandmother", p_uncle: "Uncle", father: "Father",
      mother: "Mother", m_aunt: "Aunt", p_cousin: "Cousin", brother: "Brother", me: "You", sister: "Sister", m_cousin: "Cousin",
      nephew: "Nephew", son: "Son", daughter: "Daughter", niece: "Niece" },
    basis: {
      self: () => "Your own result shows this change.",
      first_degree: (p) => `You share about half of your genes, so the chance is about ${p}%.`,
      second_degree: (p) => `Two steps of relationship: the chance halves at each step, so about ${p}%.`,
      third_degree: (p) => `Three steps of relationship: about ${p}%.`,
      origin_side: (p) => `A test you marked shows the change came from this side of the family: about ${p}%.`,
      other_side: () => "A test you marked shows the change did not come from this side: 0% for this change (the usual population chance still applies).",
      tested_carrier: () => "Marked as tested: carries the change.",
      tested_not_carrier: () => "Marked as tested: does not carry the change.",
      via_tested: (p) => `Follows from a parent you marked as tested: about ${p}%.`,
      xl_son: () => "X-linked: each son has a 50% chance of being affected.",
      xl_daughter: () => "X-linked: each daughter has a 50% chance of being a carrier.",
      xl_side: () => "X-linked: this depends on which side of the family the change comes from, and on sex. A genetic counsellor can work it out.",
    },
    status: "Tested?", unknown: "Not known", carrier: "Tested: carries it", not_carrier: "Tested: does not carry it",
    invite: "Send a private invite", summary: (c) => `Relatives in this map who may carry it: ${c}.`,
    childNote: "Son and daughter: future children. For carrier status of children, both parents' results matter.",
    legend: "Darker = higher chance. ? = a counsellor can work it out.",
  },
  ar: {
    title: "خريطة الحاملين في العائلة", gene: "الجين",
    intro: "احتمال أن يحمل كل قريب التغيّر نفسه، وفق قواعد الوراثة. اضغط على أحد الأقارب لترى السبب أو لتحدد أنه أجرى الفحص. لا تُستخدم أي أسماء، ولا يُحفظ أي شيء.",
    fside: "جهة الأب", mside: "جهة الأم",
    rel: { pgf: "الجد", pgm: "الجدة", mgf: "الجد", mgm: "الجدة", p_uncle: "العم", father: "الأب", mother: "الأم",
      m_aunt: "الخالة", p_cousin: "ابنة العم", brother: "الأخ", me: "أنت", sister: "الأخت", m_cousin: "ابن الخالة",
      nephew: "ابن الأخ", son: "الابن", daughter: "الابنة", niece: "ابنة الأخت" },
    basis: {
      self: () => "نتيجتك تُظهر هذا التغيّر.",
      first_degree: (p) => `تتشاركان نحو نصف الجينات، لذلك الاحتمال نحو ${p}%.`,
      second_degree: (p) => `درجتان من القرابة: يتناقص الاحتمال إلى النصف مع كل درجة، أي نحو ${p}%.`,
      third_degree: (p) => `ثلاث درجات من القرابة: نحو ${p}%.`,
      origin_side: (p) => `يُظهر فحص حددته أن التغيّر جاء من هذه الجهة من العائلة: نحو ${p}%.`,
      other_side: () => "يُظهر فحص حددته أن التغيّر لم يأتِ من هذه الجهة: 0% لهذا التغيّر (ويبقى الاحتمال المعتاد لدى عامة الناس).",
      tested_carrier: () => "أجرى الفحص: يحمل التغيّر.",
      tested_not_carrier: () => "أجرى الفحص: لا يحمل التغيّر.",
      via_tested: (p) => `يتبع أحد الوالدين الذي حددت أنه أجرى الفحص: نحو ${p}%.`,
      xl_son: () => "مرتبط بالكروموسوم X: لدى كل ابن احتمال 50% أن يتأثر.",
      xl_daughter: () => "مرتبط بالكروموسوم X: لدى كل ابنة احتمال 50% أن تحمل الصفة.",
      xl_side: () => "مرتبط بالكروموسوم X: يعتمد ذلك على جهة العائلة التي جاء منها التغيّر وعلى الجنس. يمكن لمستشار وراثي تحديد ذلك.",
    },
    status: "هل أجرى الفحص؟", unknown: "غير معروف", carrier: "أجرى الفحص: يحمله", not_carrier: "أجرى الفحص: لا يحمله",
    invite: "أرسل دعوة خاصة", summary: (c) => `الأقارب في هذه الخريطة الذين قد يحملونه: ${c}.`,
    childNote: "الابن والابنة: أطفال المستقبل. بالنسبة لحمل الأطفال للصفة، تهم نتيجتا الوالدين معاً.",
    legend: "اللون الأغمق = احتمال أعلى. ؟ = يمكن لمستشار تحديد ذلك.",
  },
};

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fill = (pct) => pct === null ? "#e6e1db" : pct >= 100 ? "#1f6f6b" : pct >= 50 ? "#5fa39d" : pct >= 25 ? "#a8cfcb" : pct > 0 ? "#d5e8e6" : "#ffffff";

function lines() {
  const P = POS, l = [];
  const couple = (a, b, kids, drop) => {
    const [ax, y] = P[a], [bx] = P[b], mx = (ax + bx) / 2;
    l.push(`M${ax + 16},${y} H${bx - 16}`, `M${mx},${y} V${drop}`);
    const xs = kids.map((k) => P[k][0]);
    l.push(`M${Math.min(...xs, mx)},${drop} H${Math.max(...xs, mx)}`);
    kids.forEach((k) => l.push(`M${P[k][0]},${drop} V${P[k][1] - 18}`));
  };
  couple("pgf", "pgm", ["p_uncle", "father"], 100);
  couple("mgf", "mgm", ["mother", "m_aunt"], 100);
  couple("father", "mother", ["brother", "me", "sister"], 212);
  l.push(`M${P.p_uncle[0]},${P.p_uncle[1] + 52} V${P.p_cousin[1] - 18}`, `M${P.m_aunt[0]},${P.m_aunt[1] + 52} V${P.m_cousin[1] - 18}`);
  l.push(`M${P.brother[0]},${P.brother[1] + 52} V${P.nephew[1] - 18}`, `M${P.sister[0]},${P.sister[1] + 52} V${P.niece[1] - 18}`);
  l.push(`M${P.me[0]},${P.me[1] + 52} V322 M${P.son[0]},322 H${P.daughter[0]} M${P.son[0]},322 V${P.son[1] - 18} M${P.daughter[0]},322 V${P.daughter[1] - 18}`);
  return l.join(" ");
}

function shape(id, pct, mySex, selected) {
  const [x, y] = POS[id];
  const sex = id === "me" ? mySex : SEX[id];
  const style = `fill="${fill(pct)}" stroke="${selected ? "#e0a43a" : "#3a302c"}" stroke-width="${selected || id === "me" ? 3 : 1.4}"`;
  const body = sex === "M" ? `<rect x="${x - 16}" y="${y - 16}" width="32" height="32" rx="3" ${style}/>`
                           : `<circle cx="${x}" cy="${y}" r="17" ${style}/>`;
  const q = pct === null ? `<text x="${x}" y="${y + 5}" text-anchor="middle" font-size="15" fill="#6e5d56">?</text>` : "";
  return body + q;
}

// state: { gene, tested: {id: "carrier"|"not_carrier"}, sel }
export async function renderTree(el, { lang, genes, sex, api, state, onInvite, onChange }) {
  const t = L[lang];
  state.gene = genes.includes(state.gene) ? state.gene : genes[0];
  state.tested = state.tested || {};
  const map = await api("/api/family-map", { gene: state.gene, sex, tested: state.tested });
  const by = Object.fromEntries(map.nodes.map((n) => [n.id, n]));
  const pctText = (id) => (by[id].pct === null || id === "me" ? "" : `${by[id].pct}%`);
  const counts = {};
  map.nodes.filter((n) => n.id !== "me" && n.pct > 0 && n.pct < 100).forEach((n) => (counts[n.pct] = (counts[n.pct] || 0) + 1));
  const summary = Object.keys(counts).sort((a, b) => b - a).map((p) => `${counts[p]} × ${p}%`).join(", ");
  const sel = state.sel && by[state.sel] ? state.sel : null;
  const panel = sel ? `<div class="card tree-panel"><h3>${t.rel[sel]}${by[sel].pct === null ? "" : ` · ${by[sel].pct}%`}</h3>
      <p>${esc(t.basis[by[sel].basis](by[sel].pct))}</p>
      ${sel === "me" ? "" : `<label>${t.status} <select id="tree-status">
        ${["", "carrier", "not_carrier"].map((v) => `<option value="${v}" ${(state.tested[sel] || "") === v ? "selected" : ""}>${v ? t[v] : t.unknown}</option>`).join("")}
      </select></label>
      ${["son", "daughter"].includes(sel) ? "" : `<button class="secondary" id="tree-invite">${t.invite}</button>`}`}</div>` : "";
  el.innerHTML = `<h3>${t.title}</h3><p class="small">${esc(t.intro)}</p>
    ${genes.length > 1 ? `<div class="row">${genes.map((g) => `<button class="${g === state.gene ? "" : "secondary"}" data-gene="${g}">${g}</button>`).join("")}</div>` : ""}
    <div class="tree-wrap"><svg viewBox="0 0 640 420" class="tree" role="img" aria-label="${t.title}" dir="ltr">
      <text x="100" y="14" text-anchor="middle" class="side">${t.fside}</text>
      <text x="540" y="14" text-anchor="middle" class="side">${t.mside}</text>
      <path d="${lines()}" stroke="#8a7d76" stroke-width="1.4" fill="none"/>
      ${Object.keys(POS).map((id) => `<g class="node" data-node="${id}" tabindex="0">${shape(id, by[id].pct, sex, id === sel)}
        <text x="${POS[id][0]}" y="${POS[id][1] + 33}" text-anchor="middle" class="lbl">${esc(t.rel[id])}</text>
        <text x="${POS[id][0]}" y="${POS[id][1] + 47}" text-anchor="middle" class="pct">${pctText(id)}</text></g>`).join("")}
    </svg></div>
    <p class="small">${esc(t.legend)} ${summary ? esc(t.summary(summary)) : ""}</p>
    <p class="small">${esc(t.childNote)}</p>${panel}`;
  el.querySelectorAll("[data-node]").forEach((g) => {
    const pick = () => { state.sel = g.dataset.node; renderTree(el, arguments[1]); };
    g.onclick = pick; g.onkeydown = (e) => { if (e.key === "Enter") pick(); };
  });
  el.querySelectorAll("[data-gene]").forEach((b) => (b.onclick = () => { state.gene = b.dataset.gene; state.tested = {}; state.sel = null; renderTree(el, arguments[1]); onChange?.(); }));
  const st = el.querySelector("#tree-status");
  if (st) st.onchange = () => {
    if (st.value) state.tested[sel] = st.value; else delete state.tested[sel];
    renderTree(el, arguments[1]); onChange?.();
  };
  const inv = el.querySelector("#tree-invite");
  if (inv) inv.onclick = () => onInvite?.(state.gene);
}

// A short, name-free description for the counsellor brief (always in English: the brief is clinical).
export function treeSummary(state, lang = "en") {
  const t = L.en;
  const said = { carrier: "carries it (tested)", not_carrier: "does not carry it (tested)" };
  const marked = Object.entries(state.tested || {}).map(([id, v]) => `${t.rel[id].toLowerCase()} ${said[v]}`);
  return marked.length ? `${state.gene}: ${marked.join("; ")}` : "";
}
