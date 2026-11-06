"""Turns a finding into a plain-language explanation, in Arabic or English.

Two layers, on purpose:
  1. TEMPLATES - short texts written and reviewed by humans. Always correct,
     always available (no AI, no network). This is the safety net.
  2. GEMMA 4   - rewrites the template for the reader's language and reading
     level. Its output must pass guardrails.check(); otherwise we fall back
     to the template.

The AI receives only de-identified facts (gene, condition, the risk numbers).
It never receives a name, the full carrier list, or the partner's result.
"""
import os
import re

import httpx

from . import guardrails, knowledge

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("BSF_MODEL", "gemma4:e4b")
TIMEOUT_S = float(os.environ.get("BSF_LLM_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# 1. Reviewed templates. {gene}, {condition}, {summary} are filled from the KB.
#    "simple" falls back to "standard" when not written yet.
# ---------------------------------------------------------------------------
TEMPLATES = {
    "carrier_self": {
        "en": {
            "standard": "You carry one changed copy of the {gene} gene, linked to {condition}. Being a carrier is not a disease: carriers are usually healthy. {summary} A child can only be affected if both parents carry a change in the same gene, so what this means for your future children also depends on your partner's result.",
            "simple": "You are a carrier for {condition}. This does not make you ill. A child can only have this condition if both parents are carriers in the same gene.",
        },
        "ar": {
            "standard": "أنت تحمل نسخة واحدة متغيّرة من جين {gene} المرتبط بـ{condition}. كونك حاملاً للصفة الوراثية لا يعني أنك مريض، فالحاملون عادةً بصحة جيدة. {summary} لا يمكن أن يتأثر الطفل إلا إذا كان كلا الوالدين يحملان تغيّراً في الجين نفسه، لذلك يعتمد ما يعنيه هذا لأطفالك في المستقبل على نتيجة شريكك أيضاً.",
            "simple": "أنت حامل للصفة الوراثية لـ{condition}. هذا لا يجعلك مريضاً. لا يمكن أن يُصاب الطفل بهذه الحالة إلا إذا كان كلا الوالدين حاملَين للصفة في الجين نفسه.",
        },
    },
    "xl_carrier_female": {
        "en": {"standard": "You carry a change in the {gene} gene, linked to {condition}. This gene is on the X chromosome. Women who carry it are usually healthy or only mildly affected. {summary} In each pregnancy, a son has a 50% chance of being affected and a daughter has a 50% chance of being a carrier, whatever your partner's result. A genetic counsellor can explain what this means for you."},
        "ar": {"standard": "أنتِ تحملين تغيّراً في جين {gene} المرتبط بـ{condition}. يقع هذا الجين على الكروموسوم X. النساء الحاملات له يكنّ عادةً بصحة جيدة أو يتأثرن بشكل خفيف. {summary} في كل حمل، لدى الابن احتمال 50% أن يتأثر، ولدى الابنة احتمال 50% أن تحمل الصفة، بغض النظر عن نتيجة الشريك. يمكن لمستشار وراثي أن يشرح لكِ ما يعنيه ذلك."},
    },
    "vus": {
        "en": {"standard": "Your report lists a change in the {gene} gene whose effect is not yet known. This is called a variant of uncertain significance. It is common and it is not a diagnosis. Only a genetics professional should interpret it, so we will help you talk to a genetic counsellor."},
        "ar": {"standard": "يذكر تقريرك تغيّراً في جين {gene} لم يُعرف تأثيره بعد، ويسمى «متغيّراً غير محدد الأهمية». هذا أمر شائع وليس تشخيصاً. يجب أن يفسّره مختص في علم الوراثة فقط، لذلك سنساعدك على التحدث مع مستشار وراثي."},
    },
    "ar_both_carriers": {
        "en": {
            "standard": "You both carry a change in the {gene} gene, linked to {condition}. You are both healthy carriers. {summary} In each pregnancy there is a 25% chance that the child is affected, a 50% chance that the child is a healthy carrier like you, and a 25% chance that the child does not carry it. The chances are the same in every pregnancy. There are several options, and the choice is yours. A genetic counsellor can go through them with you.",
            "simple": "You are both carriers for {condition}. You are both healthy. In each pregnancy, there is a 1 in 4 chance (25%) that the child has the condition. A genetic counsellor can talk with you about your options. The choice is yours.",
        },
        "ar": {
            "standard": "كلاكما يحمل تغيّراً في جين {gene} المرتبط بـ{condition}، وكلاكما حامل سليم للصفة الوراثية. {summary} في كل حمل، هناك احتمال 25% أن يكون الطفل مصاباً، واحتمال 50% أن يكون حاملاً سليماً مثلكما، واحتمال 25% ألا يحمل الصفة. تتكرر الاحتمالات نفسها في كل حمل. هناك عدة خيارات، والقرار لكما. يمكن لمستشار وراثي أن يناقشها معكما.",
            "simple": "كلاكما حامل للصفة الوراثية لـ{condition}، وكلاكما بصحة جيدة. في كل حمل، هناك احتمال 25% أن يُصاب الطفل بالحالة. يمكن لمستشار وراثي أن يتحدث معكما عن الخيارات. والقرار لكما.",
        },
    },
    "no_shared": {
        "en": {"standard": "On this screening panel, you do not carry changes in the same gene. This means the conditions tested here are unlikely to affect your children through both of you. No test covers every condition."},
        "ar": {"standard": "ضمن هذه اللوحة من الفحوص، لا تحملان تغيّرات في الجين نفسه. هذا يعني أن الحالات المفحوصة هنا من غير المرجح أن تنتقل إلى أطفالكما من خلالكما معاً. لا يغطي أي فحص جميع الحالات."},
    },
    # ---- for a RELATIVE who received a family invite (they have not been tested)
    "relative_ar": {
        "en": {
            "standard": "A relative of yours has learned that they carry a change in the {gene} gene, linked to {condition}. Based on how you are related, there is about a {pct}% chance that you carry the same change. {summary} Carriers are healthy and usually do not know they carry it. It matters mainly when planning a family: a child can only be affected if both parents carry a change in the same gene. A simple carrier test can tell you. Whether to test is your choice, and a genetic counsellor can help.",
            "simple": "Someone in your family carries a change in a gene linked to {condition}. You may carry it too: the chance is about {pct}%. Carriers are healthy. It matters when you plan a family: a child can only have the condition if both parents are carriers. A simple test can tell you. The choice is yours. A genetic counsellor can help.",
        },
        "ar": {
            "standard": "علم أحد أقاربك أنه يحمل تغيّراً في جين {gene} المرتبط بـ{condition}. بحسب صلة القرابة بينكما، هناك احتمال يقارب {pct}% أن تحمل التغيّر نفسه. {summary} الحاملون للصفة الوراثية عادةً بصحة جيدة ولا يعرفون أنهم يحملونها. ويهم ذلك بشكل خاص عند التخطيط لتكوين أسرة: لا يمكن أن يتأثر الطفل إلا إذا كان كلا الوالدين يحملان تغيّراً في الجين نفسه. يمكن لفحص بسيط للحاملين أن يبيّن ذلك. والقرار في إجراء الفحص يعود إليك، ويمكن لمستشار وراثي أن يساعدك.",
            "simple": "يحمل أحد أفراد عائلتك تغيّراً في جين مرتبط بـ{condition}. قد تحمله أنت أيضاً، والاحتمال يقارب {pct}%. الحاملون للصفة بصحة جيدة. يهم ذلك عند التخطيط لأسرة: لا يُصاب الطفل إلا إذا كان كلا الوالدين حاملَين. يمكن لفحص بسيط أن يبيّن ذلك. والقرار لك. يمكن لمستشار وراثي أن يساعدك.",
        },
    },
    "relative_general": {
        "en": {"standard": "A relative of yours has learned that they carry a change in the {gene} gene, linked to {condition}. Relatives can carry the same change. {summary} Carriers are usually healthy. A simple carrier test can tell you whether you carry it. Whether to test is your choice, and a genetic counsellor can explain what it means for you and your family."},
        "ar": {"standard": "علم أحد أقاربك أنه يحمل تغيّراً في جين {gene} المرتبط بـ{condition}. قد يحمل الأقارب التغيّر نفسه. {summary} الحاملون للصفة الوراثية عادةً بصحة جيدة. يمكن لفحص بسيط للحاملين أن يبيّن إن كنت تحمله. والقرار في إجراء الفحص يعود إليك، ويمكن لمستشار وراثي أن يشرح ما يعنيه ذلك لك ولعائلتك."},
    },
    "relative_xl": {
        "en": {"standard": "A relative of yours has learned that they carry a change in the {gene} gene, linked to {condition}. This gene is on the X chromosome, so who else may carry it depends on which side of the family it comes from. Women who carry it are usually healthy or only mildly affected; men who carry it can be affected. {summary} A simple test can tell you whether you carry it. Whether to test is your choice, and a genetic counsellor can explain what it means for you."},
        "ar": {"standard": "علم أحد أقاربك أنه يحمل تغيّراً في جين {gene} المرتبط بـ{condition}. يقع هذا الجين على الكروموسوم X، لذلك يعتمد من قد يحمله أيضاً على جهة العائلة التي جاء منها. النساء الحاملات له يكنّ عادةً بصحة جيدة أو يتأثرن بشكل خفيف، أما الرجال الحاملون له فقد يتأثرون. {summary} يمكن لفحص بسيط أن يبيّن إن كنت تحمله. والقرار في إجراء الفحص يعود إليك، ويمكن لمستشار وراثي أن يشرح ما يعنيه ذلك لك."},
    },
}
RELATIVE_KEYS = ("relative_ar", "relative_general", "relative_xl")

# ---------------------------------------------------------------------------
# 2. Key facts per template: what a rewrite must never drop.
#    "say" is told to Gemma; the keywords are what guardrails.missing_facts()
#    looks for (one is enough). Gene-specific facts live in panel_kb.json
#    ("key_facts") and are added when the template includes the {summary}.
# ---------------------------------------------------------------------------
def _f(id, say, en, ar):
    return {"id": id, "say": say, "en": en, "ar": ar}


_COUNSELLOR = _f("counsellor", "a genetic counsellor can help",
                 ["counsellor", "counselor"], ["مستشار", "استشاري", "المرشد"])
_HEALTHY = _f("carrier_healthy", "carriers are healthy; it is not a disease",
              ["healthy", "not ill", "not a disease", "not sick", "not make you ill"],
              ["بصحة", "سليم", "ليس مرض", "لا يعني انك مريض", "لا يجعلك مريض"])
_TEST = _f("test", "a simple carrier test can tell them", ["test"], ["فحص"])
_CHOICE = _f("choice", "whether to test is their choice", ["choice", "decision", "decide", "up to you"],
             ["قرار", "خيار", "اختيار"])   # stems: also match قرارك, اختيارك, والقرار

TEMPLATE_FACTS = {
    "carrier_self": [
        _HEALTHY,
        _f("both_parents", "a child is only affected if both parents carry the same gene",
           ["both parents", "both of you", "both partners", "both the mother and"],
           ["كلا الوالدين", "الوالدين", "كلاكما", "الاب والام", "الام والاب"]),
    ],
    "xl_carrier_female": [
        _f("x_chromosome", "the gene is on the X chromosome", ["x chromosome", "x-chromosome"], ["كروموسوم x", "الصبغي x"]),
        _f("women_usually_well", "women who carry it are usually healthy or only mildly affected",
           ["healthy", "mild", "usually well"], ["بصحة", "خفيف", "سليم"]),
        _f("sons", "each son has a 50% chance of being affected", ["son"], ["ابن", "الذكور", "الاولاد"]),
        _f("daughters", "each daughter has a 50% chance of being a carrier", ["daughter"], ["ابنة", "البنت", "الاناث", "البنات"]),
        _f("partner_independent", "this does not depend on the partner's result",
           ["whatever", "regardless", "no matter", "not depend", "doesn't depend"],
           ["بغض النظر", "لا يعتمد", "مهما"]),
        _COUNSELLOR,
    ],
    "vus": [
        _f("uncertain", "the effect of this change is not yet known",
           ["uncertain", "not yet known", "not known", "unknown", "unclear"],
           ["غير محدد", "غير معروف", "لم يعرف", "غير واضح"]),
        _f("not_diagnosis", "it is not a diagnosis", ["not a diagnosis", "does not mean you have", "isn't a diagnosis"],
           ["ليس تشخيص", "ليست تشخيص", "لا يعني تشخيص", "لا تعني تشخيص", "لا يعد تشخيص", "لا تعد تشخيص"]),
        _COUNSELLOR,
    ],
    "ar_both_carriers": [
        _f("both_healthy", "both partners are healthy carriers", ["healthy"], ["بصحة", "سليم"]),
        _f("each_pregnancy", "the chances are the same in each pregnancy",
           ["each pregnancy", "every pregnancy"], ["كل حمل"]),
        _f("choice", "the choice is theirs", ["choice", "decision", "decide", "up to you"], ["قرار", "خيار", "اختيار"]),
        _COUNSELLOR,
    ],
    "relative_ar": [
        _f("carriers_healthy", "carriers are healthy", ["healthy"], ["بصحة", "سليم"]),
        _f("both_parents", "a child is only affected if both parents carry the same gene",
           ["both parents", "both partners"], ["كلا الوالدين", "الوالدين"]),
        _TEST, _CHOICE, _COUNSELLOR,
    ],
    "relative_general": [_TEST, _CHOICE, _COUNSELLOR],
    "relative_xl": [
        _f("x_chromosome", "the gene is on the X chromosome", ["x chromosome", "x-chromosome"], ["كروموسوم x", "الصبغي x"]),
        _f("family_side", "who else may carry it depends on which side of the family it comes from",
           ["side of the family", "which side"], ["جهة العائلة", "جهة"]),
        _f("men_affected", "women carriers are usually healthy, but men who carry it can be affected",
           [" men", " boys", " sons", " males"], ["الرجال", "الذكور"]),
        _TEST, _CHOICE, _COUNSELLOR,
    ],
    "no_shared": [
        _f("panel_limits", "no test covers every condition",
           ["no test", "not every", "doesn't cover", "does not cover", "all conditions", "every condition"],
           ["لا يغطي", "جميع الحالات", "كل الحالات"]),
    ],
}


def required_facts(key: str, gene_symbol: str | None, lang: str, level: str) -> list[dict]:
    """Facts the explanation for this finding must contain."""
    facts = list(TEMPLATE_FACTS.get(key, []))
    variants = TEMPLATES[key][lang]
    raw = variants.get(level) or variants["standard"]
    if gene_symbol and "{summary}" in raw:
        facts += knowledge.gene(gene_symbol).get("key_facts", [])
    return facts


LEVEL_GUIDE = {
    "simple": "very short sentences and everyday words, for someone who reads with difficulty; about 60 words",
    "standard": "clear everyday language; about 110 words",
    "detailed": "a little more biology (genes, copies, inheritance), still without jargon; about 170 words",
}

SYSTEM_PROMPT = """You are BioSentinel Family, a careful assistant that explains genetic screening results to couples and their families in the United Arab Emirates.

Strict rules:
- Use ONLY the facts given. Do not add medical facts, treatments or statistics.
- Numbers: you may only use the numbers listed in allowed_numbers. Never calculate new ones.
- Never tell anyone whether to marry, to have children, or to end a pregnancy. Do not rank options.
- A carrier is healthy. Never say the reader has or suffers from the condition.
- Be warm, respectful of family and faith, and free of blame or stigma.
- The reader is: {audience}. Address only them.
- Do not add greetings, blessings or religious phrases; start directly with the explanation.
- In Arabic, keep the gender forms of the reviewed explanation; never assume the reader is a man or a woman.
- Keep every fact from the reviewed explanation; do not drop any sentence's meaning.
- Write in {language}. Reading level: {level_guide}.
- Plain text only: no headings, no bullet points, no markdown.
- End with one sentence saying a genetic counsellor can help."""


def template_text(key: str, gene_symbol: str | None, lang: str, level: str, pct=None) -> str:
    """Fill a reviewed template. pct is the relative's chance, from risk_engine.relative_chance()."""
    variants = TEMPLATES[key][lang]
    text = variants.get(level) or variants["standard"]
    if gene_symbol:
        g = knowledge.gene(gene_symbol)
        text = text.format(gene=gene_symbol, condition=g["condition"][lang], summary=g["summary"][lang], pct=pct)
    return text


def _clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # drop any reasoning block
    text = re.sub(r"[*#_`]+", "", text)                          # drop markdown symbols
    text = re.sub(r"\s+", " ", text).strip()
    # drop a sentence repeated word for word (Gemma sometimes repeats the closing line)
    seen, kept = set(), []
    for sentence in re.split(r"(?<=[.!?؟])\s+", text):
        if sentence not in seen:
            seen.add(sentence)
            kept.append(sentence)
    return " ".join(kept)


def _ask_gemma(system: str, user: str) -> str:
    r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=TIMEOUT_S, json={
        "model": MODEL,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 600},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    r.raise_for_status()
    return r.json()["message"]["content"]


def explain(key: str, gene_symbol: str | None, lang: str = "en", level: str = "standard",
            allowed: set[float] | None = None, use_ai: bool = True, pct=None) -> dict:
    """Return {"text", "source", "problems"}; source is "ai" or "template"."""
    base = template_text(key, gene_symbol, lang, level, pct)
    allowed = allowed if allowed is not None else {0, 100}
    if not use_ai:
        return {"text": base, "source": "template", "problems": []}

    facts = {"finding": key, "allowed_numbers": sorted(allowed)}
    if gene_symbol:
        g = knowledge.gene(gene_symbol)
        facts.update(gene=gene_symbol, inheritance=g["inheritance"], condition=g["condition"][lang])
    if pct is not None:
        facts["relative_chance_pct"] = pct
    if key in ("ar_both_carriers", "no_shared"):
        audience = "a couple, reading their shared result together"
    elif key in RELATIVE_KEYS:
        audience = ("a RELATIVE of someone who was tested. The reader has NOT been tested and does not know "
                    "who sent this; never guess or mention who it was")
    else:
        audience = "ONE person reading their own private result; their partner cannot see it"
    system = SYSTEM_PROMPT.format(language="Arabic (Modern Standard, simple)" if lang == "ar" else "English",
                                  audience=audience,
                                  level_guide=LEVEL_GUIDE.get(level, LEVEL_GUIDE["standard"]))
    must = required_facts(key, gene_symbol, lang, level)
    must_list = "\n".join(f"- {f['say']}" for f in must)
    user = (f"FACTS: {facts}\n\nYour text MUST still say each of these points, even when it is short:\n{must_list}\n\n"
            f"Rewrite this reviewed explanation for the reader, keeping every fact and number exactly:\n{base}")
    try:
        text = _clean(_ask_gemma(system, user))
    except Exception as e:  # model not running, timeout, ... -> safe fallback
        return {"text": base, "source": "template", "problems": [f"ai unavailable: {type(e).__name__}"]}

    problems = guardrails.check(text, allowed, facts=must, lang=lang, reviewed=base)
    if problems:
        return {"text": base, "source": "template", "problems": problems}
    return {"text": text, "source": "ai", "problems": []}
