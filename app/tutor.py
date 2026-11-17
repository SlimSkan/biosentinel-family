"""Live AI that adapts to what the reader understood.

1. reexplain(): after the three-question check, each missed idea is re-explained by Gemma 4,
   starting from the reader's own wrong answer ("You chose 'I have the disease'...").
2. answer(): the reader asks a question in their own words. Gemma answers ONLY from numbered
   facts about the reader's own results, and must cite a fact for every sentence. The citations
   are checked and shown, so every answer is explainable.

Both run through the same guardrails as the explanations, and both fall back to reviewed text.
"""
import re

from . import explainer, guardrails, knowledge, llm

# --------------------------------------------------------------------------- 1. teach-back
# One idea per question of the quick check (same order as quizQ in web/app.js).
CONCEPTS = {
    "carrier": {
        "en": "Being a carrier is not a disease. A carrier is healthy and usually never becomes ill from it. "
              "A carrier can pass the changed gene on to children.",
        "ar": "كونك حاملاً للصفة الوراثية ليس مرضاً. الحامل للصفة بصحة جيدة وعادةً لا يمرض بسببها. "
              "يمكن للحامل أن ينقل الجين المتغيّر إلى أطفاله.",
        "facts": [explainer._f("healthy", "a carrier is healthy, it is not a disease",
                               ["healthy", "not a disease", "not ill", "not sick"], ["بصحة", "سليم", "ليس مرض"]),
                  explainer._f("pass_on", "a carrier can pass the gene on to children",
                               ["pass", "children", "child"], ["ينقل", "أطفال", "الطفل"])],
    },
    "partner": {
        "en": "For most conditions on this panel, a child can only be affected if both parents carry a change in the "
              "same gene. So your result alone does not decide it: it also depends on your partner's result. "
              "X-linked conditions are the exception, and a genetic counsellor can explain them.",
        "ar": "في معظم الحالات ضمن هذه اللوحة، لا يمكن أن يتأثر الطفل إلا إذا كان كلا الوالدين يحملان تغيّراً في الجين "
              "نفسه. لذلك لا تحدد نتيجتك وحدها ذلك، بل تعتمد أيضاً على نتيجة شريكك. الحالات المرتبطة بالكروموسوم X "
              "استثناء، ويمكن لمستشار وراثي أن يشرحها.",
        "facts": [explainer._f("both", "both parents must carry a change in the same gene",
                               ["both parents", "both of you", "both partners"], ["كلا الوالدين", "الوالدين", "كلاكما"]),
                  explainer._f("partner", "it also depends on the partner's result", ["partner"], ["شريك"])],
    },
    "autonomy": {
        "en": "You decide what to do next, together, and only if you want to. This app does not decide, and nobody "
              "decides for you. A genetic counsellor can support you and explain the options without judging.",
        "ar": "القرار بشأن الخطوات التالية لكما معاً، وفقط إن رغبتما. هذا التطبيق لا يقرر، ولا أحد يقرر عنكما. "
              "يمكن لمستشار وراثي أن يدعمكما ويشرح الخيارات دون أن يحكم عليكما.",
        "facts": [explainer._f("you_decide", "the decision is theirs", ["you decide", "your decision", "your choice",
                               "choice is yours", "decide"], ["قرار", "تقرر", "خيار"]),
                  explainer._COUNSELLOR],
    },
}
QUIZ_CONCEPTS = ["carrier", "partner", "autonomy"]

TUTOR_PROMPT = """You are BioSentinel Family, a kind tutor helping someone understand a genetic screening idea.
The reader answered a check question wrongly. Start from THEIR answer, gently say why it is not quite right, then explain the idea.
Strict rules:
- Use ONLY the facts in the reviewed explanation. No new medical facts, no numbers.
- Never tell anyone whether to marry, have children or end a pregnancy.
- Never write "you have" or say the reader has a condition: a carrier is healthy.
- No blame. Warm, short, plain text, no markdown, no greetings.
- In Arabic, use forms that suit any reader; never assume the reader is a man or a woman.
- Write in {language}. Reading level: {level_guide}."""


def reexplain(concept: str, wrong_answer: str, question: str, lang: str = "en", level: str = "simple") -> dict:
    c = CONCEPTS[concept]
    base = c[lang]
    system = TUTOR_PROMPT.format(language="Arabic (Modern Standard, simple)" if lang == "ar" else "English",
                                 level_guide=explainer.LEVEL_GUIDE.get(level, explainer.LEVEL_GUIDE["simple"]))
    must = "\n".join(f"- {f['say']}" for f in c["facts"])
    user = (f"Check question: {question}\nThe reader answered: {wrong_answer}\n\n"
            f"Your text MUST say:\n{must}\n\nReviewed explanation of the idea:\n{base}")
    try:
        text = explainer._clean(llm.ask(system, user, max_tokens=400))
    except Exception as e:
        return {"text": base, "source": "template", "problems": [f"ai unavailable: {type(e).__name__}"]}
    problems = guardrails.check(text, {0, 100}, facts=c["facts"], lang=lang)
    if problems:
        return {"text": base, "source": "template", "problems": problems}
    return {"text": text, "source": "ai", "problems": []}


# --------------------------------------------------------------------------- 2. ask a question
# Numbers a reader may meet, by kind of result. Anything else in an answer is rejected.
NO_ANSWER = {
    "en": "This app can only answer from your own results, and it cannot answer that one safely. "
          "Please ask a genetic counsellor: they can answer questions about your situation.",
    "ar": "يجيب هذا التطبيق فقط بناءً على نتائجك، ولا يمكنه الإجابة عن هذا السؤال بأمان. "
          "يرجى سؤال مستشار وراثي، فهو يستطيع الإجابة عن الأسئلة المتعلقة بوضعك.",
}

ASK_PROMPT = """You are BioSentinel Family. Answer the reader's question about their genetic screening result.
Strict rules:
- Use ONLY the numbered FACTS. After EVERY sentence, cite the fact(s) it comes from, like [F2] or [F1][F3].
- Questions about children in general, or about whether the reader is ill, CAN be answered from the inheritance
  rules in the FACTS (for example: a carrier is healthy; the chances depend on both parents; this app does not diagnose).
- Reply with exactly NO_ANSWER only if the FACTS cannot answer it, or it asks you to choose a medical decision,
  or for advice about marriage or pregnancy.
- Numbers: only those that appear in the FACTS.
- Never tell anyone whether to marry, have children or end a pregnancy. Never rank options.
- Never write "you have" and never say the reader has a condition.
- At most 4 short sentences. Plain text, no markdown, no greetings.
- In Arabic, use forms that suit any reader.
- Write in {language}. Reading level: {level_guide}."""

_CITE = re.compile(r"\[F(\d+)\]")


def fact_list(findings: list[dict], shared: list[str], lang: str) -> list[str]:
    """Numbered facts the answer may use: only the reader's own results (no names), plus
    the general rules of inheritance and of this app."""
    facts = []
    for f in findings[:12]:
        gene, cls = f.get("gene", ""), f.get("classification", "")
        try:
            g = knowledge.gene(gene)
        except KeyError:
            continue
        inh = "on the X chromosome (X-linked)" if g["inheritance"] == "XL" else "autosomal recessive"
        if lang == "ar":
            inh = "مرتبط بالكروموسوم X" if g["inheritance"] == "XL" else "وراثة متنحية"
            facts.append(f"نتيجة القارئ: {gene} ({cls})، مرتبط بـ{g['condition']['ar']}، {inh}.")
        else:
            facts.append(f"The reader's result: {gene} ({cls}), linked to {g['condition']['en']}; {inh}.")
        facts.append(g["summary"][lang])
    rules = {
        "en": ["A carrier is healthy and has one changed copy of a gene.",
               "For an autosomal recessive condition, a child can only be affected if both parents carry a change in the same gene; then in each pregnancy the chance is 25% affected, 50% healthy carrier and 25% not a carrier.",
               "For an X-linked gene carried by a woman, in each pregnancy a son has a 50% chance of being affected and a daughter a 50% chance of being a carrier.",
               "A variant of uncertain significance (VUS) is a change whose effect is not yet known; it is not a diagnosis.",
               "Options a couple may discuss with a counsellor include confirmatory testing, IVF with genetic testing of embryos (PGT-M), testing during pregnancy, or no further action; the choice is theirs.",
               "This app gives educational information. It does not diagnose and does not replace a genetic counsellor."],
        "ar": ["الحامل للصفة الوراثية بصحة جيدة ولديه نسخة واحدة متغيّرة من الجين.",
               "في الحالات المتنحية، لا يتأثر الطفل إلا إذا كان كلا الوالدين يحملان تغيّراً في الجين نفسه، وعندها في كل حمل يكون الاحتمال 25% أن يتأثر الطفل، و50% أن يكون حاملاً سليماً، و25% ألا يحمل الصفة.",
               "في الجين المرتبط بالكروموسوم X الذي تحمله امرأة، في كل حمل لدى الابن احتمال 50% أن يتأثر، ولدى الابنة احتمال 50% أن تحمل الصفة.",
               "المتغيّر غير محدد الأهمية تغيّر لم يُعرف تأثيره بعد، وليس تشخيصاً.",
               "من الخيارات التي يمكن مناقشتها مع مستشار: فحص تأكيدي، أو أطفال الأنابيب مع فحص الأجنة وراثياً، أو الفحص أثناء الحمل، أو عدم اتخاذ أي خطوة؛ والقرار للزوجين.",
               "يقدم هذا التطبيق معلومات تثقيفية، ولا يشخّص ولا يحل محل المستشار الوراثي."],
    }[lang]
    if shared:
        rules.append(("Both partners carry a change in: " if lang == "en" else "يحمل كلا الشريكين تغيّراً في: ")
                     + ", ".join(shared) + ".")
    return facts + rules


def answer(question: str, findings: list[dict], shared: list[str], lang: str = "en", level: str = "standard") -> dict:
    facts = fact_list(findings, shared, lang)
    numbered = "\n".join(f"F{i + 1}: {f}" for i, f in enumerate(facts))
    allowed = {0, 100} | guardrails._percentages(" ".join(facts))
    refusal = {"text": NO_ANSWER[lang], "source": "template", "sources": [], "problems": []}
    system = ASK_PROMPT.format(language="Arabic (Modern Standard, simple)" if lang == "ar" else "English",
                               level_guide=explainer.LEVEL_GUIDE.get(level, explainer.LEVEL_GUIDE["standard"]))
    try:
        raw = llm.ask(system, f"FACTS:\n{numbered}\n\nQUESTION: {question}", max_tokens=400)
    except Exception as e:
        return refusal | {"problems": [f"ai unavailable: {type(e).__name__}"]}
    raw = re.sub(r"NO_?ANSWER", "", re.sub(r"[*#`]+", "", raw)).strip()
    if not _CITE.search(raw):
        return refusal | {"problems": ["model said it cannot answer from the facts"]}
    sentences = [s for s in re.split(r"(?<=[.!?؟\]])\s+", raw) if s.strip()]
    cited = {int(n) for n in _CITE.findall(raw)}
    problems = []
    if not cited or any(n < 1 or n > len(facts) for n in cited):
        problems.append("citations missing or invalid")
    uncited = [s for s in sentences if not _CITE.search(s) and len(s.split()) > 3]
    if uncited:
        problems.append(f"sentences without a source: {len(uncited)}")
    text = re.sub(r"\s*\[F\d+\]", "", raw).strip()
    problems += guardrails.check(text, allowed, lang=lang)
    if problems:
        return refusal | {"problems": problems}
    return {"text": text, "source": "ai", "problems": [],
            "sources": [{"id": f"F{n}", "text": facts[n - 1]} for n in sorted(cited)]}
