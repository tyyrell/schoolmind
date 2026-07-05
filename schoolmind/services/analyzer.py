from .ai_safety import signal_level_summary

WATCH_WORDS = {
    "pressure", "stress", "overwhelmed", "tired", "alone", "heavy", "lost", "scared",
    "قلق", "ضغط", "تعبان", "مرهق", "وحيد", "خايف", "مضغوط", "مش قادر",
}
SUPPORT_WORDS = {
    "panic", "hopeless", "trapped", "can't cope", "cannot cope", "breaking", "bully", "bullied",
    "هلع", "يائس", "محاصر", "تنمر", "متنمر", "انهرت", "مو قادر", "مش قادر اتحمل",
}
URGENT_WORDS = {
    "danger", "emergency", "unsafe", "crisis", "hurt myself", "end it",
    "خطر", "طوارئ", "غير آمن", "ازمة", "أؤذي نفسي", "اذي نفسي", "انهي حياتي",
}

DOMAIN_LABELS = {
    "mood": "Mood stability",
    "calm": "Stress load",
    "sleep": "Sleep recovery",
    "belonging": "Belonging",
    "study_load": "Study pressure",
    "focus": "Focus",
    "safety": "Safety perception",
    "support": "Support access",
}

RECOMMENDATIONS = {
    "mood": "Start with a short supportive check-in and one manageable task for today.",
    "calm": "Reduce immediate pressure, name the top stressor, and create a 20-minute recovery block.",
    "sleep": "Review workload, sleep routine, and late-night study pressure before adding more tasks.",
    "belonging": "Look for isolation, peer conflict, or classroom belonging needs before giving generic advice.",
    "study_load": "Build a simple catch-up plan with one priority, one deadline, and one person to ask for help.",
    "focus": "Use smaller work intervals, remove one distraction, and confirm the student understands the next step.",
    "safety": "Use the school-approved human escalation protocol and document only operational facts.",
    "support": "Make the support path explicit: who to contact, when, and what the student can ask for.",
}


def analyze_student_signal(text="", mood=None, stress=None, energy=None):
    raw = normalize(text)
    score = 62
    hits = []

    for word in WATCH_WORDS:
        if normalize(word) in raw:
            score -= 7
            hits.append(word)
    for word in SUPPORT_WORDS:
        if normalize(word) in raw:
            score -= 15
            hits.append(word)
    for word in URGENT_WORDS:
        if normalize(word) in raw:
            score -= 30
            hits.append(word)

    if mood is not None:
        score += (int(mood) - 3) * 7
    if stress is not None:
        score -= (int(stress) - 3) * 8
    if energy is not None:
        score += (int(energy) - 3) * 4

    level = level_for_score(score, urgent_override=bool(set(hits) & URGENT_WORDS))
    summary = build_summary(level, hits)
    return {"score": clamp_score(score), "level": level, "summary": summary, "signals": hits[:6]}


def analyze_wellbeing_assessment(values):
    mood = safe_int(values.get("mood"), 1, 5, 3)
    stress = safe_int(values.get("stress"), 1, 5, 3)
    sleep = safe_int(values.get("sleep"), 1, 5, 3)
    belonging = safe_int(values.get("belonging"), 1, 5, 3)
    study_pressure = safe_int(values.get("study_pressure"), 1, 5, 3)
    focus = safe_int(values.get("focus"), 1, 5, 3)
    safety = safe_int(values.get("safety"), 1, 5, 3)
    support_access = safe_int(values.get("support_access"), 1, 5, 3)

    score = 58
    score += (mood - 3) * 6
    score -= (stress - 3) * 7
    score += (sleep - 3) * 5
    score += (belonging - 3) * 6
    score -= (study_pressure - 3) * 6
    score += (focus - 3) * 4
    score += (safety - 3) * 9
    score += (support_access - 3) * 5

    domain_health = {
        "mood": mood,
        "calm": 6 - stress,
        "sleep": sleep,
        "belonging": belonging,
        "study_load": 6 - study_pressure,
        "focus": focus,
        "safety": safety,
        "support": support_access,
    }
    primary_need = min(domain_health, key=domain_health.get)
    urgent_override = safety <= 1
    support_override = safety <= 2 or (stress >= 5 and mood <= 2)
    level = level_for_score(score, urgent_override=urgent_override, support_override=support_override)
    recommendation = RECOMMENDATIONS[primary_need]
    if level == "steady":
        recommendation = "Keep the routine visible: one check-in, one goal, and one support path the student can name."

    return {
        "mood": mood,
        "stress": stress,
        "sleep": sleep,
        "belonging": belonging,
        "study_pressure": study_pressure,
        "focus": focus,
        "safety": safety,
        "support_access": support_access,
        "score": clamp_score(score),
        "level": level,
        "primary_need": primary_need,
        "primary_need_label": DOMAIN_LABELS[primary_need],
        "recommendation": recommendation,
        "domain_health": domain_health,
    }


def support_plan_from_assessment(assessment):
    focus_area = assessment["primary_need_label"]
    need = assessment["primary_need"]
    next_steps = {
        "mood": "Choose one trusted adult and one low-pressure task for the next school day.",
        "calm": "Create a 20-minute reset plan before the next demanding class or assignment.",
        "sleep": "Move one task earlier, reduce late-night work pressure, and review sleep barriers.",
        "belonging": "Identify one safe peer or staff connection and plan a short check-in.",
        "study_load": "Break the heaviest assignment into three small steps and confirm the first deadline.",
        "focus": "Use a 15-minute focus block with a clear finish line and one removed distraction.",
        "safety": "Follow the school escalation protocol immediately and keep a human reviewer attached.",
        "support": "Write down the support owner, contact path, and when the student should use it.",
    }
    cadence = "Daily review" if assessment["level"] in {"support", "urgent"} else "Weekly review"
    if assessment["level"] == "watch":
        cadence = "Two check-ins this week"
    return {
        "focus_area": focus_area,
        "goal": f"Improve {focus_area.lower()} without labeling the student.",
        "next_step": next_steps[need],
        "cadence": cadence,
    }


def companion_reply(message, signal):
    if signal["level"] == "urgent":
        return "Nour created an urgent human-review indicator. Use the school-approved support path now; this tool is not an emergency service or final decision-maker."
    if signal["level"] == "support":
        return "Nour saved a support indicator for human review. A useful next step is to name the hardest part and ask for one concrete support action."
    if signal["level"] == "watch":
        return "Nour noticed a watch indicator. Try one small reset: write the next task, choose a short start, and ask early if pressure stays heavy."
    return "Nour sees a steady indicator. Keep one small goal visible and check in again if the day changes."


def build_student_snapshot(journals, checkins, assessments, plans):
    latest_assessment = assessments[0] if assessments else None
    latest_checkin = checkins[0] if checkins else None
    open_plan_count = len([plan for plan in plans if plan["status"] == "active"])
    if latest_assessment:
        focus = DOMAIN_LABELS.get(latest_assessment["primary_need"], latest_assessment["primary_need"])
        headline = f"{focus} is the current focus area."
        score = latest_assessment["score"]
        level = latest_assessment["risk_level"]
    elif latest_checkin:
        headline = "Your latest check-in is saved."
        score = latest_checkin["mood"] * 12 + (6 - latest_checkin["stress"]) * 8 + latest_checkin["energy"] * 8
        level = latest_checkin["risk_level"]
    else:
        headline = "Start with a check-in or wellbeing scan."
        score = 0
        level = "steady"
    return {
        "headline": headline,
        "score": min(99, max(0, int(score or 0))),
        "level": level,
        "journal_count": len(journals),
        "checkin_count": len(checkins),
        "plan_count": open_plan_count,
    }


def build_case_brief(student, journals, checkins, assessments, events, plans):
    latest_assessment = assessments[0] if assessments else None
    latest_event = events[0] if events else None
    focus = "No assessment focus yet"
    recommendation = "Ask the student to complete the wellbeing scan before the next review."
    level = "steady"
    if latest_assessment:
        focus = DOMAIN_LABELS.get(latest_assessment["primary_need"], latest_assessment["primary_need"])
        recommendation = latest_assessment["recommendation"]
        level = latest_assessment["risk_level"]
    elif latest_event:
        focus = latest_event["title"]
        recommendation = latest_event["detail"]
        level = latest_event["risk_level"]
    return {
        "student_name": student["name"],
        "focus": focus,
        "level": level,
        "recommendation": recommendation,
        "open_plans": len([plan for plan in plans if plan["status"] == "active"]),
        "recent_inputs": len(journals) + len(checkins) + len(assessments),
    }


def class_intervention_suggestions(rows):
    suggestions = []
    for row in rows:
        group_name = row["group_name"] or "Unassigned"
        if row["avg_stress"] and row["avg_stress"] >= 4:
            suggestions.append(f"{group_name}: open class with a workload map and one flexible deadline conversation.")
        if row["avg_belonging"] and row["avg_belonging"] <= 2.7:
            suggestions.append(f"{group_name}: add a low-pressure pair activity and watch for isolation patterns.")
        if row["avg_sleep"] and row["avg_sleep"] <= 2.7:
            suggestions.append(f"{group_name}: avoid surprise deadlines and coordinate homework load.")
    if not suggestions:
        suggestions.append("Keep the weekly pulse routine and make the support path visible before pressure spikes.")
    return suggestions[:5]


def level_for_score(score, urgent_override=False, support_override=False):
    score = clamp_score(score)
    if urgent_override or score <= 22:
        return "urgent"
    if support_override or score <= 40:
        return "support"
    if score <= 58:
        return "watch"
    return "steady"


def build_summary(level, hits):
    signal_text = ", ".join(hits[:4]) if hits else "student context"
    if level == "urgent":
        return f"Prompt human review is required for {signal_text}. This is not a diagnosis."
    if level == "support":
        return f"The signal suggests counselor follow-up for {signal_text}. This is not a diagnosis."
    if level == "watch":
        return f"The signal suggests mild pressure around {signal_text}. A supportive check-in may help."
    return "The signal appears stable based on the information provided."


def normalize(text):
    return str(text or "").strip().lower()


def safe_int(value, low, high, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def clamp_score(value):
    return max(1, min(99, int(round(value))))
