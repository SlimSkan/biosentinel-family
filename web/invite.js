// BioSentinel Family - the page a RELATIVE opens from a family invite.
// The link holds only a random id. This page never learns who sent it, and the
// relative's answers (relation, contact) stay here unless they choose to send them.

const T = {
  en: {
    hIntro: "A message about your family's health",
    intro: "Someone in your family who cares about you sent you this page. It is about a gene change that can run in families.",
    privacy: "This page does not say who sent it. The sender only sees how many people opened it and asked about next steps, never who, and never your answers below.",
    hRel: "How are you related to the person who sent this?",
    relations: {
      sibling: "Brother or sister", parent: "Mother or father", child: "Son or daughter",
      half_sibling: "Half-brother or half-sister", grandparent: "Grandparent", grandchild: "Grandchild",
      aunt_uncle: "Aunt or uncle", niece_nephew: "Niece or nephew", first_cousin: "First cousin",
      unsure: "I'm not sure / I'd rather not say",
    },
    pick: "Choose…",
    hExplain: "What this means for you", hNext: "What you can do",
    levels: { simple: "Simple words", standard: "Standard", detailed: "More detail" },
    rewrite: "Rewrite with Gemma 4", rewriting: "Gemma is writing…",
    srcTemplate: "Reviewed text", srcAi: "Gemma 4 · passed safety checks",
    aiRejected: "Gemma's text did not pass the safety checks, so the reviewed text is shown.",
    nextIntro: "You don't have to do anything. If you want to know whether you carry this change:",
    askDoctor: (g) => `Ask your doctor or a genetic counsellor about a carrier test for the ${g} gene. You can show them this page.`,
    wantCounsellor: "I'd like a genetic counsellor to contact me",
    contact: "How should the counsellor contact you?", send: "Send", sent: (id) => `Sent. Request number ${id}.`,
    notNow: "Not now", notNowDone: "That's fine. You can come back to this page at any time.",
    gone: "This invite was not found or has expired.",
    aiOff: "AI rewriting is switched off in this online demo; this is the reviewed text.",
  },
  ar: {
    hIntro: "رسالة عن صحة عائلتك",
    intro: "أرسل لك هذه الصفحة أحد أفراد عائلتك ممن يهتمون بك. وهي تتعلق بتغيّر جيني قد ينتقل في العائلات.",
    privacy: "لا تذكر هذه الصفحة من أرسلها. لا يرى المرسل إلا عدد من فتحوها وسألوا عن الخطوات التالية، وليس من هم، ولا يرى إجاباتك أدناه أبداً.",
    hRel: "ما صلة قرابتك بالشخص الذي أرسل هذه الصفحة؟",
    relations: {
      sibling: "أخ أو أخت", parent: "أم أو أب", child: "ابن أو ابنة",
      half_sibling: "أخ أو أخت غير شقيق", grandparent: "جد أو جدة", grandchild: "حفيد أو حفيدة",
      aunt_uncle: "عم أو عمة أو خال أو خالة", niece_nephew: "ابن أو ابنة الأخ أو الأخت", first_cousin: "ابن أو ابنة العم أو الخال",
      unsure: "لست متأكداً / أفضّل عدم القول",
    },
    pick: "اختر…",
    hExplain: "ماذا يعني هذا بالنسبة لك", hNext: "ما يمكنك فعله",
    levels: { simple: "كلمات بسيطة", standard: "عادي", detailed: "تفاصيل أكثر" },
    rewrite: "إعادة الصياغة بواسطة Gemma 4", rewriting: "يكتب Gemma…",
    srcTemplate: "نص تمت مراجعته", srcAi: "Gemma 4 · اجتاز فحوص السلامة",
    aiRejected: "لم يجتز نص Gemma فحوص السلامة، لذلك يُعرض النص الذي تمت مراجعته.",
    nextIntro: "لست مضطراً لفعل أي شيء. إن أردت أن تعرف إن كنت تحمل هذا التغيّر:",
    askDoctor: (g) => `اسأل طبيبك أو مستشاراً وراثياً عن فحص الحاملين لجين ${g}. يمكنك أن تريه هذه الصفحة.`,
    wantCounsellor: "أود أن يتواصل معي مستشار وراثي",
    contact: "كيف يتواصل معك المستشار؟", send: "إرسال", sent: (id) => `تم الإرسال. رقم الطلب ${id}.`,
    notNow: "ليس الآن", notNowDone: "لا بأس. يمكنك العودة إلى هذه الصفحة في أي وقت.",
    gone: "لم يتم العثور على هذه الدعوة أو انتهت صلاحيتها.",
    aiOff: "إعادة الصياغة بالذكاء الاصطناعي متوقفة في هذا العرض على الإنترنت، وهذا هو النص الذي تمت مراجعته.",
  },
};

const S = { id: new URLSearchParams(location.search).get("i"), lang: "en", level: "standard",
            invite: null, relation: "", result: null, stepCounted: false, ai: true };
const t = () => T[S.lang];
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const api = async (url, body) => {
  const r = await fetch(url, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error((await r.json()).detail || r.status);
  return r.json();
};

// Count "opened" once per browser, so reloading the page does not inflate it.
function countOpenOnce() {
  const k = `bsf-opened-${S.id}`;
  try { if (localStorage.getItem(k)) return; localStorage.setItem(k, "1"); } catch { /* private mode: count anyway */ }
  api(`/api/invites/${S.id}/event`, { event: "opened" });
}
function countNextStep() {
  if (S.stepCounted) return;
  S.stepCounted = true;
  api(`/api/invites/${S.id}/event`, { event: "next_step" });
}

function render() {
  document.documentElement.lang = S.lang;
  document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr";
  for (const k of ["hIntro", "intro", "privacy", "hRel", "hExplain", "hNext"])
    $(k.replace(/^h([A-Z])/, (_, c) => "h-" + c.toLowerCase())).textContent = t()[k];
  $("level").innerHTML = Object.entries(t().levels).map(([k, v]) => `<option value="${k}" ${k === S.level ? "selected" : ""}>${v}</option>`).join("");
  $("relation").innerHTML = `<option value="">${t().pick}</option>` + S.invite.relations
    .map((r) => `<option value="${r}" ${r === S.relation ? "selected" : ""}>${esc(t().relations[r])}</option>`).join("");
  renderExplain();
  renderNext();
}

async function loadExplain(ai = false) {
  if (!S.relation) return;
  S.result = await api(`/api/invites/${S.id}/explain`, { relation: S.relation, lang: S.lang, level: S.level, ai });
  $("s-explain").classList.remove("locked");
  $("s-next").classList.remove("locked");
  renderExplain();
  renderNext();
}

function renderExplain() {
  if (!S.result) return;
  const r = S.result;
  const rejected = r.source !== "ai" && r.problems?.some((p) => !p.startsWith("ai unavailable"));
  const badge = r.source === "ai" ? `<span class="badge ai">${t().srcAi}</span>`
    : `<span class="badge">${t().srcTemplate}</span>` + (rejected ? `<div class="small">${t().aiRejected}</div>` : "");
  $("explain").innerHTML = `<div class="card"><h3>${esc(S.invite.condition[S.lang])}</h3>
    <p>${esc(r.text)}</p><div class="row">${badge} ${S.ai ? `<button class="secondary" id="ai">${t().rewrite}</button>` : `<span class="small">${t().aiOff}</span>`}</div></div>`;
  if (S.ai) $("ai").onclick = (e) => { e.target.disabled = true; e.target.textContent = t().rewriting; loadExplain(true); };
}

function renderNext() {
  if (!S.result) return;
  $("next").innerHTML = `<p>${esc(t().nextIntro)}</p><div class="card">${esc(t().askDoctor(S.invite.gene))}</div>
    <div class="row"><button id="want">${t().wantCounsellor}</button><button class="secondary" id="later">${t().notNow}</button></div>
    <div id="next-out"></div>`;
  $("later").onclick = () => ($("next-out").innerHTML = `<p>${esc(t().notNowDone)}</p>`);
  $("want").onclick = () => {
    countNextStep();
    $("next-out").innerHTML = `<label>${t().contact}<input type="text" id="contact"></label><button id="send">${t().send}</button><div id="sent"></div>`;
    $("send").onclick = async () => {
      // The counsellor sees: one gene, that it came from a family invite, language and contact. No relation.
      const { id } = await api("/api/cases", { shared_genes: [], other_reasons: [`family invite: ${S.invite.gene}`],
        language: S.lang, contact: $("contact").value });
      $("sent").innerHTML = `<p class="ok">${esc(t().sent(id))}</p>`;
      $("send").disabled = true;
    };
  };
}

$("lang").onchange = (e) => { S.lang = e.target.value; render(); loadExplain(); };
$("level").onchange = (e) => { S.level = e.target.value; loadExplain(); };
$("relation").onchange = (e) => { S.relation = e.target.value; loadExplain(); };

(async () => {
  try {
    S.invite = await api(`/api/invites/${S.id}`);
  } catch {
    document.querySelector("main").innerHTML = `<section><p>${T.en.gone}</p><p dir="rtl">${T.ar.gone}</p></section>`;
    return;
  }
  S.ai = await api("/api/health").then((h) => h.ai.reachable).catch(() => false);
  if (navigator.language?.startsWith("ar")) { S.lang = "ar"; $("lang").value = "ar"; }
  countOpenOnce();
  render();
})();
