// Genetic risk simulator: turns "25% per pregnancy" into something you can see.
// A Punnett square (one copy from each parent), random pregnancies drawn one at a time or 100 at
// once, a tally against the expected shares, and a teach-back question about independence.
// The expected shares are the Mendelian rules used by app/risk_engine.py; the draws are only an
// illustration (labelled as such), never a prediction for a real baby.

const L = {
  en: {
    title: "See how it is passed on", one: "Simulate a pregnancy", hundred: "Simulate 100 pregnancies", reset: "Reset",
    note: "A simulation to show chance, not a prediction. Each pregnancy is a new draw, like tossing two coins: the chance stays the same whatever happened before.",
    usual: "usual copy", changed: "changed copy", parentA: "Partner A", parentB: "Partner B", mother: "Mother", father: "Father",
    ar: { affected: "Affected (two changed copies)", carrier: "Healthy carrier (one changed copy)", neither: "Not a carrier" },
    xl: { sonAff: "Son, affected", sonOk: "Son, not affected", dauCar: "Daughter, carrier", dauOk: "Daughter, not a carrier" },
    expected: "expected", simulated: "simulated", last: "This pregnancy:",
    q: "Your first child has the condition. What is the chance for the next pregnancy?",
    qOpts: ["25%, the same as before", "0%: it already happened once", "50%", "100%"],
    qRight: "Right: each pregnancy is independent, so the chance stays 25%.",
    qWrong: "Not quite: each pregnancy is a new draw, so the chance stays 25%, whatever happened before.",
    xlNote: "X-linked: the father's result does not change these chances.",
  },
  ar: {
    title: "شاهد كيف تنتقل الصفة", one: "محاكاة حمل واحد", hundred: "محاكاة 100 حمل", reset: "إعادة",
    note: "محاكاة لتوضيح الاحتمال وليست تنبؤاً. كل حمل سحب جديد، مثل رمي قطعتين نقديتين: يبقى الاحتمال نفسه مهما حدث من قبل.",
    usual: "نسخة عادية", changed: "نسخة متغيّرة", parentA: "الشريك الأول", parentB: "الشريك الثاني", mother: "الأم", father: "الأب",
    ar: { affected: "مصاب (نسختان متغيّرتان)", carrier: "حامل سليم (نسخة متغيّرة واحدة)", neither: "غير حامل" },
    xl: { sonAff: "ابن مصاب", sonOk: "ابن غير مصاب", dauCar: "ابنة حاملة", dauOk: "ابنة غير حاملة" },
    expected: "المتوقع", simulated: "المحاكاة", last: "هذا الحمل:",
    q: "طفلكما الأول مصاب بالحالة. ما احتمال الإصابة في الحمل التالي؟",
    qOpts: ["25%، كما في السابق", "0%: فقد حدث ذلك مرة", "50%", "100%"],
    qRight: "صحيح: كل حمل مستقل، لذلك يبقى الاحتمال 25%.",
    qWrong: "ليس تماماً: كل حمل سحب جديد، لذلك يبقى الاحتمال 25% مهما حدث من قبل.",
    xlNote: "مرتبط بالكروموسوم X: نتيجة الأب لا تغيّر هذه الاحتمالات.",
  },
};

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const coin = () => (globalThis.crypto.getRandomValues(new Uint8Array(1))[0] & 1);   // fair 0/1

/** One random pregnancy. AR: carrier x carrier. XL: carrier mother x unaffected father. */
export function draw(kind) {
  const a = coin(), b = coin();                       // 1 = the changed copy (AR) / the changed X (mother)
  if (kind === "AR") return a + b === 2 ? "affected" : a + b === 1 ? "carrier" : "neither";
  const son = coin() === 1;                           // father gives Y (son) or X (daughter)
  return son ? (a ? "sonAff" : "sonOk") : (a ? "dauCar" : "dauOk");
}

/** Expected shares (%), from the Mendelian rules. */
export const EXPECTED = {
  AR: { affected: 25, carrier: 50, neither: 25 },
  XL: { sonAff: 25, sonOk: 25, dauCar: 25, dauOk: 25 },      // of all pregnancies; = 50% of sons / daughters
};

function square(kind, t, last) {
  const cell = (cls, label) => `<td class="sq ${cls} ${last === cls ? "hit" : ""}">${esc(label)}</td>`;
  if (kind === "AR") {
    return `<table class="punnett"><tr><th></th><th>${t.parentB}: <b>A</b></th><th>${t.parentB}: <b class="chg">a</b></th></tr>
      <tr><th>${t.parentA}: <b>A</b></th>${cell("neither", "AA · " + t.ar.neither)}${cell("carrier", "Aa · " + t.ar.carrier)}</tr>
      <tr><th>${t.parentA}: <b class="chg">a</b></th>${cell("carrier", "aA · " + t.ar.carrier)}${cell("affected", "aa · " + t.ar.affected)}</tr></table>
      <p class="small"><b>A</b> = ${t.usual} · <b class="chg">a</b> = ${t.changed}</p>`;
  }
  return `<table class="punnett"><tr><th></th><th>${t.father}: <b>X</b></th><th>${t.father}: <b>Y</b></th></tr>
    <tr><th>${t.mother}: <b class="chg">X*</b></th>${cell("dauCar", t.xl.dauCar)}${cell("sonAff", t.xl.sonAff)}</tr>
    <tr><th>${t.mother}: <b>X</b></th>${cell("dauOk", t.xl.dauOk)}${cell("sonOk", t.xl.sonOk)}</tr></table>
    <p class="small"><b class="chg">X*</b> = ${t.changed} · ${t.xlNote}</p>`;
}

// scenarios: [{id, gene, kind: "AR" | "XL"}]; state: {tab, tally: {id: {...}}, last: {id: outcome}, answer}
export function renderSimulator(el, { lang, scenarios, state, onAnswer }) {
  if (!scenarios.length) { el.innerHTML = ""; return; }
  const t = L[lang];
  state.tab = scenarios.some((s) => s.id === state.tab) ? state.tab : scenarios[0].id;
  state.tally = state.tally || {}; state.last = state.last || {};
  const sc = scenarios.find((s) => s.id === state.tab);
  const tally = state.tally[sc.id] = state.tally[sc.id] || {};
  const total = Object.values(tally).reduce((a, b) => a + b, 0);
  const labels = sc.kind === "AR" ? t.ar : t.xl;
  const bars = Object.keys(EXPECTED[sc.kind]).map((k) => {
    const pct = total ? Math.round(100 * (tally[k] || 0) / total) : 0;
    return `<div class="bar"><span class="bl">${esc(labels[k])}</span>
      <span class="bt"><span class="bf ${k}" style="width:${pct}%"></span><span class="be" style="left:${EXPECTED[sc.kind][k]}%"></span></span>
      <span class="bn">${tally[k] || 0} · ${pct}% <span class="small">(${t.expected} ${EXPECTED[sc.kind][k]}%)</span></span></div>`;
  }).join("");
  const last = state.last[sc.id];
  el.innerHTML = `<h3>${t.title}</h3>
    ${scenarios.length > 1 ? `<div class="row">${scenarios.map((s) => `<button class="${s.id === sc.id ? "" : "secondary"}" data-sim="${s.id}">${s.gene}</button>`).join("")}</div>` : ""}
    ${square(sc.kind, t, last)}
    <div class="row"><button id="sim-one">${t.one}</button><button class="secondary" id="sim-100">${t.hundred}</button>
      <button class="secondary" id="sim-reset">${t.reset}</button></div>
    ${last ? `<p><strong>${t.last}</strong> ${esc(labels[last])}</p>` : ""}
    <div class="bars">${bars}</div>
    <p class="small">${esc(t.note)}</p>
    ${sc.kind === "AR" ? `<div class="card simq"><p><strong>${esc(t.q)}</strong></p>
      ${t.qOpts.map((o, i) => `<label><input type="radio" name="simq" value="${i}" ${state.answer === i ? "checked" : ""}> ${esc(o)}</label>`).join("")}
      ${state.answer === undefined ? "" : `<p class="${state.answer === 0 ? "ok" : "flag"}">${esc(state.answer === 0 ? t.qRight : t.qWrong)}</p>`}</div>` : ""}`;
  const rerender = () => renderSimulator(el, arguments[1]);
  el.querySelectorAll("[data-sim]").forEach((b) => (b.onclick = () => { state.tab = b.dataset.sim; rerender(); }));
  el.querySelector("#sim-one").onclick = () => { const o = draw(sc.kind); tally[o] = (tally[o] || 0) + 1; state.last[sc.id] = o; rerender(); };
  el.querySelector("#sim-100").onclick = () => { let o; for (let i = 0; i < 100; i++) { o = draw(sc.kind); tally[o] = (tally[o] || 0) + 1; } state.last[sc.id] = o; rerender(); };
  el.querySelector("#sim-reset").onclick = () => { state.tally[sc.id] = {}; delete state.last[sc.id]; rerender(); };
  el.querySelectorAll("input[name=simq]").forEach((r) => (r.onchange = () => { state.answer = +r.value; onAnswer?.(state.answer === 0); rerender(); }));
}
