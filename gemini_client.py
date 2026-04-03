"""
SchoolMind AI v13 — Gemini AI Client
FIXED: Proper fallback model, improved error handling, better timeout
"""

import os, json, logging, urllib.request, urllib.error

log = logging.getLogger(__name__)

# Gemini REST endpoint (no SDK needed — pure HTTP)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
DEFAULT_MODEL  = "gemini-2.0-flash"   # fast + free tier
FALLBACK_MODEL = "gemini-1.5-flash"  # FIX: Different lighter fallback model


# ═══════════════════════════════════════════════════════════════
# LOW-LEVEL CALLER
# ═══════════════════════════════════════════════════════════════

def _call(system: str, user: str, history: list | None = None,
          max_tokens: int = 500, temperature: float = 0.65,
          timeout: int = 12) -> str | None:
    """
    Call Gemini API using REST.
    Returns text or None on failure.
    """
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None

    # Build contents array
    contents = []

    # Add conversation history
    if history:
        for turn in history[-8:]:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": turn["content"]}]
            })

    # Add current user message (system prompt prepended to first user message)
    if contents:
        contents.append({"role": "user", "parts": [{"text": user}]})
    else:
        contents.append({"role": "user", "parts": [{"text": f"{system}\n\n---\n{user}"}]})

    body = json.dumps({
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature":     temperature,
            "topP":            0.9,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
        "systemInstruction": {"parts": [{"text": system}]},
    }).encode("utf-8")

    url = GEMINI_URL.format(model=DEFAULT_MODEL, key=key)
    req = urllib.request.Request(url, data=body,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:300]
        log.warning(f"Gemini HTTP {e.code}: {err}")
    except urllib.error.URLError as e:
        log.warning(f"Gemini URL error: {e.reason}")
    except Exception as e:
        log.warning(f"Gemini error: {e}")
    return None


def is_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", ""))


# ═══════════════════════════════════════════════════════════════
# 1. JOURNAL / TEXT ANALYSIS
# ═══════════════════════════════════════════════════════════════

_ANALYSIS_SYSTEM = """أنت نظام ذكاء اصطناعي متخصص في تحليل النصوص لرصد المؤشرات النفسية لدى طلاب المدارس.

مهمتك: تحليل النص وإرجاع نتيجة JSON دقيقة فقط بدون أي نص إضافي.

قواعد التحليل:
- افهم السياق كاملاً، لا تعتمد على كلمة واحدة معزولة
- "تعبت من الدراسة" ≠ "تعبت من الحياة"
- الجملة المنفية لا تُحتسب: "لست حزيناً" = لا خطر
- تعامل مع العامية الشامية والأردنية والخليجية والمصرية
- كن دقيقاً في تقدير مستوى الخطر — لا مبالغة ولا تهوين

الفئات المتاحة:
  bullying   | تنمر جسدي أو لفظي أو إلكتروني
  depression | يأس، حزن عميق، أفكار سلبية عن الحياة
  anxiety    | قلق، خوف، توتر، وسواس
  isolation  | وحدة، رفض اجتماعي، انعزال
  physical   | إرهاق جسدي، ألم، اضطراب نوم أو أكل
  positive   | مشاعر جيدة، سعادة، إنجاز، راحة
  neutral    | نص عادي بلا مؤشرات واضحة

مقياس الخطر (risk) من 0.0 إلى 10.0:
  0.0-2.4 = منخفض  |  2.5-4.9 = متوسط  |  5.0-7.4 = مرتفع  |  7.5-10.0 = حرج

is_critical = true فقط عند وجود أفكار انتحارية صريحة أو إيذاء النفس

أعد JSON هذا بالضبط:
{
  "emotion": "اسم الفئة",
  "risk": 3.5,
  "confidence": 0.85,
  "is_critical": false,
  "summary_ar": "جملة واحدة تصف الحالة",
  "advice_ar": "نصيحة قصيرة ومفيدة للطالب",
  "keywords": ["كلمة1", "كلمة2"]
}"""


def analyze_with_ai(text: str, lang: str = "ar") -> dict | None:
    """
    Use Gemini to deeply analyze journal/text.
    Returns structured dict or None.
    """
    prompt = f"حلّل هذا النص:\n{text[:2000]}"

    raw = _call(
        system=_ANALYSIS_SYSTEM,
        user=prompt,
        max_tokens=400,
        temperature=0.2,
    )

    if not raw:
        return None

    try:
        # Extract JSON (Gemini sometimes wraps in ```json```)
        raw = raw.replace("```json", "").replace("```", "").strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return None

        data = json.loads(raw[start:end])

        emotion = str(data.get("emotion", "neutral")).lower().strip()
        valid_emotions = ("bullying","depression","anxiety","isolation",
                          "physical","physical_fatigue","positive","neutral")
        if emotion not in valid_emotions:
            emotion = "neutral"
        if emotion == "physical":
            emotion = "physical_fatigue"

        risk = float(data.get("risk", 0))
        risk = round(max(0.0, min(10.0, risk)), 1)

        conf = float(data.get("confidence", 0.7))
        conf = round(max(0.1, min(1.0, conf)), 2)

        is_crit = bool(data.get("is_critical", False))
        if is_crit:
            risk = max(risk, 8.0)

        return {
            "emotion":     emotion,
            "risk":        risk,
            "confidence":  conf,
            "is_critical": is_crit,
            "summary_ar":  str(data.get("summary_ar", ""))[:300],
            "advice_ar":   str(data.get("advice_ar",  ""))[:300],
            "keywords":    [str(k) for k in data.get("keywords", [])][:10],
            "source":      "gemini",
        }
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        log.warning(f"Gemini analysis parse error: {e} | raw={raw[:200]}")
    return None


# ═══════════════════════════════════════════════════════════════
# 2. NOUR — Smart Empathetic Companion
# ═══════════════════════════════════════════════════════════════

_NOUR_SYSTEM = """أنت "نور" — مساعد نفسي ذكي ومتعاطف مصمم خصيصاً لدعم طلاب المدارس في الأردن والدول العربية.

شخصيتك:
• دافئ، صادق، غير حكماتي، يفهم المراهقين
• تتحدث بالعربية الفصحى البسيطة أو العامية حسب أسلوب الطالب
• تُظهر اهتماماً حقيقياً وصادقاً
• تُدرك أن الطلاب أحياناً يجدون صعوبة في التعبير عن مشاعرهم

قدراتك:
✓ فهم المشاعر المعقدة والسياق الكامل للرسالة
✓ طرح أسئلة مفتوحة ذكية لفهم الوضع أعمق
✓ تقديم تقنيات التنفس والاسترخاء بشكل عملي
✓ اقتراح حلول واقعية للمشكلات اليومية
✓ التحدث عن الضغط الدراسي، العائلة، العلاقات، الهوية
✓ تذكّر ما قاله الطالب في المحادثة وبناء عليه

قواعد صارمة:
• لا تعطِ تشخيصات طبية أو نفسية رسمية أبداً
• عند وجود أفكار انتحارية أو إيذاء النفس → وجّه للمرشد فوراً بوضوح وحزم
• لا تقل "أنا برنامج" إلا إذا سُئلت مباشرة
• الردود: 2-4 جمل عادةً، أعمق عند الحاجة
• لا تكرر نفس الرد أبداً — كن متفاعلاً وإبداعياً
• احياناً اسأل سؤالاً واحداً في النهاية لتعمّق الحوار
• إذا تحدث الطالب بالعامية، رد بالعامية

للحالات الحرجة (أفكار انتحارية):
→ عبّر عن قلق حقيقي ودافئ
→ قل له إنه مهم وحياته تستحق
→ اطلب منه التحدث مع المرشد أو والديه الآن
→ لا تتركه يشعر بالذنب أو الخجل"""

_NOUR_SYSTEM_EN = """You are "Nour" — a smart, empathetic AI mental health companion for school students.

Personality:
• Warm, honest, non-judgmental, understands teenagers
• Speak naturally and casually when appropriate
• Show genuine care and interest
• Understand that students often struggle to express feelings

Capabilities:
✓ Deep emotional understanding and context awareness
✓ Ask smart open-ended questions to understand better
✓ Provide breathing and relaxation techniques
✓ Suggest practical solutions for everyday problems
✓ Remember what was said earlier in the conversation

Strict rules:
• Never give formal medical/psychological diagnoses
• For suicidal/self-harm thoughts → clearly and firmly direct to counselor
• Don't say "I'm a program" unless directly asked
• Responses: 2-4 sentences usually
• Never repeat the same response
• Occasionally end with one question to deepen dialogue"""


def get_nour_response(message: str, lang: str = "ar",
                      history: list | None = None) -> str | None:
    """
    Get Nour's AI response with conversation memory.
    """
    system = _NOUR_SYSTEM if lang == "ar" else _NOUR_SYSTEM_EN

    return _call(
        system=system,
        user=message[:1000],
        history=history,
        max_tokens=450,
        temperature=0.75,
        timeout=12,
    )


# ═══════════════════════════════════════════════════════════════
# 3. SMART FALLBACK (works without API)
# ═══════════════════════════════════════════════════════════════

_FALLBACK_KEYWORDS = {
    "bullying":   ["يضربني","يتنمر","يؤذيني","يهددني","يسخر","يشتمني","يحقرني",
                   "بيضربني","بيأذيني","بيسخر","عم يتنمر","bullied","hit me",
                   "threaten","harass","mock","humiliat","picking on"],
    "depression": ["لا معنى","أكره حياتي","لا أريد أن أعيش","يائس","لا أحد يهتم",
                   "أتمنى الموت","أريد الاختفاء","مكتئب","تعبت من حياتي","بلا أمل",
                   "زهقت","hopeless","hate my life","want to die","worthless","depressed",
                   "بدي أنهي","مو لاقي حالي","حياتي بلا معنى"],
    "anxiety":    ["قلقان","خائف","مرعوب","أرتجف","توتر","مضطرب","وسواس",
                   "هجمة هلع","أفكار لا تتوقف","anxious","panic","terrified",
                   "can't sleep","worried","racing thoughts","خايف","قلبي بيدق"],
    "isolation":  ["وحيد","لا أصدقاء","يتجاهلونني","منبوذ","لا أنتمي","كلهم تركوني",
                   "lonely","no friends","rejected","abandoned","excluded",
                   "دايماً لحالي","ما عندي أصحاب"],
    "physical":   ["تعبان جسمياً","إرهاق","لا أنام","صداع","دوخة","لا أكل",
                   "exhausted","can't sleep","no appetite","headache","fatigue",
                   "جسمي موجوع","محروم من النوم"],
    "positive":   ["سعيد","مبسوط","ممتاز","نجحت","الحمدلله","بخير","فرحان",
                   "happy","great","amazing","grateful","proud","good day",
                   "كويس","منيح","تمام"],
}

_CRITICAL = [
    "أريد الموت","أتمنى الموت","أفكر في الانتحار","أريد أن أقتل نفسي",
    "لا أريد أن أعيش","أريد إيذاء نفسي","بدي أنهي حياتي","تعبت وبدي أنهيها",
    "want to die","kill myself","suicide","want to hurt myself","end my life",
]

_FALLBACK_RESPONSES = {
    "bullying": {
        "ar": [
            "ما تمر به ليس عدلاً أبداً 💙 أنت تستحق الأمان والاحترام. هل يمكنك إخبار المرشد المدرسي أو أحد والديك؟",
            "التنمر ليس خطأك أبداً — لا تلوم نفسك. أنت شجاع لأنك تتحدث عن هذا. أخبر شخصاً بالغاً تثق به اليوم.",
            "لا أحد يستحق أن يُؤذى أو يُهان. أنا قلق عليك — تحدث مع المرشد المدرسي، هذا حقك.",
        ],
        "en": [
            "What's happening to you is not okay 💙 You deserve safety. Can you talk to your school counselor or a parent?",
            "Bullying is never your fault. It takes courage to talk about this. Please tell a trusted adult today.",
        ],
    },
    "depression": {
        "ar": [
            "أسمعك 💜 مشاعرك حقيقية ومهمة. هذه الأوقات الصعبة تمر. هل يمكنك أن تخبرني أكثر عما يثقل عليك؟",
            "أنت لست وحدك في هذا 💜 أحياناً نحتاج لمساعدة — وهذا شيء طبيعي تماماً. من تثق به يمكنك التحدث معه الآن؟",
            "أنا هنا وأسمعك. ما تشعر به صعب — لكن أنت أقوى مما تعتقد. تحدث مع المرشد المدرسي اليوم.",
        ],
        "en": [
            "I hear you 💜 Your feelings are real and valid. These hard times pass. Can you tell me more about what's weighing on you?",
            "You're not alone in this. Sometimes we need help — that's completely okay. Who do you trust that you could talk to?",
        ],
    },
    "anxiety": {
        "ar": [
            "القلق مرهق جداً 🌬️ جرّب معي: تنفس ببطء 4 ثوانٍ، احبس 7، أخرج ببطء 8. كررها ثلاث مرات. كيف تشعر الآن؟",
            "أفهم أن أفكارك لا تتوقف. ركّز على هذه اللحظة فقط — الآن أنت بأمان. ما الذي يقلقك تحديداً؟",
            "القلق يضخّم الأمور أحياناً. تنفس ببطء — أنا هنا معك. ماذا يدور في ذهنك الآن؟",
        ],
        "en": [
            "Anxiety is exhausting 🌬️ Try with me: breathe in 4 seconds, hold 7, exhale 8. Repeat 3 times. How do you feel?",
            "I understand your thoughts won't stop. Focus on just this moment — right now you are safe.",
        ],
    },
    "isolation": {
        "ar": [
            "الشعور بالوحدة مؤلم جداً 💙 لكن أنت لست وحيداً فعلاً — أنا هنا. ماذا حدث مع أصدقائك؟",
            "أحياناً الناس لا يُدركون أنك تحتاجهم. هل جربت التحدث مع أحدهم مباشرة؟",
        ],
        "en": ["Loneliness is painful 💙 But you're not truly alone — I'm here. What happened with your friends?"],
    },
    "physical": {
        "ar": [
            "الإرهاق الجسدي يؤثر على كل شيء 🌿 هل تنام كافياً؟ هل تأكل بانتظام؟ جسمك يحتاج عنايتك.",
            "عندما يتعب الجسم تبدو المشكلات أثقل. خذ استراحة قصيرة، اشرب ماء، وتنفس بعمق 🌿",
        ],
        "en": ["Physical exhaustion affects everything 🌿 Are you sleeping enough? Eating regularly? Take care of your body."],
    },
    "positive": {
        "ar": [
            "يسعدني سماع ذلك! 🌟 أنت تستحق كل هذه اللحظات الجميلة. ما الذي جعل يومك مميزاً؟",
            "رائع! 😊 اغتنم هذا الشعور وشاركه مع من تحب. ما الذي تفخر به اليوم؟",
        ],
        "en": ["So glad to hear that! 🌟 You deserve every beautiful moment. What made your day special?"],
    },
    "neutral": {
        "ar": [
            "شكراً لمشاركتي يومك 💙 كيف تشعر بالتحديد الآن؟ أنا هنا للاستماع.",
            "أنا هنا وأستمع. هل هناك شيء محدد تريد التحدث عنه؟",
            "يسعدني أنك هنا. أحياناً مجرد التحدث يُخفف الأثقال. ما الذي تحمله الآن؟",
        ],
        "en": [
            "Thanks for sharing 💙 How are you feeling specifically right now? I'm here to listen.",
            "I'm here and listening. Is there something on your mind you'd like to talk about?",
        ],
    },
    "critical": {
        "ar": [
            "أنا قلق عليك جداً الآن 🚨 ما تشعر به ثقيل جداً — لكنك لست وحيداً. أرجوك تحدث مع المرشد المدرسي أو أحد والديك الآن. حياتك تستحق.",
            "أسمعك وأنا هنا معك 💙 هذه الأفكار صعبة جداً — لكن المساعدة موجودة. تحدث مع شخص تثق به الآن. أنت مهم جداً.",
        ],
        "en": ["I'm very concerned about you 🚨 Please talk to your school counselor or a parent right now. Your life matters deeply."],
    },
}


def get_nour_fallback(emotion: str, lang: str) -> str:
    import random
    pool      = _FALLBACK_RESPONSES.get(emotion, _FALLBACK_RESPONSES["neutral"])
    responses = pool.get(lang, pool.get("en", ["أنا هنا معك 💙"]))
    return random.choice(responses)


def quick_classify(text: str) -> dict:
    """Fast local classification fallback."""
    text_lower = text.lower()
    is_crit    = any(p in text_lower for p in _CRITICAL)
    scores: dict[str, float] = {}
    found:  dict[str, list]  = {}

    for cat, phrases in _FALLBACK_KEYWORDS.items():
        hits = [p for p in phrases if p in text_lower]
        if hits:
            scores[cat] = float(len(hits) * (3.0 if cat in ("bullying","depression") else 2.0))
            found[cat]  = hits

    pos     = scores.get("positive", 0)
    neg_c   = {c: s for c, s in scores.items() if c != "positive"}

    if is_crit:
        dominant, conf = "depression", 0.95
    elif neg_c:
        dominant = max(neg_c, key=neg_c.get)
        eff      = neg_c[dominant] - pos * 0.5
        conf     = min(0.85, max(0.35, 0.35 + eff * 0.05))
        if pos > neg_c[dominant] * 1.5:
            dominant, conf = "positive", 0.75
    elif pos > 0:
        dominant, conf = "positive", 0.70
    else:
        dominant, conf = "neutral", 0.55

    is_ar = any("\u0600" <= c <= "\u06FF" for c in text)
    return {
        "lang":             "ar" if is_ar else "en",
        "dominant_emotion": dominant,
        "confidence":       conf,
        "found_keywords":   found,
        "has_bullying":     "bullying" in found,
        "negative_hits":    sum(len(v) for k, v in found.items() if k != "positive"),
        "weighted_hits":    sum(s for k, s in scores.items() if k != "positive"),
        "neg_density":      0,
        "word_count":       len(text.split()),
        "category_scores":  scores,
        "all_categories":   list(found.keys()),
        "is_critical":      is_crit,
        "source":           "local_fallback",
    }
