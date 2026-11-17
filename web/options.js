// Structured, neutral comparison of reproductive options, and a personal next-steps plan.
// Reviewed text only (no AI). Options are listed in no particular order and never ranked.
// The couple can pick options to compare side by side; their picks go into the counsellor brief.

export const FIELDS = {
  en: { when: "When", involves: "What it involves", tells: "What it can tell you", consider: "Things to consider", ask: "A question to ask the counsellor" },
  ar: { when: "متى", involves: "ماذا يتضمن", tells: "ماذا يمكن أن يبيّن", consider: "أمور يجب مراعاتها", ask: "سؤال للمستشار" },
};

export const OPTIONS = [
  { id: "counselling",
    en: { name: "Genetic counselling", when: "Any time, ideally before a pregnancy.",
          involves: "A conversation with a certified genetic counsellor, in person or online. No test.",
          tells: "What your result means for you, and every option in detail.",
          consider: "It does not commit you to anything.", ask: "What would each option involve for us?" },
    ar: { name: "الاستشارة الوراثية", when: "في أي وقت، ويُفضّل قبل الحمل.",
          involves: "محادثة مع مستشار وراثي معتمد، حضورياً أو عن بُعد. دون أي فحص.",
          tells: "ماذا تعني نتيجتكما لكما، وكل خيار بالتفصيل.",
          consider: "لا تُلزمكما بأي شيء.", ask: "ماذا يتضمن كل خيار بالنسبة لنا؟" } },
  { id: "confirm",
    en: { name: "Confirmatory testing", when: "Before deciding anything.",
          involves: "A new blood sample, sometimes testing the exact change found.",
          tells: "Whether the screening result is confirmed.",
          consider: "Results can take a few weeks.", ask: "Do we need to repeat or extend the test?" },
    ar: { name: "فحص تأكيدي", when: "قبل اتخاذ أي قرار.",
          involves: "عينة دم جديدة، وأحياناً فحص التغيّر نفسه الذي وُجد.",
          tells: "ما إذا كانت نتيجة الفحص مؤكدة.",
          consider: "قد تستغرق النتائج بضعة أسابيع.", ask: "هل نحتاج إلى إعادة الفحص أو توسيعه؟" } },
  { id: "pgt",
    en: { name: "IVF with genetic testing of embryos (PGT-M)", when: "Before a pregnancy.",
          involves: "IVF treatment; embryos are tested before one is transferred.",
          tells: "Whether an embryo carries the condition, before a pregnancy starts.",
          consider: "Several clinic visits and medication; success is not guaranteed; cost.",
          ask: "Is PGT-M available for our gene, and what does it involve?" },
    ar: { name: "أطفال الأنابيب مع فحص الأجنة وراثياً (PGT-M)", when: "قبل الحمل.",
          involves: "علاج أطفال الأنابيب، وتُفحص الأجنة قبل نقل أحدها.",
          tells: "ما إذا كان الجنين يحمل الحالة، قبل بدء الحمل.",
          consider: "عدة زيارات للعيادة وأدوية؛ النجاح غير مضمون؛ التكلفة.",
          ask: "هل يتوفر فحص PGT-M لجيننا، وماذا يتضمن؟" } },
  { id: "prenatal",
    en: { name: "Testing during pregnancy", when: "During a pregnancy, at set weeks.",
          involves: "A sample from the placenta or the fluid around the baby.",
          tells: "Whether the baby is affected.",
          consider: "A small risk to the pregnancy; the result can help the couple prepare.",
          ask: "When could this be done, and what are the risks?" },
    ar: { name: "الفحص أثناء الحمل", when: "أثناء الحمل، في أسابيع محددة.",
          involves: "عينة من المشيمة أو من السائل المحيط بالجنين.",
          tells: "ما إذا كان الجنين مصاباً.",
          consider: "خطر بسيط على الحمل؛ ويمكن أن تساعد النتيجة الزوجين على الاستعداد.",
          ask: "متى يمكن إجراؤه، وما هي المخاطر؟" } },
  { id: "newborn",
    en: { name: "Newborn testing and early care", when: "Soon after birth.",
          involves: "A blood test for the baby.",
          tells: "Whether the baby is affected, so care can start early.",
          consider: "Treatment and care for many of these conditions have improved a lot.",
          ask: "Which specialists would follow our baby?" },
    ar: { name: "فحص المولود والرعاية المبكرة", when: "بعد الولادة بوقت قصير.",
          involves: "فحص دم للمولود.",
          tells: "ما إذا كان المولود مصاباً، لتبدأ الرعاية مبكراً.",
          consider: "تحسّن علاج كثير من هذه الحالات ورعايتها كثيراً.",
          ask: "أي الأطباء المختصين سيتابعون طفلنا؟" } },
  { id: "none",
    en: { name: "No further action", when: "Any time.", involves: "Nothing.",
          tells: "—", consider: "You can change your mind and talk to a counsellor at any time.",
          ask: "Who can we contact later if we have questions?" },
    ar: { name: "عدم اتخاذ أي خطوة", when: "في أي وقت.", involves: "لا شيء.",
          tells: "—", consider: "يمكنكما تغيير رأيكما والتحدث مع مستشار في أي وقت.",
          ask: "بمن نتصل لاحقاً إن كانت لدينا أسئلة؟" } },
];

const UI = {
  en: { title: "Options, side by side (in no particular order: the choice is yours)",
        pick: "Tick up to 3 options to compare them. Your picks are added to your counsellor summary only if you choose to send it.",
        compare: "Compare", plan: "My next steps", planNote: "Tick each step when it is done. This is a guide, not medical advice." },
  ar: { title: "الخيارات جنباً إلى جنب (بلا ترتيب معيّن — والقرار لكما)",
        pick: "اختر حتى 3 خيارات لمقارنتها. تُضاف اختياراتك إلى ملخص المستشار فقط إذا قررت إرساله.",
        compare: "قارن", plan: "خطواتي التالية", planNote: "ضع علامة على كل خطوة عند إنجازها. هذا دليل وليس نصيحة طبية." },
};

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Personal next steps, from the result type only (deterministic, reviewed text).
export function nextSteps({ shared = [], xlFemale = [], vus = [], picks = [] }, lang) {
  const en = lang !== "ar";
  const steps = [];
  const names = picks.map((id) => OPTIONS.find((o) => o.id === id)[lang].name);
  if (shared.length) {
    steps.push(en ? `Book a genetic counselling appointment together (step 5) about ${shared.join(", ")}.`
                  : `احجزا موعد استشارة وراثية معاً (الخطوة ٥) بشأن ${shared.join("، ")}.`);
    steps.push(en ? "Ask whether a confirmatory test is needed for both of you." : "اسألا إن كان فحص تأكيدي لازماً لكليكما.");
    steps.push(names.length
      ? (en ? `Before a pregnancy, discuss the options you picked: ${names.join("; ")}.` : `قبل الحمل، ناقشا الخيارات التي اخترتماها: ${names.join("؛ ")}.`)
      : (en ? "Before a pregnancy, go through the options with the counsellor." : "قبل الحمل، راجعا الخيارات مع المستشار."));
  }
  for (const g of xlFemale) {
    steps.push(en ? `Ask the counsellor what your ${g} result means for sons and daughters.` : `اسألي المستشار ماذا تعني نتيجة ${g} بالنسبة للأبناء والبنات.`);
  }
  for (const g of vus) {
    steps.push(en ? `Ask whether the lab may update (reclassify) your uncertain ${g} result later.` : `اسأل إن كان المختبر قد يحدّث تصنيف نتيجة ${g} غير المؤكدة لاحقاً.`);
  }
  if (shared.length || xlFemale.length) {
    steps.push(en ? "If you wish, tell relatives privately with a family invite (step 6): they may carry it too."
                  : "إن رغبتما، أخبرا الأقارب بشكل خاص عبر دعوة عائلية (الخطوة ٦)، فقد يحملونها أيضاً.");
  }
  if (!steps.length) {
    steps.push(en ? "No shared gene on this panel. No test covers every condition; a counsellor can answer questions."
                  : "لا يوجد جين مشترك ضمن هذه اللوحة. لا يغطي أي فحص جميع الحالات، ويمكن لمستشار الإجابة عن الأسئلة.");
  }
  return steps;
}

// Renders the comparison into `el`. state.picks is an array of option ids; onChange() is called when it changes.
export function renderOptions(el, lang, state, onChange) {
  const u = UI[lang], f = FIELDS[lang];
  const picked = OPTIONS.filter((o) => state.picks.includes(o.id));
  const table = picked.length >= 2 ? `<div class="cmp-wrap"><table class="cmp"><tr><th></th>${picked.map((o) => `<th>${esc(o[lang].name)}</th>`).join("")}</tr>
      ${Object.keys(f).map((k) => `<tr><th>${f[k]}</th>${picked.map((o) => `<td>${esc(o[lang][k])}</td>`).join("")}</tr>`).join("")}</table></div>` : "";
  el.innerHTML = `<p><strong>${u.title}</strong></p><p class="small">${u.pick}</p>
    <div class="options">${OPTIONS.map((o) => `<label class="card opt ${state.picks.includes(o.id) ? "on" : ""}">
      <input type="checkbox" data-opt="${o.id}" ${state.picks.includes(o.id) ? "checked" : ""}>
      <h3>${esc(o[lang].name)}</h3><div class="small"><b>${f.when}:</b> ${esc(o[lang].when)}</div>
      <div class="small">${esc(o[lang].involves)}</div></label>`).join("")}</div>${table}`;
  el.querySelectorAll("[data-opt]").forEach((cb) => (cb.onchange = () => {
    const id = cb.dataset.opt;
    state.picks = cb.checked ? [...state.picks, id].slice(-3) : state.picks.filter((x) => x !== id);
    renderOptions(el, lang, state, onChange);
    onChange?.();
  }));
}

export function renderPlan(el, lang, input, state) {
  const u = UI[lang];
  const steps = nextSteps(input, lang);
  state.steps = steps;
  state.done = state.done || {};
  el.innerHTML = `<p><strong>${u.plan}</strong></p><ol class="plan">${steps.map((s, i) =>
    `<li><label><input type="checkbox" data-step="${i}" ${state.done[s] ? "checked" : ""}> ${esc(s)}</label></li>`).join("")}</ol>
    <p class="small">${u.planNote}</p>`;
  el.querySelectorAll("[data-step]").forEach((cb) => (cb.onchange = () => { state.done[steps[+cb.dataset.step]] = cb.checked; }));
}
