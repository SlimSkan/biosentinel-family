"""One door to Gemma 4, wherever it runs.

  - "gemini": Gemma 4 hosted by Google, through the Gemini API (needs GEMINI_API_KEY).
               This is what the free online demo uses: no GPU needed on our server.
  - "ollama": Gemma 4 running on this machine (a laptop, Colab, or an Azure GPU).

BSF_LLM chooses: "gemini", "ollama", or "auto" (default: gemini if a key is set, else ollama).

What is sent: only the prompt built by explainer.py / brief.py, which holds de-identified
facts (gene, condition, risk numbers, quiz answers). Never a name, contact or full result.
"""
import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("BSF_MODEL", "gemma4:e4b")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("BSF_GEMINI_MODEL", "gemma-4-26b-a4b-it")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT_S = float(os.environ.get("BSF_LLM_TIMEOUT", "120"))


def provider() -> str:
    choice = os.environ.get("BSF_LLM", "auto")
    if choice in ("gemini", "ollama"):
        return choice
    return "gemini" if GEMINI_KEY else "ollama"


def model_name() -> str:
    return GEMINI_MODEL if provider() == "gemini" else OLLAMA_MODEL


def ask(system: str, user: str, max_tokens: int = 700) -> str:
    """Send one prompt, return the model's text. Raises on any network or API error
    (the callers then fall back to reviewed text)."""
    if provider() == "gemini":
        data = _gemini(f"{system}

{user}", max_tokens)
        parts = data["candidates"][0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))
    r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=TIMEOUT_S, json={
        "model": OLLAMA_MODEL, "stream": False, "think": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    r.raise_for_status()
    return r.json()["message"]["content"]


def _gemini(prompt: str, max_tokens: int) -> dict:
    """Gemma 4 on the Gemini API. Gemma takes the instructions inside the user turn.
    Gemma 4 may reason before answering, and that reasoning uses output tokens too, so the
    budget is generous; the reasoning parts ("thought") are never shown."""
    r = httpx.post(f"{GEMINI_URL}/{GEMINI_MODEL}:generateContent", timeout=TIMEOUT_S,
                   headers={"x-goog-api-key": GEMINI_KEY},
                   json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                         "generationConfig": {"temperature": 0.2, "maxOutputTokens": max(4096, max_tokens * 4)}})
    r.raise_for_status()
    return r.json()


def probe() -> dict:
    """Shape of one tiny Gemini reply (finish reason, part kinds and lengths, token use).
    No content and no key: safe to show for diagnosis."""
    if provider() != "gemini":
        return {"provider": provider()}
    try:
        d = _gemini("Reply with the single word: OK", 50)
        c = d["candidates"][0]
        return {"finish": c.get("finishReason"), "usage": d.get("usageMetadata", {}),
                "parts": [{"thought": bool(p.get("thought")), "chars": len(p.get("text", ""))}
                          for p in c.get("content", {}).get("parts", [])]}
    except Exception as e:
        return {"error": type(e).__name__, "detail": str(getattr(e, "response", "") and e.response.status_code)}


def status() -> dict:
    """Can we reach the model? Used by /api/health (and to warm it before a demo)."""
    try:
        if provider() == "gemini":
            r = httpx.get(f"{GEMINI_URL}/{GEMINI_MODEL}", headers={"x-goog-api-key": GEMINI_KEY}, timeout=8)
            return {"reachable": r.status_code == 200, "model_present": r.status_code == 200,
                    **({} if r.status_code == 200 else {"error": f"HTTP {r.status_code}"})}
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        names = [m["name"] for m in r.json().get("models", [])]
        return {"reachable": True, "model_present": OLLAMA_MODEL in names}
    except Exception as e:
        return {"reachable": False, "error": type(e).__name__}
