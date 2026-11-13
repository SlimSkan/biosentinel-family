// BioSentinel Family - the partner's app (runs in the phone's browser).
// Flow: 1 my result -> 2 quick check -> 3 private match -> 4 our result -> 5 counsellor
//       6 help my family (optional, opens after the quick check)
import { PSI } from "./psi.js";
import { pdfToText } from "./report_reader.js";
import { parseReportText } from "./report_parser.js";

// ------------------------------------------------------------------ text (EN / AR)
const T = {
  en: {
    s1: "1. My result", s2: "2. Quick check", s3: "3. Compare privately with my partner",
    s4: "4. Our result", s5: "5. Talk to a genetic counsellor",
    levels: { simple: "Simple words", standard: "Standard", detailed: "More detail" },
    hello: (n) => `Hello ${n}. This is your own result. Nobody else can see it.`,
    lab: "From", rewrite: "Rewrite with Gemma 4", rewriting: "Gemma is writing… (this can take a minute on a laptop)",
    srcTemplate: "Reviewed text", srcAi: "Gemma 4 · passed safety checks",
    aiRejected: "Gemma's text did not pass the safety checks, so the reviewed text is shown.",
    escRequired: "Please talk to a genetic counsellor about this result.",
    escRecommended: "A genetic counsellor can help you understand this result.",
    quizQ: [
      ["Being a carrier means…", ["I am healthy and can pass the change on", "I have the disease", "I will get the disease later"], 0],
      ["For most conditions, does my result alone tell me if my children will be affected?", ["No, it also depends on my partner's result", "Yes, my result alone decides it"], 0],
      ["Who decides what to do next?", ["We do, with a counsellor's support if we want", "The app decides", "The doctor decides for us"], 0],
    ],
    check: "Check my answers", quizGood: "All correct. You can continue.",
    quizSimpler: (n) => `${n} of 3 correct. We switched to simpler explanations above, and here are the right answers:`,
    consent: "I agree to compare privately. Only genes we BOTH carry will be shown, to both of us. Nothing else is revealed.",
    start: "Start and get a code", join: "Join with my partner's code", codePh: "Partner's code",
    shareCode: "Give this code to your partner:", waiting: "Waiting for your partner…",
    shareCodeWa: "Send the code by WhatsApp",
    impTitle: "Import my lab report",
    impIntro: "Choose the PDF report you received from the screening lab. We read the results from it, then you check them before anything is explained.",
    impPrivacy: "Your PDF is read on this phone. It is not uploaded or stored anywhere.",
    impChoose: "Choose a PDF report", impReading: "Reading your report on this phone…",
    impNoReport: "No report at hand? Try a fictional one:",
    impCheck: "This is what we read from your report. Please check it against your paper report.",
    impLab: "Lab", impName: "Name", impSex: "Sex", impFemale: "Female", impMale: "Male", impPickSex: "Choose…",
    impCols: ["Use", "Gene", "Variant", "Classification"],
    impNegative: (g) => `Listed as not carried: ${g}.`,
    impNotCovered: (g) => `Also in your report but not covered by this app: ${g}. Please ask a genetic counsellor about these.`,
    impNone: "We could not find any results in this file. Is it a text PDF from a lab? (Photos and scanned pages are not supported yet.)",
    impNoFindings: "The report lists no carrier results for the genes this app covers.",
    impConfirmBox: "I checked these results against my paper report.",
    impNeedSex: "Choose your sex first: it changes what some results mean.",
    impContinue: "Continue with these results", impAgain: "Choose another file",
    impError: "This file could not be read. Is it a PDF?",
    you: "you", yourPdf: "Your PDF report",
    matchMsg: (c) => `Let's compare our screening results privately in BioSentinel Family. Only a gene we both carry will be shown, nothing else. My code: ${c}`,
    codeReceived: "Your partner sent you a code. Read the consent text, tick the box, then press Join.",
    working: "Comparing privately…", done: "Done.",
    sharedNone: "No shared genes on this panel.", sharedSome: (g) => `Shared gene(s): ${g}`,
    legend: ["Affected", "Healthy carrier", "Not a carrier"], perPregnancy: "Each pregnancy (16 dots = 16 equal chances)",
    optionsTitle: "Options (listed in no particular order — the choice is yours)",
    options: [
      ["Genetic counselling", "Talk through the result, feelings and choices with a qualified counsellor."],
      ["Confirmatory testing", "Repeat or extend testing to confirm the result."],
      ["Preconception options", "For example IVF with genetic testing of embryos (PGT-M)."],
      ["Testing during pregnancy", "Tests that can show whether a baby is affected."],
      ["No further action", "Some couples choose to continue without further steps."],
    ],
    feeling: "How are you feeling about these results?", feelings: ["Calm", "Unsure", "Worried"],
    shareWhat: "Choose what the counsellor will see:", shareShared: "Our shared gene(s)",
    shareMine: "My findings that need a counsellor", shareQuiz: "My quick-check score",
    contact: "How should the counsellor contact you? (optional)", note: "Message (optional)",
    preview: "The counsellor will see exactly this:", send: "Send to counsellor",
    sent: (id) => `Sent. Case number ${id}. A counsellor will contact you.`,
    recRequired: "We strongly recommend talking with a genetic counsellor.",
    recOptional: "Talking with a counsellor is your choice.",
    aiOff: "AI rewriting (Gemma 4) is switched off in this online demo, so the reviewed texts are shown. Every other feature works.",
    s6: "6. Help my family (optional)",
    famIntro: "Brothers, sisters, cousins and other relatives can carry the same change without knowing it. You can send them a private page that explains it.",
    famPrivacy: "The page does not include your name or any of your other results. Your relative chooses whether to read it, and you will only see how many people opened it, never who.",
    famNone: "None of your results needs a family invite. Uncertain results are not shared with family.",
    famCreate: "Create invite", famLink: "Private link:", famCopy: "Copy", famCopied: "Copied",
    famWhatsapp: "Share on WhatsApp", famPreview: "See what they will see",
    famMsg: "I learned something about our family's health that may matter to you too. This private page explains it:",
    famStats: (o, n) => `Opened ${o} time(s) · ${n} asked about next steps`,
    famChoice: "You decide who to send it to, and you never have to send it.",
  },
  ar: {
    s1: "١. نتيجتي", s2: "٢. تحقق سريع", s3: "٣. مقارنة خاصة مع شريكي",
    s4: "٤. نتيجتنا", s5: "٥. التحدث مع مستشار وراثي",
    levels: { simple: "كلمات بسيطة", standard: "عادي", detailed: "تفاصيل أكثر" },
    hello: (n) => `مرحباً ${n}. هذه نتيجتك الخاصة، ولا يمكن لأحد غيرك رؤيتها.`,
    lab: "من", rewrite: "إعادة الصياغة بواسطة Gemma 4", rewriting: "يكتب Gemma… (قد يستغرق ذلك دقيقة على الحاسوب)",
    srcTemplate: "نص تمت مراجعته", srcAi: "Gemma 4 · اجتاز فحوص السلامة",
    aiRejected: "لم يجتز نص Gemma فحوص السلامة، لذلك يُعرض النص الذي تمت مراجعته.",
    escRequired: "يرجى التحدث مع مستشار وراثي بشأن هذه النتيجة.",
    escRecommended: "يمكن لمستشار وراثي أن يساعدك على فهم هذه النتيجة.",
    quizQ: [
      ["كونك حاملاً للصفة الوراثية يعني…", ["أنني بصحة جيدة ويمكنني نقل التغيّر", "أنني مصاب بالمرض", "أنني سأصاب بالمرض لاحقاً"], 0],
      ["في معظم الحالات، هل تحدد نتيجتي وحدها إن كان أطفالي سيتأثرون؟", ["لا، يعتمد ذلك أيضاً على نتيجة شريكي", "نعم، نتيجتي وحدها تحدد ذلك"], 0],
      ["من يقرر ما سنفعله بعد ذلك؟", ["نحن، بدعم من مستشار إن أردنا", "التطبيق يقرر", "الطبيب يقرر عنا"], 0],
    ],
    check: "تحقق من إجاباتي", quizGood: "كل الإجابات صحيحة. يمكنك المتابعة.",
    quizSimpler: (n) => `${n} من ٣ إجابات صحيحة. انتقلنا إلى شرح أبسط في الأعلى، وهذه هي الإجابات الصحيحة:`,
    consent: "أوافق على المقارنة الخاصة. ستُعرض علينا نحن الاثنين فقط الجينات التي نحملها معاً، ولن يُكشف أي شيء آخر.",
    start: "ابدأ واحصل على رمز", join: "انضم برمز شريكي", codePh: "رمز الشريك",
    shareCode: "أعطِ هذا الرمز لشريكك:", waiting: "بانتظار شريكك…",
    shareCodeWa: "أرسل الرمز عبر واتساب",
    impTitle: "استيراد تقرير المختبر",
    impIntro: "اختر تقرير PDF الذي استلمته من مختبر الفحص. نقرأ النتائج منه، ثم تتحقق منها قبل أي شرح.",
    impPrivacy: "يُقرأ ملف PDF على هذا الهاتف فقط، ولا يُرفع ولا يُحفظ في أي مكان.",
    impChoose: "اختر تقرير PDF", impReading: "تجري قراءة تقريرك على هذا الهاتف…",
    impNoReport: "ليس لديك تقرير؟ جرّب تقريراً وهمياً:",
    impCheck: "هذا ما قرأناه من تقريرك. يرجى مطابقته مع تقريرك الورقي.",
    impLab: "المختبر", impName: "الاسم", impSex: "الجنس", impFemale: "أنثى", impMale: "ذكر", impPickSex: "اختر…",
    impCols: ["استخدام", "الجين", "المتغيّر", "التصنيف"],
    impNegative: (g) => `مذكورة على أنها غير محمولة: ${g}.`,
    impNotCovered: (g) => `موجودة أيضاً في تقريرك لكن هذا التطبيق لا يغطيها: ${g}. يرجى سؤال مستشار وراثي عنها.`,
    impNone: "لم نجد أي نتائج في هذا الملف. هل هو ملف PDF نصي من مختبر؟ (الصور والصفحات الممسوحة غير مدعومة بعد.)",
    impNoFindings: "لا يذكر التقرير أي نتيجة حمل للجينات التي يغطيها هذا التطبيق.",
    impConfirmBox: "تحققت من هذه النتائج مقارنة بتقريري الورقي.",
    impNeedSex: "اختر الجنس أولاً، فهو يغيّر معنى بعض النتائج.",
    impContinue: "المتابعة بهذه النتائج", impAgain: "اختيار ملف آخر",
    impError: "تعذّرت قراءة هذا الملف. هل هو ملف PDF؟",
    you: "أنت", yourPdf: "تقرير PDF الخاص بك",
    matchMsg: (c) => `لنقارن نتائج فحصنا بشكل خاص في BioSentinel Family. لن يظهر إلا جين نحمله كلانا، ولا شيء غير ذلك. رمزي: ${c}`,
    codeReceived: "أرسل لك شريكك رمزاً. اقرأ نص الموافقة، وضع علامة في المربع، ثم اضغط انضم.",
    working: "تجري المقارنة الخاصة…", done: "تم.",
    sharedNone: "لا توجد جينات مشتركة ضمن هذه اللوحة.", sharedSome: (g) => `الجينات المشتركة: ${g}`,
    legend: ["مصاب", "حامل سليم", "غير حامل"], perPregnancy: "كل حمل (١٦ نقطة = ١٦ احتمالاً متساوياً)",
    optionsTitle: "الخيارات (بلا ترتيب معيّن — والقرار لكما)",
    options: [
      ["الاستشارة الوراثية", "مناقشة النتيجة والمشاعر والخيارات مع مستشار مؤهل."],
      ["فحص تأكيدي", "إعادة الفحص أو توسيعه لتأكيد النتيجة."],
      ["خيارات قبل الحمل", "مثل أطفال الأنابيب مع الفحص الجيني للأجنّة (PGT-M)."],
      ["فحوص أثناء الحمل", "فحوص يمكن أن تبيّن إن كان الجنين متأثراً."],
      ["عدم اتخاذ خطوات إضافية", "يختار بعض الأزواج المتابعة دون خطوات إضافية."],
    ],
    feeling: "كيف تشعر تجاه هذه النتائج؟", feelings: ["مطمئن", "غير متأكد", "قلق"],
    shareWhat: "اختر ما سيراه المستشار:", shareShared: "الجينات المشتركة بيننا",
    shareMine: "نتائجي التي تحتاج إلى مستشار", shareQuiz: "نتيجة التحقق السريع",
    contact: "كيف يتواصل معك المستشار؟ (اختياري)", note: "رسالة (اختيارية)",
    preview: "سيرى المستشار هذا فقط:", send: "أرسل إلى المستشار",
    sent: (id) => `تم الإرسال. رقم الحالة ${id}. سيتواصل معك مستشار.`,
    recRequired: "ننصح بشدة بالتحدث مع مستشار وراثي.",
    recOptional: "التحدث مع مستشار هو اختيارك.",
    aiOff: "إعادة الصياغة بالذكاء الاصطناعي (Gemma 4) متوقفة في هذا العرض على الإنترنت، لذلك تُعرض النصوص التي تمت مراجعتها. وتعمل جميع الميزات الأخرى.",
    s6: "٦. مساعدة عائلتي (اختياري)",
    famIntro: "قد يحمل الإخوة والأخوات وأبناء العم وغيرهم من الأقارب التغيّر نفسه دون أن يعلموا. يمكنك أن ترسل لهم صفحة خاصة تشرح ذلك.",
    famPrivacy: "لا تتضمن الصفحة اسمك ولا أياً من نتائجك الأخرى. يختار قريبك إن كان يريد قراءتها، ولن ترى إلا عدد من فتحوها، وليس من هم.",
    famNone: "لا تحتاج أي من نتائجك إلى دعوة للعائلة. لا تتم مشاركة النتائج غير المحددة مع العائلة.",
    famCreate: "إنشاء دعوة", famLink: "الرابط الخاص:", famCopy: "نسخ", famCopied: "تم النسخ",
    famWhatsapp: "مشاركة عبر واتساب", famPreview: "شاهد ما سيرونه",
    famMsg: "عرفت شيئاً عن صحة عائلتنا قد يهمك أنت أيضاً. هذه الصفحة الخاصة تشرحه:",
    famStats: (o, n) => `فُتحت ${o} مرة · ${n} سألوا عن الخطوات التالية`,
    famChoice: "أنت من يقرر لمن ترسلها، ولست مضطراً لإرسالها أبداً.",
  },
};

// ------------------------------------------------------------------ state
// Everything about this person lives in this page's memory only.
const S = {
  pid: new URLSearchParams(location.search).get("p") || "amina",
  lang: "en", level: "standard",
  person: null,          // the lab report
  findings: [],          // per-gene explanations from the server
  quizScore: null,
  shared: null,          // genes both partners carry (after PSI)
  couple: null,          // risk engine output for the couple
  invites: {},           // gene -> {id, owner, opened, next_step}; owner secret stays on this phone
  ai: true,              // can the server reach Gemma? (false on the free online demo)
};
const t = () => T[S.lang];
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const api = async (url, body) => {
  const r = await fetch(url, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error((await r.json()).detail || r.status);
  return r.json();
};
const unlock = (id) => $(id).classList.remove("locked");
const pathogenicGenes = () => S.person.variants.filter((v) => v.classification !== "Uncertain significance").map((v) => v.gene);

// ------------------------------------------------------------------ 1. my result
async function loadFindings() {
  $("findings").innerHTML = `<p>${esc(t().hello(S.person.name))}</p><p class="small">${t().lab}: ${esc(S.person.lab)}</p>${S.ai ? "" : `<p class="small">${t().aiOff}</p>`}<div id="cards"></div>`;
  S.findings = await Promise.all(S.person.variants.map((v) =>
    api("/api/explain/finding", { gene: v.gene, classification: v.classification, sex: S.person.sex, lang: S.lang, level: S.level, ai: false })
      .then((res) => ({ ...res, variant: v }))));
  renderFindings();
}

function sourceBadge(res) {
  if (res.source === "ai") return `<span class="badge ai">${t().srcAi}</span>`;
  const rejected = res.problems?.some((p) => !p.startsWith("ai unavailable"));
  return `<span class="badge">${t().srcTemplate}</span>` + (rejected ? `<div class="small">${t().aiRejected}</div>` : "");
}

function renderFindings() {
  const cards = S.findings.map((f, i) => `
    <div class="card">
      <h3>${esc(f.condition)}</h3>
      <div class="meta">${esc(f.variant.gene)} · ${esc(f.variant.variant)} · ${esc(f.variant.classification)}</div>
      <p id="fx-${i}">${esc(f.text)}</p>
      <div class="row">${sourceBadge(f)} ${S.ai ? `<button class="secondary" data-ai="${i}">${t().rewrite}</button>` : ""}</div>
      ${f.finding.escalation === "required" ? `<div class="flag">${t().escRequired}</div>` : ""}
      ${f.finding.escalation === "recommended" ? `<div class="flag">${t().escRecommended}</div>` : ""}
    </div>`).join("");
  $("cards").innerHTML = cards;
  document.querySelectorAll("[data-ai]").forEach((b) => (b.onclick = () => rewriteFinding(+b.dataset.ai, b)));
}

async function rewriteFinding(i, btn) {
  const f = S.findings[i];
  btn.disabled = true; btn.textContent = t().rewriting;
  const res = await api("/api/explain/finding", { gene: f.variant.gene, classification: f.variant.classification,
    sex: S.person.sex, lang: S.lang, level: S.level, ai: true });
  S.findings[i] = { ...res, variant: f.variant };
  renderFindings();
}

// ------------------------------------------------------------------ 2. quick check (teach-back)
function renderQuiz() {
  $("quiz").innerHTML = t().quizQ.map(([q, opts], qi) => `
    <p><strong>${esc(q)}</strong></p>
    ${opts.map((o, oi) => `<label><input type="radio" name="q${qi}" value="${oi}"> ${esc(o)}</label>`).join("")}
  `).join("") + `<button id="quiz-go">${t().check}</button><div id="quiz-out"></div>`;
  $("quiz-go").onclick = () => {
    const answers = t().quizQ.map((_, qi) => document.querySelector(`input[name=q${qi}]:checked`)?.value);
    const score = t().quizQ.filter(([, , right], qi) => +answers[qi] === right).length;
    S.quizScore = score;
    if (score === 3) {
      $("quiz-out").innerHTML = `<p class="ok">${t().quizGood}</p>`;
    } else {
      // Teach-back: a wrong answer means OUR explanation failed. Re-explain more simply.
      S.level = "simple"; $("level").value = "simple"; loadFindings();
      $("quiz-out").innerHTML = `<p>${esc(t().quizSimpler(score))}</p><ul>${t().quizQ.map(([q, o, r]) => `<li>${esc(q)} <strong>${esc(o[r])}</strong></li>`).join("")}</ul>`;
    }
    unlock("s-match"); renderMatch();
    unlock("s-family"); renderFamily();
  };
}

// ------------------------------------------------------------------ 3. private match (PSI)
function renderMatch() {
  if (S.shared) { $("match").innerHTML = `<p class="ok">${t().done} ${S.shared.length ? esc(t().sharedSome(S.shared.join(", "))) : t().sharedNone}</p>`; return; }
  $("match").innerHTML = `
    <label><input type="checkbox" id="consent"> ${esc(t().consent)}</label>
    <div class="row"><button id="m-start" disabled>${t().start}</button></div>
    <div class="row" style="margin-top:8px"><input type="text" id="m-code" placeholder="${t().codePh}" style="max-width:180px">
      <button id="m-join" class="secondary" disabled>${t().join}</button></div>
    <div id="m-status"></div>`;
  $("consent").onchange = (e) => { $("m-start").disabled = $("m-join").disabled = !e.target.checked; };
  // Opened from the partner's WhatsApp link: fill in the code, but consent stays a deliberate tick.
  if (codeFromLink()) { $("m-code").value = codeFromLink(); status(`<p class="flag">${esc(t().codeReceived)}</p>`); }
  $("m-start").onclick = startMatch;
  $("m-join").onclick = () => joinMatch($("m-code").value.trim().toUpperCase());
}

const status = (html) => ($("m-status").innerHTML = html);

// Demo couples. In real life the link would open the partner's own copy of the app.
const PARTNER = { amina: "khalid", khalid: "amina", sara: "omar", omar: "sara", import: "import" };
const joinUrl = (code) => `${location.origin}/partner.html?p=${PARTNER[S.pid] || "khalid"}&code=${code}`;
// A code that arrived in a link (?code=ABC123): letters and digits only, 6 at most.
const codeFromLink = () => (new URLSearchParams(location.search).get("code") || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function pollUntil(code, ready) {
  for (;;) { const s = await api(`/api/match/${code}`); if (ready(s)) return s; await sleep(1500); }
}

// Partner A: Amina (starts)
async function startMatch() {
  const key = PSI.newKey();                         // secret, never sent
  const items = PSI.shuffle(pathogenicGenes());
  const { code } = await api("/api/match", {});
  const wa = `https://wa.me/?text=${encodeURIComponent(t().matchMsg(code) + " " + joinUrl(code))}`;
  status(`<p>${t().shareCode}</p><div class="code">${code}</div>
    <p><a class="btn" target="_blank" rel="noopener" href="${wa}">${t().shareCodeWa}</a></p><p>${t().waiting}</p>`);
  await api(`/api/match/${code}/a1`, { values: await PSI.lockItems(items, key) });           // H(x)^a
  const s = await pollUntil(code, (s) => s.a_double && s.b_locked);
  status(`<p>${t().working}</p>`);
  const bDouble = PSI.lockValues(s.b_locked, key);                                          // (H(y)^b)^a
  await api(`/api/match/${code}/a2`, { values: bDouble });
  finishMatch(PSI.shared(items, s.a_double, bDouble));
}

// Partner B: Khalid (joins)
async function joinMatch(code) {
  status(`<p>${t().working}</p>`);
  const key = PSI.newKey();
  const items = PSI.shuffle(pathogenicGenes());
  const s = await pollUntil(code, (s) => s.a_locked);
  const aDouble = PSI.lockValues(s.a_locked, key);                                          // (H(x)^a)^b
  await api(`/api/match/${code}/b1`, { a_double: aDouble, b_locked: await PSI.lockItems(items, key) });
  const s2 = await pollUntil(code, (s) => s.b_double);
  finishMatch(PSI.shared(items, s2.b_double, aDouble));
}

async function finishMatch(shared) {
  S.shared = shared.sort();
  renderMatch();
  unlock("s-couple");
  await loadCouple();
  unlock("s-counsel");
  renderCounsel();
}

// ------------------------------------------------------------------ 4. our result
async function loadCouple(ai = false) {
  S.couple = await api("/api/explain/couple", { shared_genes: S.shared, lang: S.lang, level: S.level, ai });
  renderCouple();
}

function grid16(r) {
  // 16 dots: affected, carrier, unaffected in proportion to the risk engine's numbers
  const a = Math.round(r.affected * 16), c = Math.round(r.carrier * 16);
  const dots = Array.from({ length: 16 }, (_, i) => `<span class="${i < a ? "affected" : i < a + c ? "carrier" : ""}"></span>`).join("");
  const L = t().legend;
  return `<div class="small">${t().perPregnancy}</div><div class="grid16">${dots}</div>
    <div class="legend"><span>● ${L[0]} ${r.affected_pct}%</span><span>◐ ${L[1]} ${r.carrier_pct}%</span><span>○ ${L[2]} ${r.unaffected_pct}%</span></div>`;
}

function renderCouple() {
  if (!S.couple) return;
  const blocks = S.couple.explanations.map((e) => {
    const r = S.couple.risks.find((x) => x.gene === e.gene);
    return `<div class="card">${r ? `<h3>${esc(e.gene)}</h3>${grid16(r)}` : ""}<p>${esc(e.text)}</p>${sourceBadge(e)}</div>`;
  }).join("");
  const opts = S.couple.risks.length ? `<p><strong>${t().optionsTitle}</strong></p><div class="options">${
    t().options.map(([h, d]) => `<div class="card"><h3>${esc(h)}</h3><div class="small">${esc(d)}</div></div>`).join("")}</div>` : "";
  $("couple").innerHTML = blocks + (S.ai ? `<button class="secondary" id="c-ai">${t().rewrite}</button>` : "") + opts;
  if (S.ai) $("c-ai").onclick = (ev) => { ev.target.disabled = true; ev.target.textContent = t().rewriting; loadCouple(true); };
}

// ------------------------------------------------------------------ 5. counsellor hand-off
function renderCounsel() {
  const mine = S.findings.filter((f) => f.finding.escalation !== "none").map((f) => `${f.variant.gene}: ${f.finding.reason}`);
  const required = S.couple?.risks.length || S.findings.some((f) => f.finding.escalation === "required");
  $("counsel").innerHTML = `
    <p class="${required ? "flag" : ""}">${required ? t().recRequired : t().recOptional}</p>
    <p><strong>${t().feeling}</strong></p>
    <div class="row">${t().feelings.map((f, i) => `<label><input type="radio" name="feel" value="${i}"> ${f}</label>`).join("")}</div>
    <p><strong>${t().shareWhat}</strong></p>
    ${S.shared?.length ? `<label><input type="checkbox" id="sh-shared" checked> ${t().shareShared}: ${esc(S.shared.join(", "))}</label>` : ""}
    ${mine.length ? `<label><input type="checkbox" id="sh-mine" checked> ${t().shareMine}: ${esc(mine.join("; "))}</label>` : ""}
    <label><input type="checkbox" id="sh-quiz"> ${t().shareQuiz}</label>
    <label>${t().contact}<input type="text" id="sh-contact"></label>
    <label>${t().note}<input type="text" id="sh-note"></label>
    <p class="small">${t().preview}</p><pre class="card small" id="sh-preview"></pre>
    <button id="sh-send">${t().send}</button><div id="sh-out"></div>`;
  const build = () => {
    const feel = document.querySelector("input[name=feel]:checked")?.value;
    const reasons = [];
    if ($("sh-mine")?.checked) reasons.push(...S.findings.filter((f) => f.finding.escalation !== "none").map((f) => `${f.variant.gene}:${f.finding.reason}`));
    if (feel === "2") reasons.push("feels worried");
    return { shared_genes: $("sh-shared")?.checked ? S.shared : [], other_reasons: reasons, language: S.lang,
             quiz_score: $("sh-quiz").checked ? S.quizScore : null, contact: $("sh-contact").value, note: $("sh-note").value };
  };
  const refresh = () => ($("sh-preview").textContent = JSON.stringify(build(), null, 2));
  $("counsel").oninput = refresh; $("counsel").onchange = refresh; refresh();
  $("sh-send").onclick = async () => {
    const { id } = await api("/api/cases", build());
    $("sh-out").innerHTML = `<p class="ok">${esc(t().sent(id))}</p>`;
    $("sh-send").disabled = true;
  };
}

// ------------------------------------------------------------------ 6. help my family (cascade invites)
// The invite link holds only a random id. The relative says how they are related
// on THEIR phone, so you never label anyone, and the chance is computed for them.
const inviteUrl = (id) => `${location.origin}/invite.html?i=${id}`;

function renderFamily() {
  const eligible = S.findings.filter((f) => ["Pathogenic", "Likely pathogenic"].includes(f.variant.classification));
  if (!eligible.length) { $("family").innerHTML = `<p>${t().famNone}</p>`; return; }
  $("family").innerHTML = `<p>${esc(t().famIntro)}</p><p class="small">${esc(t().famPrivacy)}</p>` +
    eligible.map((f) => {
      const inv = S.invites[f.variant.gene];
      const body = inv ? `
        <div class="small">${t().famLink}</div>
        <div class="row"><input type="text" readonly value="${inviteUrl(inv.id)}" style="max-width:420px">
          <button class="secondary" data-copy="${f.variant.gene}">${t().famCopy}</button></div>
        <div class="row" style="margin-top:8px">
          <a class="btn" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent(t().famMsg + " " + inviteUrl(inv.id))}">${t().famWhatsapp}</a>
          <a class="btn secondary" target="_blank" href="${inviteUrl(inv.id)}">${t().famPreview}</a></div>
        <p class="small" id="stats-${f.variant.gene}">${esc(t().famStats(inv.opened, inv.next_step))}</p>`
        : `<button data-invite="${f.variant.gene}">${t().famCreate}</button>`;
      return `<div class="card"><h3>${esc(f.condition)}</h3><div class="meta">${esc(f.variant.gene)}</div>${body}</div>`;
    }).join("") + `<p class="small">${esc(t().famChoice)}</p>`;
  document.querySelectorAll("[data-invite]").forEach((b) => (b.onclick = () => createInvite(b.dataset.invite)));
  document.querySelectorAll("[data-copy]").forEach((b) => (b.onclick = async () => {
    await navigator.clipboard?.writeText(inviteUrl(S.invites[b.dataset.copy].id)).catch(() => {});
    b.textContent = t().famCopied;
  }));
}

async function createInvite(gene) {
  const f = S.findings.find((x) => x.variant.gene === gene);
  const { id, owner } = await api("/api/invites", { gene, classification: f.variant.classification });
  S.invites[gene] = { id, owner, opened: 0, next_step: 0 };
  renderFamily();
}

// Refresh the two counters every few seconds while this page is open.
setInterval(async () => {
  for (const [gene, inv] of Object.entries(S.invites)) {
    const r = await fetch(`/api/invites/${inv.id}/status`, { headers: { "X-Invite-Owner": inv.owner } });
    if (!r.ok) continue;
    Object.assign(inv, await r.json());
    const el = $(`stats-${gene}`);
    if (el) el.textContent = t().famStats(inv.opened, inv.next_step);
  }
}, 4000);

// ------------------------------------------------------------------ language, level, start
function applyLang() {
  document.documentElement.lang = S.lang;
  document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t()[el.dataset.t]));
  $("level").innerHTML = Object.entries(t().levels).map(([k, v]) => `<option value="${k}" ${k === S.level ? "selected" : ""}>${v}</option>`).join("");
}

// ------------------------------------------------------------------ 0. import my own lab report (PDF)
// The PDF is read in the browser (report_reader.js), the findings are found by rules
// (report_parser.js), and the person confirms them before anything else happens.
function renderImport() {
  $("findings").innerHTML = `<h3>${t().impTitle}</h3><p>${esc(t().impIntro)}</p>
    <p class="small">${esc(t().impPrivacy)}</p>
    <label class="btn">${t().impChoose}<input type="file" id="pdf" accept="application/pdf,.pdf" hidden></label>
    <p class="small">${t().impNoReport} ${["amina", "khalid", "sara", "omar"].map((p) =>
      `<a href="/samples/${p}_report.pdf" download>${p[0].toUpperCase() + p.slice(1)}</a>`).join(" · ")}</p>
    <div id="import-out"></div>`;
  $("pdf").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    $("import-out").innerHTML = `<p>${t().impReading}</p>`;
    try {
      const [text, panel] = await Promise.all([pdfToText(file), api("/api/panel")]);
      S.imported = parseReportText(text, panel.genes);
      renderConfirm();
    } catch (err) {
      console.error(err);
      $("import-out").innerHTML = `<p class="flag">${t().impError}</p>`;
    }
  };
  if (S.imported) renderConfirm();
}

function renderConfirm() {
  const r = S.imported;
  if (!r.findings.length && !r.negative.length && !r.notCovered.length) {
    $("import-out").innerHTML = `<p class="flag">${t().impNone}</p>`;
    return;
  }
  const rows = r.findings.map((f, i) => `<tr><td><input type="checkbox" data-use="${i}" checked></td>
    <td><strong>${esc(f.gene)}</strong></td><td>${esc(f.variant || "—")}</td><td>${esc(f.classification)}</td></tr>`).join("");
  $("import-out").innerHTML = `<div class="card">
    <p><strong>${esc(t().impCheck)}</strong></p>
    <p class="small">${t().impLab}: ${esc(r.lab || "—")}${r.name ? ` · ${t().impName}: ${esc(r.name)}` : ""}</p>
    <label>${t().impSex}: <select id="imp-sex"><option value="">${t().impPickSex}</option>
      <option value="F" ${r.sex === "F" ? "selected" : ""}>${t().impFemale}</option>
      <option value="M" ${r.sex === "M" ? "selected" : ""}>${t().impMale}</option></select></label>
    ${rows ? `<table class="imp"><tr>${t().impCols.map((c) => `<th>${c}</th>`).join("")}</tr>${rows}</table>`
           : `<p>${t().impNoFindings}</p>`}
    ${r.negative.length ? `<p class="small">${esc(t().impNegative(r.negative.join(", ")))}</p>` : ""}
    ${r.notCovered.length ? `<p class="flag">${esc(t().impNotCovered(r.notCovered.join(", ")))}</p>` : ""}
    <label><input type="checkbox" id="imp-ok"> ${esc(t().impConfirmBox)}</label>
    <div class="row"><button id="imp-go" disabled>${t().impContinue}</button>
      <button class="secondary" id="imp-again">${t().impAgain}</button></div>
    <div id="imp-msg"></div></div>`;
  $("imp-ok").onchange = (e) => ($("imp-go").disabled = !e.target.checked);
  $("imp-again").onclick = () => { S.imported = null; renderImport(); };
  $("imp-go").onclick = async () => {
    const sex = $("imp-sex").value;
    if (!sex) { $("imp-msg").innerHTML = `<p class="flag">${t().impNeedSex}</p>`; return; }
    const used = r.findings.filter((_, i) => document.querySelector(`[data-use="${i}"]`).checked);
    // From here on the imported report is used exactly like a lab-delivered one, in page memory only.
    S.person = { name: r.name || t().you, sex, lab: r.lab || t().yourPdf, variants: used };
    $("title").textContent = `BioSentinel Family · ${S.person.name}`;
    await rerenderAll();
    unlock("s-quiz");
  };
}

async function rerenderAll() {
  applyLang();
  if (!S.person) { renderImport(); return; }     // still on the import screen
  await loadFindings();
  renderQuiz();
  if (!$("s-match").classList.contains("locked")) renderMatch();
  if (S.shared) { await loadCouple(); renderCounsel(); }
  if (!$("s-family").classList.contains("locked")) renderFamily();
}

$("lang").onchange = (e) => { S.lang = e.target.value; rerenderAll(); };
$("level").onchange = (e) => { S.level = e.target.value; loadFindings(); if (S.shared) loadCouple(); };

(async () => {
  // Ask the server once whether Gemma is reachable; if not, hide the rewrite buttons.
  S.ai = await api("/api/health").then((h) => h.ai.reachable).catch(() => false);
  if (S.pid === "import") { $("title").textContent = "BioSentinel Family"; await rerenderAll(); return; }
  S.person = await api(`/api/personas/${S.pid}`);
  $("title").textContent = `BioSentinel Family · ${S.person.name}`;
  await rerenderAll();
  unlock("s-quiz");
})();
