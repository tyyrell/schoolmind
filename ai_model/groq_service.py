"""
SchoolMind AI — Groq integration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Wraps the Groq chat completions API with:
  • Timeout (20 s hard limit)
  • Retry on transient network errors (1 retry, 1 s backoff)
  • Graceful fallback to the local Nour engine on any failure
  • Strict output size limits (max_tokens capped at 300)
  • Safe error logging (NEVER logs the API key)
  • System prompt is built server-side, not user-controllable

The API key is read from the environment variable GROQ_API_KEY.
If it's missing, `call_groq_ai` returns None and the caller falls back
to the local rule-based engine.
"""
import os
import json
import time
import logging
import urllib.request
import urllib.error

log = logging.getLogger("schoolmind.groq")

# ─────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────
GROQ_ENDPOINT  = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL     = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_TIMEOUT   = 20        # hard cap in seconds
MAX_TOKENS     = 320       # allow 3-6 short sentences
MAX_USER_CHARS = 1000      # user message cap before we send it
MAX_HISTORY    = 8         # slightly more context for better continuity

# Cached flag — avoid repeated os.environ lookups
_API_KEY_CACHE = None
_API_KEY_CHECKED = False


def _get_api_key():
    """Fetch API key from env once per process; never log it."""
    global _API_KEY_CACHE, _API_KEY_CHECKED
    if _API_KEY_CHECKED:
        return _API_KEY_CACHE
    key = os.environ.get("GROQ_API_KEY", "").strip()
    _API_KEY_CACHE = key if key else None
    _API_KEY_CHECKED = True
    if _API_KEY_CACHE:
        log.info("Groq API key loaded (len=%d). Model=%s",
                 len(_API_KEY_CACHE), GROQ_MODEL)
    else:
        log.info("Groq API key not set; using local fallback.")
    return _API_KEY_CACHE


def is_available():
    """Public helper: is Groq usable right now?"""
    return _get_api_key() is not None


# ─────────────────────────────────────────────────────────────────────────
# System prompts — kept server-side, never user-controlled
# ─────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT_AR = (
    "أنت 'نور'، رفيق نفسي ذكي ودافئ للطلاب (12-18 سنة). تتحدث مثل صديق متفهم لا مثل معالج رسمي.\n\n"
    "أسلوبك:\n"
    "- تحدّث بالعربية الفصحى أو باللهجة التي يستخدمها الطالب (عامية أردنية، فلسطينية، خليجية... طبّق نفس اللهجة).\n"
    "- طبيعي وبسيط، لا تستخدم كلمات معقدة أو طبية.\n"
    "- أظهر تعاطفاً حقيقياً قبل إعطاء النصيحة (اعترف بالشعور أولاً).\n"
    "- استخدم الأسئلة المفتوحة لتفهم أكثر بدلاً من الاستنتاج السريع.\n\n"
    "حدود مطلقة لا تتجاوزها:\n"
    "1. ردّك قصير (3-6 جمل كحد أقصى). لا تكتب فقرات طويلة.\n"
    "2. لا تشخّص أي حالة نفسية، ولا تسمّي اضطراباً معيناً (اكتئاب، قلق عام، صدمة...)، ولا تقترح دواءً.\n"
    "3. إذا ذكر الطالب إيذاءً للنفس أو انتحاراً أو أذى من شخص آخر: اعترف بالألم، وأخبره فوراً بالاتصال بخط الطوارئ 911 في الأردن، أو التحدث مع شخص بالغ موثوق الآن. لا تؤجّل هذه الخطوة.\n"
    "4. لا تعد بسرية مطلقة. اذكر بوضوح أن المرشد قد يُبلَّغ عند وجود خطر على حياته.\n"
    "5. لا تحكم، لا تلقّن، لا تعِظ. أنت مستمع لا واعظ.\n"
    "6. إيموجي واحد كحد أقصى إذا ناسب الموقف، وليس كل رد.\n"
    "7. اختم بسؤال مفتوح ليكمل الطالب الحديث (إلا في حالة الطوارئ، حينها ركّز على سلامته).\n"
    "8. إذا سألك الطالب عن معلومات واقعية غير متعلقة بمشاعره (مادة دراسية، سؤال عام)، أجب بإيجاز ثم اسأله كيف يشعر."
)

SYSTEM_PROMPT_EN = (
    "You are 'Nour', a smart warm mental-health companion for students aged 12-18. Talk like an understanding friend, not a formal therapist.\n\n"
    "Your style:\n"
    "- Use the same language register the student uses (formal English, casual, slang — match their vibe).\n"
    "- Natural and simple. No complex or clinical words.\n"
    "- Show real empathy BEFORE giving advice (acknowledge the feeling first).\n"
    "- Use open-ended questions to understand more, rather than jumping to conclusions.\n\n"
    "Strict boundaries — never cross:\n"
    "1. Keep replies short (3-6 sentences max). No long paragraphs.\n"
    "2. Never diagnose any condition, never name a disorder (depression, GAD, PTSD...), never suggest medication.\n"
    "3. If student mentions self-harm, suicide, or being hurt by someone: acknowledge the pain, then IMMEDIATELY tell them to call 911 (Jordan) or talk to a trusted adult NOW. Don't delay this step.\n"
    "4. Never promise absolute confidentiality. Clearly state that the counselor may be notified if there's risk to their life.\n"
    "5. No judgment, no lecturing, no preaching. You listen, you don't moralize.\n"
    "6. Max one emoji when it fits — not every reply.\n"
    "7. End with an open question so the student keeps talking (except in emergencies, then focus on safety).\n"
    "8. If the student asks a factual question unrelated to feelings (schoolwork, general), answer briefly then ask how they're feeling."
)


def _build_system_prompt(lang, emotion=None):
    base = SYSTEM_PROMPT_AR if lang == "ar" else SYSTEM_PROMPT_EN
    if emotion and emotion != "neutral":
        hint_ar = f"\nالحالة العاطفية المكتشفة: {emotion}. ضع ذلك بعين الاعتبار."
        hint_en = f"\nDetected emotion: {emotion}. Take this into account."
        base += hint_ar if lang == "ar" else hint_en
    return base


# ─────────────────────────────────────────────────────────────────────────
# Main API function
# ─────────────────────────────────────────────────────────────────────────
def call_groq_ai(user_message, lang="ar", emotion=None, history=None):
    """
    Send a user message to Groq and return the assistant reply string.

    Returns:
        str — reply text on success
        None — on any error (caller should fall back to local engine)

    Parameters:
        user_message : str   — the user's text (will be trimmed to MAX_USER_CHARS)
        lang         : 'ar'|'en'
        emotion      : str   — detected emotion tag (optional, informs system prompt)
        history      : list  — [{role: 'user'|'assistant', content: str}, ...]
    """
    api_key = _get_api_key()
    if not api_key:
        return None  # Falls back to local

    if not user_message or not isinstance(user_message, str):
        return None

    # Input size guard
    user_message = user_message.strip()[:MAX_USER_CHARS]
    if not user_message:
        return None

    lang = lang if lang in ("ar", "en") else "ar"

    # Build messages array
    messages = [{"role": "system", "content": _build_system_prompt(lang, emotion)}]

    if history:
        # Only keep last MAX_HISTORY turns, filter to valid roles, cap content
        for turn in history[-MAX_HISTORY:]:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content[:800]})

    messages.append({"role": "user", "content": user_message})

    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": False,
    }).encode("utf-8")

    return _post_with_retry(payload, api_key)


def _post_with_retry(payload, api_key):
    """Try once, retry once on timeout or 5xx. Returns text or None."""
    for attempt in (1, 2):
        try:
            return _post(payload, api_key)
        except urllib.error.HTTPError as e:
            status = e.code
            # 5xx is transient — retry; 4xx is permanent — abort
            body = ""
            try:
                body = e.read().decode("utf-8", "ignore")[:200]
            except Exception:
                pass
            if status >= 500 and attempt == 1:
                log.warning("Groq HTTP %s (attempt %d) body=%s",
                            status, attempt, body)
                time.sleep(1.0)
                continue
            log.warning("Groq HTTP %s (final) body=%s", status, body)
            return None
        except urllib.error.URLError as e:
            # Network / DNS / TLS error — typically transient
            reason = getattr(e, "reason", str(e))
            log.warning("Groq URL error (attempt %d): %s", attempt, reason)
            if attempt == 1:
                time.sleep(1.0)
                continue
            return None
        except TimeoutError:
            log.warning("Groq timeout (attempt %d)", attempt)
            if attempt == 1:
                time.sleep(1.0)
                continue
            return None
        except Exception as e:
            # Don't leak the key or payload in the log
            log.error("Groq unexpected error: %s: %s", type(e).__name__, str(e)[:120])
            return None
    return None


def _post(payload, api_key):
    """Actual POST. Raises on error; returns string on success."""
    req = urllib.request.Request(
        GROQ_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "Authorization": "Bearer " + api_key,
            "User-Agent":    "SchoolMindAI/21 (Flask)",
            "Accept":        "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=GROQ_TIMEOUT) as resp:
        raw = resp.read()
        if not raw:
            log.warning("Groq empty response")
            return None
        try:
            data = json.loads(raw.decode("utf-8", "ignore"))
        except (ValueError, UnicodeDecodeError) as e:
            log.warning("Groq JSON parse failed: %s", e)
            return None

    # Extract message defensively
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        log.warning("Groq response missing choices")
        return None

    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
        return None

    content = msg.get("content", "")
    if not isinstance(content, str):
        return None

    content = content.strip()
    if not content:
        return None

    # Final safety cap — never return absurdly long text to the user
    return content[:1500]
