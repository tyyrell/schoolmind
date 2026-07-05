import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA_VERSION = "2026-07-schoolmind-postgres-14"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    country TEXT NOT NULL DEFAULT 'Jordan',
    plan TEXT NOT NULL DEFAULT 'starter',
    status TEXT NOT NULL DEFAULT 'trial',
    trial_ends_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS school_settings (
    school_id INTEGER PRIMARY KEY,
    support_owner TEXT NOT NULL DEFAULT '',
    escalation_window_minutes INTEGER NOT NULL DEFAULT 60,
    emergency_instructions TEXT NOT NULL DEFAULT 'Use the school-approved human escalation protocol. This product does not replace emergency services or professional judgment.',
    data_retention_days INTEGER NOT NULL DEFAULT 365,
    guardian_consent_required INTEGER NOT NULL DEFAULT 1,
    launch_language TEXT NOT NULL DEFAULT 'en',
    launch_mode TEXT NOT NULL DEFAULT 'self_serve_trial',
    launch_stage TEXT NOT NULL DEFAULT 'setup',
    approval_owner TEXT NOT NULL DEFAULT '',
    data_owner TEXT NOT NULL DEFAULT '',
    support_email TEXT NOT NULL DEFAULT '',
    expected_students INTEGER NOT NULL DEFAULT 0,
    expected_staff INTEGER NOT NULL DEFAULT 0,
    pilot_goal TEXT NOT NULL DEFAULT '',
    onboarding_completed_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','teacher','counselor','admin')),
    group_name TEXT,
    google_sub TEXT,
    auth_provider TEXT NOT NULL DEFAULT 'password',
    avatar_url TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    last_login_at TEXT,
    password_changed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    language TEXT NOT NULL DEFAULT 'en',
    theme TEXT NOT NULL DEFAULT 'dark',
    font_size TEXT NOT NULL DEFAULT 'normal',
    reduced_motion INTEGER NOT NULL DEFAULT 0,
    high_contrast INTEGER NOT NULL DEFAULT 0,
    dyslexia_friendly INTEGER NOT NULL DEFAULT 0,
    notify_email INTEGER NOT NULL DEFAULT 1,
    notify_support INTEGER NOT NULL DEFAULT 1,
    personalization_completed INTEGER NOT NULL DEFAULT 0,
    personalization_dismissed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'trialing',
    seats INTEGER NOT NULL DEFAULT 250,
    monthly_price INTEGER NOT NULL DEFAULT 49,
    discount_percent INTEGER NOT NULL DEFAULT 0,
    coupon_code TEXT NOT NULL DEFAULT '',
    checkout_reference TEXT,
    current_period_end TEXT,
    renewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS billing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    plan TEXT NOT NULL,
    amount INTEGER NOT NULL DEFAULT 0,
    provider_reference TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS coupon_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    discount_percent INTEGER NOT NULL CHECK(discount_percent BETWEEN 1 AND 100),
    max_redemptions INTEGER NOT NULL DEFAULT 100,
    redeemed_count INTEGER NOT NULL DEFAULT 0,
    applies_to_plan TEXT NOT NULL DEFAULT 'all',
    status TEXT NOT NULL DEFAULT 'active',
    expires_at TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (created_by) REFERENCES platform_admins(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS coupon_redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL,
    subscription_id INTEGER,
    discount_amount INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (coupon_id) REFERENCES coupon_codes(id) ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS payment_intents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    amount INTEGER NOT NULL,
    discount_amount INTEGER NOT NULL DEFAULT 0,
    final_amount INTEGER NOT NULL,
    coupon_code TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    provider_reference TEXT,
    created_at TEXT NOT NULL,
    paid_at TEXT,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS site_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_by INTEGER,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (updated_by) REFERENCES platform_admins(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    sentiment_score INTEGER NOT NULL DEFAULT 50,
    risk_level TEXT NOT NULL DEFAULT 'steady',
    ai_summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    mood INTEGER NOT NULL CHECK(mood BETWEEN 1 AND 5),
    stress INTEGER NOT NULL CHECK(stress BETWEEN 1 AND 5),
    energy INTEGER NOT NULL CHECK(energy BETWEEN 1 AND 5),
    note TEXT,
    risk_level TEXT NOT NULL DEFAULT 'steady',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wellbeing_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    mood INTEGER NOT NULL CHECK(mood BETWEEN 1 AND 5),
    stress INTEGER NOT NULL CHECK(stress BETWEEN 1 AND 5),
    sleep INTEGER NOT NULL CHECK(sleep BETWEEN 1 AND 5),
    belonging INTEGER NOT NULL CHECK(belonging BETWEEN 1 AND 5),
    study_pressure INTEGER NOT NULL CHECK(study_pressure BETWEEN 1 AND 5),
    focus INTEGER NOT NULL CHECK(focus BETWEEN 1 AND 5),
    safety INTEGER NOT NULL CHECK(safety BETWEEN 1 AND 5),
    support_access INTEGER NOT NULL CHECK(support_access BETWEEN 1 AND 5),
    score INTEGER NOT NULL DEFAULT 50,
    risk_level TEXT NOT NULL DEFAULT 'steady',
    primary_need TEXT NOT NULL DEFAULT 'support',
    recommendation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_support_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    focus_area TEXT NOT NULL,
    goal TEXT NOT NULL,
    next_step TEXT NOT NULL,
    cadence TEXT NOT NULL DEFAULT 'Weekly review',
    status TEXT NOT NULL DEFAULT 'active',
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS student_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'wellbeing',
    target_date TEXT,
    progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS game_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    game_name TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS breathing_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    technique TEXT NOT NULL DEFAULT 'box',
    cycles INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    mood_before INTEGER,
    mood_after INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_ai_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','nour')),
    message TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'steady',
    provider TEXT NOT NULL DEFAULT 'local',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK(risk_level IN ('steady','watch','support','urgent')),
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    assigned_to INTEGER,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS support_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS interventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    counselor_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (counselor_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    risk_event_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    counselor_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('assigned','escalated','closed','note')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (risk_event_id) REFERENCES risk_events(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (counselor_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS consent_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    guardian_name TEXT NOT NULL,
    guardian_email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT NOT NULL DEFAULT '',
    recorded_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS playbooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER,
    title TEXT NOT NULL,
    trigger_level TEXT NOT NULL DEFAULT 'watch',
    action_steps TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sales_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    school_name TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    lead_type TEXT NOT NULL DEFAULT 'contact',
    requested_plan TEXT NOT NULL DEFAULT '',
    billing_cycle TEXT NOT NULL DEFAULT '',
    student_count INTEGER NOT NULL DEFAULT 0,
    launch_timeline TEXT NOT NULL DEFAULT '',
    preferred_path TEXT NOT NULL DEFAULT '',
    role_interest TEXT NOT NULL DEFAULT '',
    privacy_review_needed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    imported_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invite_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','teacher','counselor','admin')),
    group_name TEXT,
    token_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    created_by INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    accepted_at TEXT,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS outbox_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    message_type TEXT NOT NULL DEFAULT 'transactional',
    metadata TEXT NOT NULL DEFAULT '',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    provider_reference TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_attempt_at TEXT,
    sent_at TEXT,
    updated_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agreement_acceptances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    agreement_type TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER,
    user_id INTEGER,
    email TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    ip_address TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS platform_admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    last_login_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_admin_preferences (
    admin_id INTEGER PRIMARY KEY,
    language TEXT NOT NULL DEFAULT 'en',
    theme TEXT NOT NULL DEFAULT 'dark',
    font_size TEXT NOT NULL DEFAULT 'normal',
    reduced_motion INTEGER NOT NULL DEFAULT 0,
    high_contrast INTEGER NOT NULL DEFAULT 0,
    dyslexia_friendly INTEGER NOT NULL DEFAULT 0,
    notify_email INTEGER NOT NULL DEFAULT 1,
    personalization_completed INTEGER NOT NULL DEFAULT 0,
    personalization_dismissed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (admin_id) REFERENCES platform_admins(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_school ON users(school_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_school_role ON users(school_id, role);
CREATE INDEX IF NOT EXISTS idx_user_preferences_language ON user_preferences(language, theme);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_subscription_school_status ON subscriptions(school_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_coupon_status ON coupon_codes(status, code);
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_school ON coupon_redemptions(school_id, created_at);
CREATE INDEX IF NOT EXISTS idx_payment_intents_school ON payment_intents(school_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_billing_events_school ON billing_events(school_id, created_at);
CREATE INDEX IF NOT EXISTS idx_risk_school_status ON risk_events(school_id, status, risk_level);
CREATE INDEX IF NOT EXISTS idx_journal_school_student ON journal_entries(school_id, student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_journal_student ON journal_entries(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_checkin_school_student ON checkins(school_id, student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_checkin_student ON checkins(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assessment_school_student ON wellbeing_assessments(school_id, student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assessment_student ON wellbeing_assessments(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assessment_school_need ON wellbeing_assessments(school_id, primary_need, risk_level);
CREATE INDEX IF NOT EXISTS idx_support_plans_school_student ON student_support_plans(school_id, student_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_support_plans_student ON student_support_plans(student_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_goals_school_student ON student_goals(school_id, student_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_goals_student ON student_goals(student_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_games_school_student ON game_scores(school_id, student_id, game_name, created_at);
CREATE INDEX IF NOT EXISTS idx_games_student ON game_scores(student_id, game_name, created_at);
CREATE INDEX IF NOT EXISTS idx_breathing_school_student ON breathing_sessions(school_id, student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_breathing_student ON breathing_sessions(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_messages_school_student ON student_ai_messages(school_id, student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_messages_student ON student_ai_messages(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_messages_student_date ON student_ai_messages(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_consent_school_student ON consent_records(school_id, student_id);
CREATE INDEX IF NOT EXISTS idx_leads_created ON sales_leads(created_at);
CREATE INDEX IF NOT EXISTS idx_leads_type_status ON sales_leads(lead_type, status, created_at);
CREATE INDEX IF NOT EXISTS idx_invites_school_status ON invite_tokens(school_id, status);
CREATE INDEX IF NOT EXISTS idx_outbox_school_status ON outbox_messages(school_id, status);
CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON outbox_messages(status, created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_type_status ON outbox_messages(message_type, status, created_at);
CREATE INDEX IF NOT EXISTS idx_password_resets_status ON password_reset_tokens(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_case_actions_event ON case_actions(school_id, risk_event_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agreements_user ON agreement_acceptances(school_id, user_id, agreement_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_school ON audit_events(school_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_audit_user ON audit_events(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_account_security_school ON account_security_events(school_id, created_at);
CREATE INDEX IF NOT EXISTS idx_account_security_email ON account_security_events(email, created_at);
"""

DEFAULT_PLAYBOOKS = (
    ("Watch signal review", "watch", "1. Review recent check-ins and context.\n2. Ask a calm, non-leading follow-up question.\n3. Record whether classroom pressure, attendance, or workload is involved."),
    ("Support follow-up", "support", "1. Schedule a counselor check-in.\n2. Notify the assigned support owner according to school policy.\n3. Document the action and next review time."),
    ("Urgent human escalation", "urgent", "1. Use the school-approved escalation protocol immediately.\n2. Involve the designated human support owner.\n3. Document only necessary operational facts."),
)

SQLITE_TO_POSTGRES_TABLE_ORDER = (
    "schools",
    "platform_admins",
    "school_settings",
    "users",
    "platform_admin_preferences",
    "user_preferences",
    "subscriptions",
    "billing_events",
    "coupon_codes",
    "coupon_redemptions",
    "payment_intents",
    "site_settings",
    "journal_entries",
    "checkins",
    "wellbeing_assessments",
    "student_support_plans",
    "student_goals",
    "game_scores",
    "breathing_sessions",
    "student_ai_messages",
    "risk_events",
    "support_requests",
    "interventions",
    "case_actions",
    "consent_records",
    "playbooks",
    "sales_leads",
    "import_batches",
    "invite_tokens",
    "password_reset_tokens",
    "outbox_messages",
    "agreement_acceptances",
    "audit_events",
    "account_security_events",
    "schema_migrations",
)


def utcnow():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def database_engine():
    return str(current_app.config.get("DATABASE_ENGINE", "sqlite")).lower()


def is_postgres():
    return database_engine() == "postgres"


def normalize_database_url(url):
    value = (url or "").strip()
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://"):]
    return value


def postgres_url_settings(url):
    value = normalize_database_url(url)
    if not value:
        return {}
    parsed = urlparse(value)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return {key.lower(): val for key, val in params.items()}


def build_postgres_database_url(url, sslmode="", application_name=""):
    value = normalize_database_url(url)
    if not value:
        return value
    parsed = urlparse(value)
    if parsed.scheme != "postgresql":
        return value
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if sslmode and "sslmode" not in {key.lower() for key in params}:
        params["sslmode"] = sslmode
    if application_name and "application_name" not in {key.lower() for key in params}:
        params["application_name"] = application_name
    return urlunparse(parsed._replace(query=urlencode(params)))


def database_url_uses_supabase_pooler(url):
    host = (urlparse(normalize_database_url(url)).hostname or "").lower()
    port = urlparse(normalize_database_url(url)).port
    return "supabase" in host and port in {6543, 5432}


def mask_database_url(url):
    value = (url or "").strip()
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return "<masked>"
        host = parsed.hostname or "host"
        port = f":{parsed.port}" if parsed.port else ""
        database = parsed.path or ""
        return f"{parsed.scheme}://***:***@{host}{port}{database}"
    except Exception:
        return "<masked>"


def convert_placeholders(sql):
    if not sql:
        return sql
    converted = []
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double:
            converted.append(ch)
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                converted.append(sql[i + 1])
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single:
            converted.append(ch)
            in_double = not in_double
        elif ch == "?" and not in_single and not in_double:
            converted.append("%s")
        else:
            converted.append(ch)
        i += 1
    return "".join(converted)


def split_sql_statements(script):
    statements = []
    current = []
    in_single = False
    in_double = False
    i = 0
    while i < len(script):
        ch = script[i]
        current.append(ch)
        if ch == "'" and not in_double:
            if i + 1 < len(script) and script[i + 1] == "'":
                current.append(script[i + 1])
                i += 1
            else:
                in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double:
            stmt = "".join(current).strip().rstrip(";").strip()
            if stmt:
                statements.append(stmt)
            current = []
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def schema_statements_for_engine(engine):
    """Return schema statements split into table creation and post-migration statements.

    Important: CREATE INDEX statements must run after migrate_database(). Existing
    deployments can have older tables that lack newly added columns such as
    sales_leads.lead_type or outbox_messages.message_type. Running indexes before
    column backfills makes PostgreSQL fail at boot with UndefinedColumn.
    """
    normalized = str(engine or "sqlite").lower()
    table_statements = {}
    post_migration_statements = []
    for statement in split_sql_statements(SCHEMA):
        if normalized == "postgres" and statement.upper().startswith("PRAGMA"):
            continue
        match = re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)", statement, re.IGNORECASE)
        if match:
            if normalized == "postgres":
                statement = convert_sqlite_schema_to_postgres(statement)
            table_statements[match.group(1)] = statement
        else:
            post_migration_statements.append(statement)

    ordered_tables = [table_statements[name] for name in SQLITE_TO_POSTGRES_TABLE_ORDER if name in table_statements]
    ordered_tables.extend(table_statements[name] for name in sorted(set(table_statements) - set(SQLITE_TO_POSTGRES_TABLE_ORDER)))
    return ordered_tables, post_migration_statements


def join_sql_statements(statements):
    statements = [statement.strip().rstrip(";") for statement in statements if statement and statement.strip()]
    if not statements:
        return ""
    return ";\n\n".join(statements) + ";\n"


def schema_table_sql(engine):
    tables, _ = schema_statements_for_engine(engine)
    return join_sql_statements(tables)


def schema_post_migration_sql(engine):
    _, post_migration = schema_statements_for_engine(engine)
    return join_sql_statements(post_migration)


def postgres_schema_sql():
    return schema_table_sql("postgres") + schema_post_migration_sql("postgres")


def schema_for_engine(engine):
    return schema_table_sql(engine) + schema_post_migration_sql(engine)


def convert_sqlite_schema_to_postgres(sql):
    converted = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
    converted = re.sub(r"\bAUTOINCREMENT\b", "", converted, flags=re.IGNORECASE)
    return converted


def postgres_column_definition(definition):
    return convert_sqlite_schema_to_postgres(definition)


class CursorAdapter:
    def __init__(self, cursor, connection, engine, sql=""):
        self.cursor = cursor
        self.connection = connection
        self.engine = engine
        self.sql = sql
        self._lastrowid_loaded = False
        self._lastrowid = None

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def rowcount(self):
        return getattr(self.cursor, "rowcount", -1)

    @property
    def lastrowid(self):
        if self.engine == "sqlite":
            return getattr(self.cursor, "lastrowid", None)
        if not self._lastrowid_loaded:
            self._lastrowid_loaded = True
            self._lastrowid = self._load_postgres_lastrowid()
        return self._lastrowid

    def _load_postgres_lastrowid(self):
        match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][\w]*)", self.sql or "", re.IGNORECASE)
        if not match:
            return None
        table = match.group(1)
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT currval(pg_get_serial_sequence(%s, 'id')) AS id", (table,))
                row = cur.fetchone()
                if isinstance(row, dict):
                    return row.get("id")
                if row:
                    return row[0]
        except Exception:
            return None
        return None


class DatabaseAdapter:
    def __init__(self, connection, engine):
        self.connection = connection
        self.engine = engine

    def execute(self, sql, params=()):
        if self.engine == "postgres":
            sql = convert_placeholders(sql)
        cursor = self.connection.execute(sql, params or ())
        return CursorAdapter(cursor, self.connection, self.engine, sql)

    def executemany(self, sql, seq_of_params):
        if self.engine == "postgres":
            sql = convert_placeholders(sql)
        cursor = self.connection.executemany(sql, seq_of_params)
        return CursorAdapter(cursor, self.connection, self.engine, sql)

    def executescript(self, script):
        if self.engine == "sqlite":
            self.connection.executescript(script)
            return None
        for statement in split_sql_statements(script):
            self.execute(statement)
        return None

    def commit(self):
        return self.connection.commit()

    def rollback(self):
        return self.connection.rollback()

    def close(self):
        return self.connection.close()


def connect_postgres(database_url):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("DATABASE_ENGINE=postgres requires psycopg[binary]. Install project requirements before starting the app.") from exc
    sslmode = current_app.config.get("DATABASE_SSLMODE", "")
    application_name = current_app.config.get("DATABASE_APPLICATION_NAME", "schoolmind-ai")
    url = build_postgres_database_url(database_url, sslmode=sslmode, application_name=application_name)
    if not url.startswith("postgresql://"):
        raise RuntimeError("DATABASE_URL must start with postgres:// or postgresql:// when DATABASE_ENGINE=postgres.")

    connection_kwargs = {
        "row_factory": dict_row,
        "connect_timeout": int(current_app.config.get("DATABASE_CONNECT_TIMEOUT_SECONDS", 10)),
        "options": f"-c statement_timeout={int(current_app.config.get('DATABASE_STATEMENT_TIMEOUT_MS', 30000))}",
    }
    return psycopg.connect(url, **connection_kwargs)


def get_db():
    if "db" not in g:
        engine = database_engine()
        if engine == "postgres":
            database_url = current_app.config.get("DATABASE_URL", "")
            g.db = DatabaseAdapter(connect_postgres(database_url), "postgres")
        elif engine == "sqlite":
            path = current_app.config["DATABASE_PATH"]
            if path != ":memory:":
                dirname = os.path.dirname(path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            g.db = DatabaseAdapter(connection, "sqlite")
        else:
            raise RuntimeError("DATABASE_ENGINE must be sqlite or postgres.")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_database():
    db = get_db()
    engine = database_engine()
    db.executescript(schema_table_sql(engine))
    db.commit()
    migrate_database()
    db = get_db()
    db.executescript(schema_post_migration_sql(engine))
    db.commit()
    record_schema_version()
    seed_default_playbooks()
    seed_platform_admin()
    seed_site_settings()
    seed_default_coupons()


def record_schema_version():
    if not query_one("SELECT version FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)):
        execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (SCHEMA_VERSION, utcnow()))


def migrate_database():
    ensure_columns(
        "users",
        {
            "google_sub": "TEXT",
            "auth_provider": "TEXT NOT NULL DEFAULT 'password'",
            "avatar_url": "TEXT NOT NULL DEFAULT ''",
            "failed_login_count": "INTEGER NOT NULL DEFAULT 0",
            "locked_until": "TEXT",
            "last_login_at": "TEXT",
            "password_changed_at": "TEXT",
        },
    )
    ensure_columns(
        "platform_admins",
        {
            "failed_login_count": "INTEGER NOT NULL DEFAULT 0",
            "locked_until": "TEXT",
            "last_login_at": "TEXT",
        },
    )
    ensure_columns(
        "subscriptions",
        {
            "discount_percent": "INTEGER NOT NULL DEFAULT 0",
            "coupon_code": "TEXT NOT NULL DEFAULT ''",
            "current_period_end": "TEXT",
        },
    )
    ensure_columns(
        "user_preferences",
        {
            "personalization_completed": "INTEGER NOT NULL DEFAULT 0",
            "personalization_dismissed": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    ensure_columns(
        "platform_admin_preferences",
        {
            "personalization_completed": "INTEGER NOT NULL DEFAULT 0",
            "personalization_dismissed": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    ensure_columns(
        "sales_leads",
        {
            "lead_type": "TEXT NOT NULL DEFAULT 'contact'",
            "requested_plan": "TEXT NOT NULL DEFAULT ''",
            "billing_cycle": "TEXT NOT NULL DEFAULT ''",
            "student_count": "INTEGER NOT NULL DEFAULT 0",
            "launch_timeline": "TEXT NOT NULL DEFAULT ''",
            "preferred_path": "TEXT NOT NULL DEFAULT ''",
            "role_interest": "TEXT NOT NULL DEFAULT ''",
            "privacy_review_needed": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    ensure_columns(
        "school_settings",
        {
            "launch_language": "TEXT NOT NULL DEFAULT 'en'",
            "launch_mode": "TEXT NOT NULL DEFAULT 'self_serve_trial'",
            "launch_stage": "TEXT NOT NULL DEFAULT 'setup'",
            "approval_owner": "TEXT NOT NULL DEFAULT ''",
            "data_owner": "TEXT NOT NULL DEFAULT ''",
            "support_email": "TEXT NOT NULL DEFAULT ''",
            "expected_students": "INTEGER NOT NULL DEFAULT 0",
            "expected_staff": "INTEGER NOT NULL DEFAULT 0",
            "pilot_goal": "TEXT NOT NULL DEFAULT ''",
            "onboarding_completed_at": "TEXT",
        },
    )
    ensure_columns(
        "outbox_messages",
        {
            "message_type": "TEXT NOT NULL DEFAULT 'transactional'",
            "metadata": "TEXT NOT NULL DEFAULT ''",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "last_error": "TEXT NOT NULL DEFAULT ''",
            "last_attempt_at": "TEXT",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        },
    )


def ensure_columns(table, columns):
    db = get_db()
    existing = existing_columns(table)
    for name, definition in columns.items():
        if name not in existing:
            if is_postgres():
                definition = postgres_column_definition(definition)
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    db.commit()


def existing_columns(table):
    if is_postgres():
        rows = query_all(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = ?
            """,
            (table,),
        )
        return {row["column_name"] for row in rows}
    return {row[1] for row in get_db().execute(f"PRAGMA table_info({table})").fetchall()}


def seed_platform_admin():
    email = (os.environ.get("PLATFORM_ADMIN_EMAIL") or "owner@schoolmind.ai").strip().lower()
    password = os.environ.get("PLATFORM_ADMIN_PASSWORD") or "demo12345"
    name = os.environ.get("PLATFORM_ADMIN_NAME") or "Platform Owner"
    if query_one("SELECT id FROM platform_admins WHERE email = ?", (email,)):
        return
    execute(
        "INSERT INTO platform_admins (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(password), utcnow()),
    )


def seed_site_settings():
    defaults = {
        "public_announcement": "Now piloting SchoolMind with schools and youth organizations.",
        "hero_title": "A student support operating system for schools.",
        "hero_subtitle": "Wellbeing scans, support plans, counselor workflows, classroom pulse, billing, consent, and safety in one SaaS workspace.",
        "maintenance_mode": "false",
        "allow_public_trials": "true",
    }
    for key, value in defaults.items():
        if query_one("SELECT key FROM site_settings WHERE key = ?", (key,)):
            continue
        execute(
            "INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, utcnow()),
        )


def seed_default_coupons():
    if query_one("SELECT id FROM coupon_codes WHERE code = ?", ("PILOT25",)):
        return
    execute(
        """
        INSERT INTO coupon_codes (code, description, discount_percent, max_redemptions, applies_to_plan, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("PILOT25", "25% pilot discount for early school partners", 25, 50, "all", "active", utcnow()),
    )


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur


def executemany(sql, params_seq):
    db = get_db()
    cur = db.executemany(sql, params_seq)
    db.commit()
    return cur


@contextmanager
def transaction():
    db = get_db()
    try:
        if db.engine == "sqlite":
            db.execute("BEGIN")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


def log_event(action, detail, school_id=None, user_id=None):
    execute(
        "INSERT INTO audit_events (school_id, user_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (school_id, user_id, str(action)[:120], str(detail)[:500], utcnow()),
    )


def ensure_school_settings(school_id):
    existing = query_one("SELECT * FROM school_settings WHERE school_id = ?", (school_id,))
    if existing:
        return existing
    execute(
        "INSERT INTO school_settings (school_id, updated_at) VALUES (?, ?)",
        (school_id, utcnow()),
    )
    return query_one("SELECT * FROM school_settings WHERE school_id = ?", (school_id,))


def ensure_user_preferences(user_id):
    existing = query_one("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    if existing:
        return existing
    execute("INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?)", (user_id, utcnow()))
    return query_one("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))


def ensure_platform_preferences(admin_id):
    existing = query_one("SELECT * FROM platform_admin_preferences WHERE admin_id = ?", (admin_id,))
    if existing:
        return existing
    execute("INSERT INTO platform_admin_preferences (admin_id, updated_at) VALUES (?, ?)", (admin_id, utcnow()))
    return query_one("SELECT * FROM platform_admin_preferences WHERE admin_id = ?", (admin_id,))


def seed_default_playbooks():
    for title, trigger_level, steps in DEFAULT_PLAYBOOKS:
        existing = query_one("SELECT id FROM playbooks WHERE school_id IS NULL AND title = ?", (title,))
        if existing:
            continue
        execute(
            "INSERT INTO playbooks (school_id, title, trigger_level, action_steps, is_default, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (None, title, trigger_level, steps, 1, utcnow()),
        )


def count_users(school_id, role=None):
    if role:
        return query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role = ?", (school_id, role))["c"]
    return query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ?", (school_id,))["c"]


def seed_demo_data():
    existing = query_one("SELECT id FROM schools WHERE slug = ?", ("pixel-academy",))
    now = utcnow()
    if existing:
        school_id = existing["id"]
        ensure_school_settings(school_id)
        password = generate_password_hash("demo12345")
        people = [
            ("Ava Admin", "admin@schoolmind.ai", "admin", None),
            ("Cora Counselor", "counselor@schoolmind.ai", "counselor", None),
            ("Theo Teacher", "teacher@schoolmind.ai", "teacher", "Grade 10-A"),
            ("Sam Student", "student@schoolmind.ai", "student", "Grade 10-A"),
        ]
        for name, email, role, group_name in people:
            user = query_one("SELECT id FROM users WHERE email = ?", (email,))
            if user:
                execute(
                    """
                    UPDATE users
                    SET school_id = ?, name = ?, password_hash = ?, role = ?, group_name = ?,
                        is_active = 1, failed_login_count = 0, locked_until = NULL, password_changed_at = ?
                    WHERE id = ?
                    """,
                    (school_id, name, password, role, group_name, now, user["id"]),
                )
            else:
                execute(
                    """
                    INSERT INTO users
                    (school_id, name, email, password_hash, role, group_name, password_changed_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (school_id, name, email, password, role, group_name, now, now),
                )
        return
    trial_end = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    school_id = execute(
        "INSERT INTO schools (name, slug, country, plan, status, trial_ends_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("SchoolMind Demo School", "pixel-academy", "Global", "growth", "trial", trial_end, now),
    ).lastrowid
    ensure_school_settings(school_id)
    execute(
        "UPDATE school_settings SET support_owner = ?, escalation_window_minutes = ?, updated_at = ? WHERE school_id = ?",
        ("Cora Counselor", 45, utcnow(), school_id),
    )
    execute(
        "INSERT INTO subscriptions (school_id, plan, status, seats, monthly_price, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (school_id, "growth", "trialing", 1000, 120, now),
    )
    execute(
        "INSERT INTO billing_events (school_id, event_type, plan, amount, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (school_id, "trial_started", "growth", 0, "Demo tenant trial started", now),
    )
    password = generate_password_hash("demo12345")
    people = [
        ("Ava Admin", "admin@schoolmind.ai", "admin", None),
        ("Cora Counselor", "counselor@schoolmind.ai", "counselor", None),
        ("Theo Teacher", "teacher@schoolmind.ai", "teacher", "Grade 10-A"),
        ("Sam Student", "student@schoolmind.ai", "student", "Grade 10-A"),
        ("Mia Student", "mia@student.schoolmind.ai", "student", "Grade 10-A"),
        ("Leo Student", "leo@student.schoolmind.ai", "student", "Grade 10-B"),
    ]
    ids = {}
    for name, email, role, group_name in people:
        ids[email] = execute(
            "INSERT INTO users (school_id, name, email, password_hash, role, group_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (school_id, name, email, password, role, group_name, now),
        ).lastrowid
    student_id = ids["student@schoolmind.ai"]
    counselor_id = ids["counselor@schoolmind.ai"]
    execute(
        "INSERT INTO checkins (school_id, student_id, mood, stress, energy, note, risk_level, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, 3, 4, 2, "I need a calmer day and less pressure.", "watch", now),
    )
    execute(
        "INSERT INTO journal_entries (school_id, student_id, body, sentiment_score, risk_level, ai_summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, "School feels heavy this week, but I want to catch up.", 42, "watch", "The entry suggests pressure and a need for support, not a diagnosis.", now),
    )
    execute(
        "INSERT INTO risk_events (school_id, student_id, source, risk_level, title, detail, assigned_to, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, "checkin", "watch", "Sustained stress signal", "Recent check-in suggests the student may benefit from a supportive follow-up.", counselor_id, now),
    )
    execute(
        "INSERT INTO support_requests (school_id, student_id, topic, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (school_id, student_id, "Academic pressure", "I want help making a study plan.", now),
    )
    demo_assessments = [
        (ids["student@schoolmind.ai"], 3, 4, 2, 3, 5, 3, 4, 3, 45, "watch", "study_load", "Build a simple catch-up plan with one priority, one deadline, and one person to ask for help."),
        (ids["mia@student.schoolmind.ai"], 4, 2, 4, 4, 2, 4, 5, 4, 76, "steady", "support", "Keep the routine visible: one check-in, one goal, and one support path the student can name."),
        (ids["leo@student.schoolmind.ai"], 2, 5, 2, 2, 4, 2, 3, 2, 34, "support", "calm", "Reduce immediate pressure, name the top stressor, and create a 20-minute recovery block."),
    ]
    for row in demo_assessments:
        execute(
            """
            INSERT INTO wellbeing_assessments
            (school_id, student_id, mood, stress, sleep, belonging, study_pressure, focus, safety, support_access, score, risk_level, primary_need, recommendation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (school_id, *row, now),
        )
    execute(
        """
        INSERT INTO student_support_plans
        (school_id, student_id, focus_area, goal, next_step, cadence, status, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            school_id,
            student_id,
            "Study pressure",
            "Improve study pressure without labeling the student.",
            "Break the heaviest assignment into three small steps and confirm the first deadline.",
            "Two check-ins this week",
            "active",
            counselor_id,
            now,
            now,
        ),
    )
    execute(
        """
        INSERT INTO student_goals (school_id, student_id, title, description, category, target_date, progress, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (school_id, student_id, "Finish the math catch-up plan", "Break the missing work into three short sessions.", "study", None, 35, "active", now, now),
    )
    for game_name, score, duration in (("calm_match", 84, 120), ("focus_tiles", 66, 180), ("gratitude_builder", 91, 90)):
        execute(
            "INSERT INTO game_scores (school_id, student_id, game_name, score, duration_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (school_id, student_id, game_name, score, duration, now),
        )
    execute(
        "INSERT INTO breathing_sessions (school_id, student_id, technique, cycles, duration_seconds, mood_before, mood_after, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, "box", 4, 180, 2, 4, now),
    )
    execute(
        "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, "student", "I feel pressure before exams and need a study plan.", "watch", "local", now),
    )
    execute(
        "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, "nour", "Let's turn the pressure into one small plan: choose the first assignment, set a 20-minute block, then ask your support owner if it still feels heavy.", "steady", "local", now),
    )
    execute(
        "INSERT INTO consent_records (school_id, student_id, guardian_name, guardian_email, status, note, recorded_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, "Demo Guardian", "guardian@example.com", "recorded", "Demo consent record only.", ids["admin@schoolmind.ai"], now),
    )
    log_event("seed_demo", "Demo tenant created", school_id=school_id)
