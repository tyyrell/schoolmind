# SchoolMind AI - Comprehensive Code Review

**Date:** July 3, 2026  
**Project:** SchoolMind AI - Educational Wellbeing SaaS Platform  
**Stack:** Python 3.12, Flask 3, PostgreSQL/Supabase (production), SQLite (development)  
**Status:** MVP ready for controlled pilots with operator-managed deployment steps

---

## Executive Summary

SchoolMind is a well-architected Flask SaaS with strong foundational security, tenant isolation, and feature completeness. The codebase demonstrates good practices in parameterized SQL, role-based access control, and CSRF protection. However, the project needs attention in operational resilience, performance optimization, data handling, accessibility, and production-readiness practices before handling real student data at scale.

**Key Strengths:**
- Clear multi-tenant architecture with school-scoped queries
- Comprehensive security headers and CSRF/rate-limit enforcement
- Role-based access control with proper decorator implementation
- Parameterized SQL throughout (no SQL injection vulnerabilities detected)
- Comprehensive feature set with billing, consent, and audit trails

**Critical Gaps:**
- Rate limiting uses unbounded in-memory storage (memory leak risk)
- Email delivery not properly abstracted; production needs manual SMTP setup
- Missing database connection pooling configuration for production
- No caching strategy for frequently accessed data
- Incomplete error handling in database operations
- String-based date columns instead of proper datetime types
- Session management could be stronger
- Accessibility compliance not validated

---

## 1. SECURITY ISSUES & VULNERABILITIES

### 1.1 🔴 CRITICAL: Unbounded Rate Limiting Memory Growth

**Location:** [schoolmind/security.py](schoolmind/security.py#L1-L20)

**Issue:**
```python
def rate_limit(scope, max_requests=40, window_seconds=300):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            now = time.time()
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            key = f"{scope}:{ip}"
            bucket = [stamp for stamp in RATE_BUCKETS.get(key, []) if now - stamp < window_seconds]
            # ... rest of code
            RATE_BUCKETS[key] = bucket
```

The `RATE_BUCKETS` dictionary never clears old entries. Over time, this causes unbounded memory growth as new IP addresses and scopes accumulate entries that are never removed.

**Recommendations:**
1. Implement periodic cleanup (e.g., every 10,000 requests or on timer)
2. Use Redis or Memcached for distributed rate limiting
3. Add maximum bucket size limit and evict oldest entries
4. Consider using Flask-Limiter extension instead

**Fixed Code Example:**
```python
import threading
import time

RATE_BUCKETS = {}
CLEANUP_INTERVAL = 300  # Clean every 5 minutes
LAST_CLEANUP = 0

def rate_limit(scope, max_requests=40, window_seconds=300):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            global LAST_CLEANUP
            now = time.time()
            
            # Periodic cleanup
            if now - LAST_CLEANUP > CLEANUP_INTERVAL:
                stale_keys = [k for k, v in RATE_BUCKETS.items() if not v or all(now - t > window_seconds for t in v)]
                for k in stale_keys:
                    del RATE_BUCKETS[k]
                LAST_CLEANUP = now
            
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            key = f"{scope}:{ip}"
            bucket = [stamp for stamp in RATE_BUCKETS.get(key, []) if now - stamp < window_seconds]
            if len(bucket) >= max_requests:
                abort(429)
            bucket.append(now)
            RATE_BUCKETS[key] = bucket
            return view(*args, **kwargs)
        return wrapper
    return decorator
```

---

### 1.2 🟠 HIGH: Weak CSP (Content Security Policy)

**Location:** [schoolmind/security.py](schoolmind/security.py#L75)

**Issue:**
```python
"Content-Security-Policy", "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; ..."
```

Allowing `'unsafe-inline'` for styles defeats much of CSP's purpose. This allows inline style injection attacks.

**Recommendations:**
1. Extract all inline styles to external CSS files
2. Remove `'unsafe-inline'` from `style-src`
3. Add `nonce` attribute to any necessary inline scripts
4. Add `script-src-elem` and `script-src-attr` for finer control

**Improved CSP:**
```python
"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';"
```

---

### 1.3 🟠 HIGH: Session Cookie Security Could Be Enhanced

**Location:** [schoolmind/__init__.py](schoolmind/__init__.py#L30)

**Issue:**
```python
SESSION_COOKIE_SAMESITE="Lax",  # Supports OAuth callbacks; CSRF tokens protect unsafe methods
```

`SameSite=Lax` still allows some cross-site requests. For a sensitive education platform, `Strict` is more appropriate.

**Recommendations:**
1. Change to `SameSite=Strict` (may impact some workflows)
2. Consider reducing session timeout from 8 hours
3. Implement session fingerprinting to detect hijacking
4. Add option to revoke sessions from security settings

**Updated Code:**
```python
SESSION_COOKIE_SAMESITE="Lax",  # OAuth-compatible; keep CSRF on POST/PUT/PATCH/DELETE
PERMANENT_SESSION_LIFETIME=timedelta(hours=4),  # Reduced from 8
SESSION_COOKIE_SECURE=True,  # Always true in production
SESSION_COOKIE_HTTPONLY=True,  # Already set
```

---

### 1.4 🟠 HIGH: Password Reset Token Lacks Expiration Validation

**Location:** [schoolmind/auth.py](schoolmind/auth.py) - Password reset flow

**Issue:**
The password reset flow stores tokens but doesn't validate their expiration server-side. A captured reset token could potentially be used indefinitely if:
1. The token isn't explicitly deleted after use
2. No TTL validation occurs on retrieval

**Recommendations:**
1. Add `expires_at` timestamp to `password_reset_tokens` table
2. Validate token expiration in the reset view (should be 1-2 hours)
3. Implement token cleanup job for expired tokens
4. Delete token immediately after successful reset

**Schema Update:**
```sql
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,  -- NEW: Add TTL
    used_at TEXT,              -- NEW: Track if used
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

**Validation Code:**
```python
reset_record = query_one(
    "SELECT * FROM password_reset_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
    (token_hash, utcnow())
)
if not reset_record:
    flash("Reset token expired or already used.", "error")
    return redirect(url_for("auth.login"))

# After successful reset:
execute("UPDATE password_reset_tokens SET used_at = ? WHERE id = ?", (utcnow(), reset_record["id"]))
```

---

### 1.5 🟠 HIGH: Google OAuth State Parameter Not Validated Properly

**Location:** [schoolmind/auth.py](schoolmind/auth.py#L95)

**Issue:**
```python
if int(datetime.now(UTC).timestamp()) - started_at > 600:  # 10 minutes
    flash("Google sign-in expired. Try again.", "error")
```

The expiration check uses the `started_at` timestamp stored in session, but there's no invalidation of used state tokens. A captured state token could potentially be replayed.

**Recommendations:**
1. Delete state after using it (already doing with `session.pop()` ✓)
2. Add state token signature/HMAC validation
3. Include request fingerprint in state validation
4. Implement PKCE (Proof Key for Code Exchange) flow

**Improved Implementation:**
```python
import hmac
import hashlib

def create_oauth_state():
    state = secrets.token_urlsafe(24)
    signature = hmac.new(
        app.config["SECRET_KEY"].encode(),
        state.encode(),
        hashlib.sha256
    ).hexdigest()
    session["google_oauth_state"] = f"{state}.{signature}"
    session["google_oauth_started_at"] = int(datetime.now(UTC).timestamp())
    return state

def validate_oauth_state(state):
    expected = session.pop("google_oauth_state", "")
    if not expected or "." not in expected:
        return False
    state_part, sig_part = expected.split(".")
    expected_sig = hmac.new(
        app.config["SECRET_KEY"].encode(),
        state_part.encode(),
        hashlib.sha256
    ).hexdigest()
    return secrets.compare_digest(expected_sig, sig_part) and secrets.compare_digest(state_part, state)
```

---

### 1.6 🟡 MEDIUM: Platform Admin Account Creation Not Secured

**Location:** [schoolmind/db.py](schoolmind/db.py) and [schoolmind/__init__.py](schoolmind/__init__.py)

**Issue:**
Platform admin accounts are created via environment variables during initialization but there's no validation that a password was changed on first login. The `PLATFORM_ADMIN_PASSWORD` is set from environment variable which could be logged or exposed.

**Recommendations:**
1. Require password change on first login
2. Add `last_password_changed_at` tracking
3. Implement password strength requirements (min 12 chars, complexity)
4. Add account creation audit logging

**Implementation:**
```python
# In platform routes - add before_request check
@bp.before_app_request
def enforce_platform_admin_password_change():
    admin = g.get("platform_admin")
    if admin and request.endpoint not in {"platform.platform_logout", "platform.platform_account_settings"}:
        if not admin.get("password_changed_at"):
            flash("Please change your password before continuing.", "warning")
            return redirect(url_for("platform.platform_account_settings"))
```

---

## 2. DATABASE & DATA INTEGRITY ISSUES

### 2.1 🔴 CRITICAL: String-Based Datetime Columns

**Location:** [schoolmind/db.py](schoolmind/db.py) - Schema throughout

**Issue:**
Almost all timestamp columns use TEXT with ISO format strings instead of proper TIMESTAMP/DATETIME types:

```python
"created_at TEXT NOT NULL",
"updated_at TEXT NOT NULL",
"trial_ends_at TEXT NOT NULL",
"expires_at TEXT",
"locked_until TEXT",
```

**Problems:**
1. Cannot use SQL date functions or operators
2. No database-level validation of date formats
3. Sorting and filtering less efficient
4. Easy to insert malformed dates
5. No timezone handling at DB level
6. Harder to debug date issues

**Recommendations:**
For PostgreSQL (production):
1. Use `TIMESTAMP WITH TIME ZONE` for all timestamps
2. Set default to `CURRENT_TIMESTAMP`
3. Add database-level constraints for date validity

For SQLite (local dev):
1. Use `DATETIME` type
2. Add check constraints for ISO format validation

**Updated Schema Example:**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    -- ... other fields ...
    locked_until TIMESTAMP,  -- Changed from TEXT
    last_login_at TIMESTAMP,
    password_changed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

-- PostgreSQL migration
ALTER TABLE users 
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN last_login_at TYPE TIMESTAMP WITH TIME ZONE,
    ALTER COLUMN locked_until TYPE TIMESTAMP WITH TIME ZONE,
    ALTER COLUMN password_changed_at TYPE TIMESTAMP WITH TIME ZONE;
```

---

### 2.2 🟠 HIGH: No Database Connection Pooling Configuration

**Location:** [schoolmind/db.py](schoolmind/db.py)

**Issue:**
PostgreSQL connection handling doesn't configure connection pooling. In production with multiple Gunicorn workers, this can cause connection exhaustion or performance degradation.

**Current Code:**
```python
# db.py - connection management is per-request but no pooling layer
```

**Recommendations:**
1. Use PgBouncer for connection pooling (in front of Supabase)
2. Or configure `psycopg` connection pool directly
3. Set appropriate min/max pool sizes for Gunicorn worker count
4. Add connection timeout and retry logic

**Improved Implementation:**
```python
from psycopg import pool
import logging

_connection_pool = None

def get_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        app = current_app
        min_size = int(os.environ.get("DB_POOL_MIN", "2"))
        max_size = int(os.environ.get("DB_POOL_MAX", "20"))
        
        _connection_pool = pool.SimpleConnectionPool(
            min_size,
            max_size,
            conninfo=app.config["DATABASE_URL"],
            connect_timeout=5,
            options="-c search_path=public -c statement_timeout=30s"
        )
    return _connection_pool

def get_db_connection():
    pool = get_connection_pool()
    conn = pool.getconn()
    conn.row_factory = dict_row  # If using dict_row
    return conn

def return_db_connection(conn):
    pool = get_connection_pool()
    pool.putconn(conn)
```

---

### 2.3 🟠 HIGH: No Indexes for Common Query Patterns

**Location:** [schoolmind/db.py](schoolmind/db.py) - Schema definition

**Issue:**
The schema has no explicit indexes. While some databases auto-index primary keys, this leaves queries inefficient:

```python
# Queries like these would benefit from indexes:
SELECT * FROM wellbeing_assessments WHERE student_id = ? ORDER BY created_at DESC
SELECT * FROM risk_events WHERE school_id = ? AND status = 'open'
SELECT * FROM users WHERE email = ? 
SELECT * FROM user_preferences WHERE user_id = ?
```

**Recommendations:**
Add comprehensive indexes:

```sql
-- User lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_school_id_role ON users(school_id, role);

-- Wellbeing and assessments
CREATE INDEX idx_wellbeing_assessments_student_created ON wellbeing_assessments(student_id, created_at DESC);
CREATE INDEX idx_wellbeing_assessments_school ON wellbeing_assessments(school_id);

-- Risk events (heavily queried)
CREATE INDEX idx_risk_events_school_status ON risk_events(school_id, status);
CREATE INDEX idx_risk_events_student ON risk_events(student_id);

-- Tokens
CREATE INDEX idx_invite_tokens_token_hash ON invite_tokens(token_hash);
CREATE INDEX idx_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);

-- Messages
CREATE INDEX idx_student_ai_messages_student_created ON student_ai_messages(student_id, created_at DESC);

-- Audit/events
CREATE INDEX idx_audit_events_school_created ON audit_events(school_id, created_at DESC);
CREATE INDEX idx_account_security_events_user ON account_security_events(user_id, created_at DESC);

-- Subscriptions/billing
CREATE INDEX idx_subscriptions_school ON subscriptions(school_id);
CREATE INDEX idx_payment_intents_school ON payment_intents(school_id);

-- Coupons
CREATE INDEX idx_coupon_codes_code ON coupon_codes(code);
```

---

### 2.4 🟠 HIGH: Missing Foreign Key Constraints

**Location:** [schoolmind/db.py](schoolmind/db.py)

**Issue:**
Some relationships lack explicit foreign key constraints:

```python
# created_by references should have ON DELETE SET NULL or CASCADE
"created_by INTEGER," # No FOREIGN KEY in some tables
```

**Recommendations:**
Audit all user/reference relationships to ensure proper constraints exist.

---

## 3. ERROR HANDLING & LOGGING ISSUES

### 3.1 🟠 HIGH: Insufficient Database Error Handling

**Location:** [schoolmind/db.py](schoolmind/db.py)

**Issue:**
Database operations lack granular error handling. When queries fail, errors are often silently caught or result in 500 errors with minimal logging:

```python
def inject_security_context():
    settings = {}
    try:
        from .db import query_all
        settings = {row["key"]: row["value"] for row in query_all("SELECT key, value FROM site_settings")}
    except Exception:  # Too broad
        settings = {}
```

**Recommendations:**
1. Handle specific database exceptions
2. Add proper logging with context
3. Implement circuit breaker pattern for failing databases
4. Add retry logic with exponential backoff

**Improved Error Handling:**
```python
import logging
from psycopg import Error as PsycopgError, DatabaseError, IntegrityError

logger = logging.getLogger(__name__)

def get_site_settings_with_logging():
    settings = {}
    try:
        settings = {row["key"]: row["value"] for row in query_all("SELECT key, value FROM site_settings")}
    except IntegrityError as e:
        logger.error(f"Data integrity error loading site settings: {e}", exc_info=True)
        # Could also send alert
    except DatabaseError as e:
        logger.error(f"Database error loading site settings: {e}", exc_info=True)
        # Return cached settings or defaults
    except PsycopgError as e:
        logger.error(f"PostgreSQL connection error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error loading site settings: {e}", exc_info=True)
    return settings
```

---

### 3.2 🟡 MEDIUM: Generic 500 Error Response

**Location:** [schoolmind/__init__.py](schoolmind/__init__.py#L105)

**Issue:**
```python
@app.errorhandler(500)
def server_error(error):
    app.logger.exception("unhandled_server_error", extra={"request_id": getattr(g, "request_id", "")})
    return render_template("errors/error.html", code=500, title="Server error", message="The server hit an unexpected problem."), 500
```

The error message is too generic for debugging. In production, users can't identify what went wrong.

**Recommendations:**
1. Log full stack trace with request context
2. Generate error ID and show to user
3. Send alerts for certain error types (e.g., OutOfMemory, database connection lost)
4. Add breadcrumb/context information

**Improved Handler:**
```python
@app.errorhandler(500)
def server_error(error):
    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    app.logger.exception(
        "unhandled_server_error",
        extra={
            "request_id": request_id,
            "user_id": getattr(g.user, "id", None) if hasattr(g, "user") else None,
            "school_id": getattr(g.user, "school_id", None) if hasattr(g, "user") else None,
            "endpoint": request.endpoint,
            "method": request.method,
            "path": request.path,
        }
    )
    # Send alert if error type is critical
    if isinstance(error, MemoryError):
        send_alert(f"MemoryError in {app.config['APP_ENV']}: request {request_id}")
    
    return render_template(
        "errors/error.html",
        code=500,
        title="Server error",
        message=f"We encountered an error (ID: {request_id}). Our team has been notified.",
        error_id=request_id
    ), 500
```

---

### 3.3 🟡 MEDIUM: Insufficient Audit Logging

**Location:** [schoolmind/db.py](schoolmind/db.py)

**Issue:**
Audit events are logged but with limited context:

```python
def log_event(action, detail, school_id=None, user_id=None):
    execute(
        "INSERT INTO audit_events (school_id, user_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (school_id, user_id, action, detail, utcnow()),
    )
```

Missing context:
- Request ID
- IP address
- HTTP method/path
- Response status
- Timing information
- Resource identifiers

**Recommendations:**
Add structured audit fields:

```python
def log_event(action, detail, school_id=None, user_id=None, resource_type=None, resource_id=None, ip_address=None, status_code=None):
    ip_address = ip_address or request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    request_id = getattr(g, "request_id", None)
    
    execute(
        """
        INSERT INTO audit_events 
        (school_id, user_id, action, detail, resource_type, resource_id, ip_address, request_id, status_code, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (school_id, user_id, action, detail, resource_type, resource_id, ip_address, request_id, status_code, utcnow()),
    )
```

---

## 4. EMAIL & NOTIFICATION DELIVERY ISSUES

### 4.1 🔴 CRITICAL: Email Delivery Not Production-Ready

**Location:** [schoolmind/services/mailer.py](schoolmind/services/mailer.py)

**Issue:**
Email delivery is completely abstracted but lacks proper implementation:
1. No validation that SMTP is actually configured
2. No retry logic for transient failures
3. No error recovery (emails stuck in "failed" state forever)
4. No rate limiting on SMTP sends
5. No bounce handling or list management

**Current Implementation:**
```python
def deliver_message(row):
    mode = current_app.config.get("EMAIL_DELIVERY_MODE", "queue")
    if mode == "console":
        print(f"[SchoolMind email] To: {row['recipient']} | Subject: {row['subject']}\n{row['body']}")
        return True, "console"
    if mode != "smtp":
        return False, "EMAIL_DELIVERY_MODE is not smtp or console"
    if not smtp_configured():
        return False, "SMTP is not configured"
    try:
        # ... send logic
    except Exception as exc:
        return False, f"SMTP error: {exc}"
```

**Recommendations:**
1. Implement retry queue with exponential backoff
2. Add bounce detection and handling
3. Separate critical emails (password reset) from transactional
4. Add delivery status tracking
5. Implement rate limiting per recipient domain
6. Add templating engine (Jinja2)

**Enhanced Implementation:**
```python
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [60, 300, 1800]  # 1 min, 5 min, 30 min

def dispatch_queued_with_retry(limit=25):
    now = utcnow()
    
    # Find messages ready for retry
    rows = query_all(
        """
        SELECT * FROM outbox_messages 
        WHERE status IN ('queued', 'failed') 
        AND (next_retry_at IS NULL OR next_retry_at <= ?)
        AND retry_count < ?
        ORDER BY created_at ASC 
        LIMIT ?
        """,
        (now, MAX_RETRIES, int(limit)),
    )
    
    sent = 0
    failed_permanent = 0
    
    for row in rows:
        ok, reference = deliver_message_safely(row)
        if ok:
            sent += 1
            execute(
                "UPDATE outbox_messages SET status = 'sent', provider_reference = ?, sent_at = ?, retry_count = ? WHERE id = ?",
                (reference, utcnow(), row["retry_count"], row["id"]),
            )
            logger.info(f"Email delivered: {row['id']} to {row['recipient']}")
        else:
            retry_count = row["retry_count"] + 1
            if retry_count >= MAX_RETRIES:
                failed_permanent += 1
                execute(
                    "UPDATE outbox_messages SET status = 'failed_permanent', provider_reference = ? WHERE id = ?",
                    (reference[:240], row["id"]),
                )
                logger.error(f"Email failed permanently: {row['id']} to {row['recipient']}")
                # Alert admin
                queue_email(
                    None,  # admin school
                    current_app.config.get("SUPPORT_EMAIL"),
                    f"Failed Email Alert: {row['recipient']}",
                    f"Email {row['id']} failed after {MAX_RETRIES} retries: {reference}"
                )
            else:
                next_retry = now + timedelta(seconds=RETRY_DELAYS[retry_count - 1])
                execute(
                    "UPDATE outbox_messages SET status = 'failed', provider_reference = ?, retry_count = ?, next_retry_at = ? WHERE id = ?",
                    (reference[:240], retry_count, next_retry, row["id"]),
                )
                logger.warning(f"Email retry scheduled: {row['id']} (attempt {retry_count}) - {reference}")
    
    return {"sent": sent, "failed_permanent": failed_permanent, "total": len(rows)}
```

---

## 5. PERFORMANCE & SCALABILITY ISSUES

### 5.1 🟠 HIGH: No Caching Strategy

**Location:** All query-heavy endpoints

**Issue:**
No caching implemented for frequently accessed, slowly-changing data:
- Site settings (queried on every request in `inject_security_context`)
- School information
- User preferences
- Coupon codes

**Recommendations:**
1. Implement Redis caching layer
2. Add cache invalidation on updates
3. Cache warm-up on startup
4. Use cache versioning

**Implementation with Flask-Caching:**
```python
from flask_caching import Cache

cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'schoolmind:',
})

# Cache site settings
@cache.cached(timeout=3600, key_prefix='site_settings')
def get_site_settings():
    return {row["key"]: row["value"] for row in query_all("SELECT key, value FROM site_settings")}

# Invalidate on update
@bp.route("/settings/site", methods=["POST"])
def update_site_settings():
    # ... update logic ...
    cache.delete('site_settings')
    return redirect(url_for("admin.settings"))

# Cache user preferences with per-user key
@cache.cached(timeout=3600, key_prefix=lambda user_id: f'user_prefs:{user_id}')
def get_user_preferences(user_id):
    return query_one("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
```

---

### 5.2 🟠 HIGH: CSV Export Lacks Pagination

**Location:** [schoolmind/api.py](schoolmind/api.py#L116)

**Issue:**
The student export query could be very large for schools with thousands of students:

```python
@bp.route("/export/students.csv")
@role_required("admin", "counselor")
def export_students():
    rows = query_all(
        """
        SELECT users.name, users.email, users.group_name,
               COUNT(risk_events.id) AS open_events,
               latest.score AS wellbeing_score,
               ...
        FROM users
        LEFT JOIN risk_events ON ...
        LEFT JOIN wellbeing_assessments AS latest ON ...
        WHERE users.school_id = ? AND users.role = 'student'
        GROUP BY users.id
        ORDER BY users.name
        """,
        (g.user["school_id"],),
    )
```

For a school with 5,000 students, this could take significant time and memory.

**Recommendations:**
1. Stream CSV response with generator
2. Add pagination parameters
3. Allow filtering by date range
4. Pre-generate reports for large schools

**Streaming Implementation:**
```python
from flask import Response, request

@bp.route("/export/students.csv")
@role_required("admin", "counselor")
def export_students_streaming():
    page = request.args.get("page", 1, type=int)
    limit = min(int(request.args.get("limit", 1000)), 5000)  # Max 5000
    offset = (page - 1) * limit
    
    def generate():
        # Header row
        yield "name,email,group,open_events,wellbeing_score,wellbeing_level,wellbeing_focus\n"
        
        rows = query_all(
            """
            SELECT users.name, users.email, users.group_name,
                   COUNT(risk_events.id) AS open_events,
                   latest.score AS wellbeing_score,
                   latest.risk_level AS wellbeing_level,
                   latest.primary_need AS wellbeing_focus
            FROM users
            LEFT JOIN risk_events ON risk_events.student_id = users.id AND risk_events.status = 'open'
            LEFT JOIN wellbeing_assessments AS latest ON ...
            WHERE users.school_id = ? AND users.role = 'student'
            GROUP BY users.id
            ORDER BY users.name
            LIMIT ? OFFSET ?
            """,
            (g.user["school_id"], limit, offset),
        )
        
        writer = csv.writer(StringIO())
        for row in rows:
            writer.writerow([...])
            yield writer.getvalue()
    
    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=students_p{page}.csv"}
    )
```

---

### 5.3 🟡 MEDIUM: Inefficient Wellbeing Assessment Queries

**Location:** [schoolmind/api.py](schoolmind/api.py#L130)

**Issue:**
```python
LEFT JOIN wellbeing_assessments AS latest
  ON latest.student_id = users.id
 AND latest.created_at = (
     SELECT MAX(created_at)
     FROM wellbeing_assessments AS inner_assessment
     WHERE inner_assessment.student_id = users.id
 )
```

This subquery runs for every student, causing N+1 query problem. For 1,000 students, this is 1,001 queries.

**Recommendations:**
Use window functions (PostgreSQL):

```sql
SELECT 
    users.name, users.email, users.group_name,
    COUNT(risk_events.id) AS open_events,
    latest.score AS wellbeing_score,
    latest.risk_level AS wellbeing_level,
    latest.primary_need AS wellbeing_focus
FROM users
LEFT JOIN risk_events ON risk_events.student_id = users.id AND risk_events.status = 'open'
LEFT JOIN LATERAL (
    SELECT score, risk_level, primary_need
    FROM wellbeing_assessments
    WHERE wellbeing_assessments.student_id = users.id
    ORDER BY created_at DESC
    LIMIT 1
) AS latest ON true
WHERE users.school_id = ? AND users.role = 'student'
GROUP BY users.id, latest.score, latest.risk_level, latest.primary_need
ORDER BY users.name
```

Or use CTE (Common Table Expression):

```sql
WITH latest_assessments AS (
    SELECT 
        student_id,
        score,
        risk_level,
        primary_need,
        ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY created_at DESC) AS rn
    FROM wellbeing_assessments
    WHERE school_id = ?
)
SELECT 
    users.name, users.email, users.group_name,
    COUNT(risk_events.id) AS open_events,
    la.score AS wellbeing_score,
    la.risk_level AS wellbeing_level,
    la.primary_need AS wellbeing_focus
FROM users
LEFT JOIN risk_events ON risk_events.student_id = users.id AND risk_events.status = 'open'
LEFT JOIN latest_assessments la ON la.student_id = users.id AND la.rn = 1
WHERE users.school_id = ? AND users.role = 'student'
GROUP BY users.id, la.score, la.risk_level, la.primary_need
ORDER BY users.name
```

---

## 6. CODE QUALITY & MAINTAINABILITY ISSUES

### 6.1 🟡 MEDIUM: Insufficient Code Documentation

**Location:** Throughout codebase

**Issue:**
Complex business logic lacks docstrings and inline comments:

```python
def analyze_wellbeing_assessment(values):
    # No docstring explaining algorithm, domain scoring, etc.
    mood = safe_int(values.get("mood"), 1, 5, 3)
    stress = safe_int(values.get("stress"), 1, 5, 3)
    # ... 40 more lines without explanation
```

**Recommendations:**
Add comprehensive docstrings:

```python
def analyze_wellbeing_assessment(values):
    """
    Analyze an eight-domain student wellbeing assessment and generate risk level and recommendations.
    
    Domain Mapping:
    - mood: Emotional state (1=very low, 5=very high)
    - stress: Perceived stress level (1=no stress, 5=overwhelming)
    - sleep: Sleep quality/duration (1=very poor, 5=excellent)
    - belonging: Sense of belonging (1=isolated, 5=very connected)
    - study_pressure: Academic pressure (1=no pressure, 5=unbearable)
    - focus: Ability to concentrate (1=very distracted, 5=very focused)
    - safety: Feeling of safety (1=unsafe, 5=very safe)
    - support_access: Ability to access support (1=no access, 5=excellent access)
    
    Scoring Algorithm:
    - Base score: 58 (neutral)
    - Each domain contributes +/- (value - 3) * weight
    - Mood: +6, Stress: -7, Sleep: +5, Belonging: +6, Study: -6, Focus: +4, Safety: +9, Support: +5
    
    Risk Levels:
    - urgent: <30 (score) or safety <= 1
    - support: 30-50 or (stress >= 5 AND mood <= 2)
    - watch: 50-75
    - steady: >= 75
    
    Args:
        values: dict with mood, stress, sleep, belonging, study_pressure, focus, safety, support_access
    
    Returns:
        dict with: score, level, primary_need, primary_need_label, recommendation, domain_health
    
    Primary Need Determination:
        Finds the domain with the lowest health score (closest to 1)
        This becomes the focus area for support plans
    """
```

---

### 6.2 🟡 MEDIUM: Repetitive Route Logic

**Location:** [schoolmind/dashboard.py](schoolmind/dashboard.py)

**Issue:**
Similar patterns repeated across role-specific views:

```python
@bp.route("/student")
@role_required("student")
def student_home():
    journals = query_all(...)
    # ...
    return render_template("dashboard/student.html", ...)

@bp.route("/teacher")
@role_required("teacher")
def teacher_home():
    classes = query_all(...)
    # ...
    return render_template("dashboard/teacher.html", ...)
```

**Recommendations:**
1. Create base view class or factory function
2. Use role-based view registry
3. Extract common logic to helpers

**Refactored Approach:**
```python
ROLE_DASHBOARDS = {
    "student": {
        "template": "dashboard/student.html",
        "data_loader": load_student_data,
        "required_role": "student",
    },
    "teacher": {
        "template": "dashboard/teacher.html",
        "data_loader": load_teacher_data,
        "required_role": "teacher",
    },
    # ...
}

def load_student_data(user):
    return {
        "journals": query_all(...),
        # ...
    }

def load_teacher_data(user):
    return {
        "classes": query_all(...),
        # ...
    }

@bp.route("/<role>_home")
@login_required
def dashboard_home(role):
    config = ROLE_DASHBOARDS.get(role)
    if not config or g.user["role"] != config["required_role"]:
        abort(403)
    
    data = config["data_loader"](g.user)
    return render_template(config["template"], **data)
```

---

### 6.3 🟡 MEDIUM: Magic Numbers and Hard-Coded Values

**Location:** Throughout codebase

**Issue:**
Hard-coded limits and parameters scattered across code:

```python
# In rate_limit decorator
@rate_limit("login", max_requests=40, window_seconds=300)

# In security
if next_count >= 5:
    locked_until = (datetime.now(UTC) + timedelta(minutes=15))

# In billingassure
"ai_daily": 20, "ai_daily": 150, "ai_daily": 1000

# In analyzer
score -= 7  # What does 7 mean?
score += (mood - 3) * 6  # Magic 6
```

**Recommendations:**
Create constants module:

```python
# schoolmind/constants.py
# Rate limiting
RATE_LIMIT_LOGIN = 40
RATE_LIMIT_LOGIN_WINDOW = 300

RATE_LIMIT_GOOGLE = 30
RATE_LIMIT_GOOGLE_WINDOW = 300

RATE_LIMIT_CONTACT = 20
RATE_LIMIT_CONTACT_WINDOW = 600

# Security
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 15

GOOGLE_OAUTH_TIMEOUT = 600  # 10 minutes

# Feature limits per plan
FEATURE_LIMITS = {
    "starter": {
        "ai_daily": 20,
        "active_goals": 3,
        "games": True,
    },
    # ...
}

# Wellbeing scoring
WELLBEING_DOMAIN_WEIGHTS = {
    "mood": 6,
    "stress": -7,
    "sleep": 5,
    "belonging": 6,
    "study_pressure": -6,
    "focus": 4,
    "safety": 9,
    "support_access": 5,
}

WELLBEING_BASE_SCORE = 58

WATCH_SCORE_THRESHOLD = 50
SUPPORT_SCORE_THRESHOLD = 30

# Then import and use
from .constants import (
    RATE_LIMIT_LOGIN, MAX_FAILED_LOGIN_ATTEMPTS,
    WELLBEING_DOMAIN_WEIGHTS, WELLBEING_BASE_SCORE
)
```

---

## 7. TESTING & QA ISSUES

### 7.1 🟡 MEDIUM: Limited Test Coverage for Error Cases

**Location:** [run_tests.py](run_tests.py)

**Issue:**
51 tests provide happy-path coverage but lack negative test cases:
- Rate limit enforcement not tested
- Error recovery scenarios
- Database connection failures
- Concurrent request handling
- Malformed input handling
- Token expiration edge cases

**Current Test Coverage:**
- ✓ Public pages load
- ✓ Login flow (demo account)
- ✓ Student workflows
- ✓ CSV export
- ✗ Rate limit enforcement
- ✗ Malformed input
- ✗ Database errors
- ✗ Concurrent access
- ✗ Token edge cases

**Recommendations:**
Add comprehensive test suite:

```python
class SchoolMindSecurityTests(unittest.TestCase):
    def test_rate_limit_login_enforcement(self):
        """Verify rate limiting works on login endpoint"""
        for i in range(45):  # Try 45 times (limit is 40)
            response = self.post_with_csrf(
                "/login",
                {"email": "test@example.com", "password": "wrong"},
                follow_redirects=False
            )
            if i < 40:
                self.assertNotEqual(response.status_code, 429, f"Rate limited too early at attempt {i}")
            else:
                self.assertEqual(response.status_code, 429, f"Not rate limited at attempt {i}")
    
    def test_password_reset_token_expiration(self):
        """Verify expired password reset tokens are rejected"""
        # Generate reset token
        response = self.post_with_csrf("/forgot-password", {"email": "student@schoolmind.ai"})
        
        # Extract token
        with self.app.app_context():
            token_record = query_one("SELECT * FROM password_reset_tokens ORDER BY created_at DESC LIMIT 1")
        
        # Manually expire the token
        with self.app.app_context():
            execute(
                "UPDATE password_reset_tokens SET expires_at = ? WHERE id = ?",
                ((datetime.now(UTC) - timedelta(hours=1)).isoformat(), token_record["id"])
            )
        
        # Try to use expired token
        response = self.client.post(
            f"/reset-password/{token_record['token']}",
            data={"password": "newpass123", "csrf_token": "dummy"},
            follow_redirects=True
        )
        self.assertIn(b"expired", response.data.lower())
    
    def test_malformed_email_input(self):
        """Verify input validation on email fields"""
        test_cases = [
            "",
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "with space@test.com",
            "with\x00null@test.com",
        ]
        for email in test_cases:
            response = self.post_with_csrf("/contact", {
                "name": "Test",
                "email": email,
                "school_name": "Test School",
                "message": "This is a test message."
            })
            self.assertNotIn(b"Message captured", response.data, f"Accepted invalid email: {repr(email)}")
    
    def test_role_boundary_enforcement(self):
        """Verify role-based access control"""
        self.login("student@schoolmind.ai")
        
        admin_endpoints = [
            "/admin",
            "/admin/users",
            "/admin/billing",
            "/admin/settings",
        ]
        
        for endpoint in admin_endpoints:
            response = self.client.get(endpoint, follow_redirects=False)
            self.assertEqual(response.status_code, 403, f"Student accessed admin endpoint: {endpoint}")
    
    def test_concurrent_request_handling(self):
        """Verify app handles concurrent requests from same session"""
        import threading
        import time
        
        results = []
        
        def make_request():
            with self.app.test_client() as client:
                response = client.get("/")
                results.append(response.status_code)
        
        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(results), 10)
        self.assertTrue(all(code == 200 for code in results))
```

---

### 7.2 🟡 MEDIUM: No Load Testing

**Location:** Not present

**Issue:**
No load tests to verify performance under stress:
- Concurrent user handling
- Database query performance
- Memory usage
- Response time degradation

**Recommendations:**
Implement load testing:

```bash
# Install locust
pip install locust

# Create locustfile.py
from locust import HttpUser, task, between

class SchoolMindUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def student_login(self):
        self.client.get("/login")
        self.client.post("/login", {
            "email": "student@schoolmind.ai",
            "password": "demo12345",
            "csrf_token": self.get_csrf_token()
        })
    
    @task(2)
    def view_dashboard(self):
        self.client.get("/student")
    
    @task(1)
    def take_assessment(self):
        self.client.post("/wellbeing-assessment", {...})
    
    def get_csrf_token(self):
        response = self.client.get("/login")
        # Extract CSRF token from response
        return "token"

# Run: locust -f locustfile.py -u 100 -r 10 -t 5m
```

---

## 8. SECURITY & COMPLIANCE ISSUES

### 8.1 🟡 MEDIUM: Missing Two-Factor Authentication (2FA)

**Location:** Authentication system

**Issue:**
Critical for a student data platform, currently no 2FA support.

**Recommendations:**
1. Implement TOTP (Time-based One-Time Password) via authenticator apps
2. Add backup recovery codes
3. Require 2FA for admin accounts
4. Make optional for regular users

**Implementation Steps:**
```python
# Install pyotp
pip install pyotp

# In user model/preferences, add:
# - totp_secret (encrypted)
# - totp_enabled (boolean)
# - recovery_codes (encrypted list)

def setup_2fa(user_id):
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    
    # Generate 10 recovery codes
    recovery_codes = [secrets.token_hex(4) for _ in range(10)]
    
    return {
        "secret": secret,
        "provisioning_uri": totp.provisioning_uri(
            name=g.user["email"],
            issuer_name="SchoolMind"
        ),
        "recovery_codes": recovery_codes
    }

def verify_2fa(user_id, token):
    user_secret = query_one(
        "SELECT totp_secret FROM users WHERE id = ?",
        (user_id,)
    )
    totp = pyotp.TOTP(user_secret)
    return totp.verify(token)
```

---

### 8.2 🟡 MEDIUM: Data Deletion Not Comprehensive

**Location:** Admin retention cleanup

**Issue:**
Current retention cleanup may not completely remove student data:

```python
# Current approach likely only deletes from primary tables
# Orphaned records in related tables remain
```

**Recommendations:**
Comprehensive data deletion with cascade:

```python
def delete_student_data(school_id, student_id):
    """
    Completely remove student data and all related records.
    Respects audit/compliance requirements.
    """
    with transaction() as db:
        # Get student name for audit
        student = query_one("SELECT name, email FROM users WHERE id = ?", (student_id,))
        
        # Delete or anonymize as required:
        tables_to_delete = [
            "wellbeing_assessments",
            "checkins",
            "journal_entries",
            "student_support_plans",
            "student_goals",
            "game_scores",
            "breathing_sessions",
            "student_ai_messages",
            "support_requests",
            "interventions",
            "consent_records",
            # Do NOT delete from audit_events - compliance requirement
        ]
        
        for table in tables_to_delete:
            db.execute(
                f"DELETE FROM {table} WHERE school_id = ? AND student_id = ?",
                (school_id, student_id)
            )
        
        # Anonymize user record
        db.execute(
            "UPDATE users SET name = '[DELETED]', email = ?, is_active = 0 WHERE id = ?",
            (f"deleted-{student_id}@schoolmind-internal.invalid", student_id)
        )
        
        # Log the deletion
        db.execute(
            "INSERT INTO audit_events (school_id, user_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (school_id, g.user["id"], "student_data_deleted", f"Student {student['email']} deleted", utcnow())
        )
        
        return True, f"Student {student['email']} data deletion complete"
```

---

## 9. UI/UX & ACCESSIBILITY ISSUES

### 9.1 🟡 MEDIUM: WCAG 2.1 Compliance Not Validated

**Location:** All templates

**Issue:**
No automated accessibility testing. Templates may have:
- Missing alt text on images
- Poor color contrast
- Missing ARIA labels
- Keyboard navigation issues
- Screen reader compatibility

**Recommendations:**
1. Add automated accessibility testing
2. Run WCAG 2.1 Level AA validation
3. Test with screen readers (NVDA, JAWS)
4. Implement keyboard-only navigation

**Tools & Implementation:**
```bash
# Install axe accessibility testing
pip install axe-selenium-python

# Add accessibility test
def test_home_page_accessibility():
    browser = webdriver.Chrome()
    browser.get("http://localhost:5000")
    
    from axe_selenium_python import Axe
    axe = Axe(browser)
    axe.inject()
    axe.run()
    results = axe.report()
    
    # Check for violations
    assert not results["violations"], f"Accessibility violations: {results['violations']}"
```

Also add inline checks:
```html
<!-- Good: Alt text, ARIA label -->
<img src="icon.svg" alt="Student wellbeing score icon" aria-label="Wellbeing assessment">

<!-- Good: Proper heading hierarchy -->
<h1>Student Console</h1>
<h2>This Week's Summary</h2>

<!-- Good: Color contrast check -->
<span style="color: #666; background: #fff;">Good contrast ratio 4.5:1</span>

<!-- Good: Keyboard navigation -->
<button aria-label="Close menu" tabindex="0">✕</button>

<!-- Good: Screen reader only content -->
<span class="sr-only">current page: student dashboard</span>
```

---

### 9.2 🟡 MEDIUM: Mobile Responsiveness Not Fully Validated

**Location:** static/css/ and templates

**Issue:**
Mobile drawer navigation exists but viewport optimization unclear:
- No device testing mentioned
- CSS may not use mobile-first approach
- Touch target sizes may be too small
- Font sizes may be hard to read on mobile

**Recommendations:**
1. Test on actual devices
2. Validate touch target sizes (min 44x44 pixels)
3. Test portrait and landscape
4. Verify text readability

**Mobile Validation Checklist:**
```html
<!-- Ensure viewport meta tag -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">

<!-- Touch target size validation -->
<style>
  /* Minimum 44x44 for touch targets */
  button, a, input[type="checkbox"], input[type="radio"] {
    min-height: 44px;
    min-width: 44px;
    padding: 0.5rem;
  }
  
  /* Mobile-first responsive text -->
  body {
    font-size: 16px; /* No less than 16px on mobile */
    line-height: 1.5;
  }
  
  h1 { font-size: clamp(1.5rem, 5vw, 2.5rem); }
  
  /* Mobile-friendly layout */
  @media (max-width: 600px) {
    .sidebar { display: none; }
    main { padding: 1rem; }
  }
</style>
```

---

## 10. DEPLOYMENT & OPERATIONS ISSUES

### 10.1 🔴 CRITICAL: Missing Environment Variable Validation on Boot

**Location:** [schoolmind/__init__.py](schoolmind/__init__.py)

**Issue:**
Some critical environment variables aren't validated on startup. If they're missing, the app may start but fail at runtime:

```python
CHECKOUT_STARTER_URL=os.environ.get("CHECKOUT_STARTER_URL", ""),
BILLING_WEBHOOK_SECRET=os.environ.get("BILLING_WEBHOOK_SECRET", ""),
```

Missing these in production causes silent failures.

**Recommendations:**
Validate required env vars on startup:

```python
def validate_runtime_config(app):
    """Ensure all required environment variables are set in production"""
    app_env = app.config.get("APP_ENV", "development")
    
    if app_env != "production":
        return  # Skip validation in dev/test
    
    required_vars = {
        "SECRET_KEY": "Session encryption key (min 32 chars)",
        "DATABASE_URL": "PostgreSQL connection string",
        "PUBLIC_BASE_URL": "Public domain URL",
        "PLATFORM_ADMIN_EMAIL": "Platform admin email",
        "PLATFORM_ADMIN_PASSWORD": "Platform admin password",
    }
    
    # Checkout URLs optional if not accepting payments
    payments_enabled = any(
        os.environ.get(f"CHECKOUT_{plan.upper()}_URL")
        for plan in ("starter", "growth", "scale")
    )
    if payments_enabled:
        required_vars["BILLING_WEBHOOK_SECRET"] = "Webhook signature secret"
    
    missing = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing.append(f"{var}: {description}")
    
    if missing:
        raise RuntimeError(
            f"Missing required environment variables in {app_env}:\n" +
            "\n".join(f"  - {item}" for item in missing)
        )
    
    # Validate SECRET_KEY strength
    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError(f"SECRET_KEY must be at least 32 characters (got {len(secret)})")
    
    # Validate passwords aren't defaults
    platform_password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "")
    if platform_password in ("demo12345", "password", "admin123"):
        raise RuntimeError("PLATFORM_ADMIN_PASSWORD cannot be a default/weak password")
    
    app.logger.info(f"Runtime configuration validated for {app_env}")
```

---

### 10.2 🟠 HIGH: Missing Health Check Endpoint Readiness

**Location:** [schoolmind/api.py](schoolmind/api.py#L8)

**Issue:**
Health and readiness endpoints exist but Gunicorn doesn't check them before marking service ready:

```python
@bp.route("/health")
def health():
    return {"ok": True, "service": "schoolmind-ai"}

@bp.route("/readiness")
def readiness():
    # Checks database, schema, etc.
    ...
```

But there's no startup probe configuration.

**Recommendations:**
Add proper startup/liveness/readiness probes:

```yaml
# render.yaml or kubernetes config
healthCheck:
  path: /api/health
  checkIntervalSeconds: 10
  initialDelaySeconds: 30
  timeoutSeconds: 5
  unhealthyThreshold: 3
  healthyThreshold: 2

startupProbe:
  path: /api/readiness
  checkIntervalSeconds: 5
  initialDelaySeconds: 0
  timeoutSeconds: 5
  failureThreshold: 60  # 5 minutes max startup time

livenessProbe:
  path: /api/health
  checkIntervalSeconds: 30
  initialDelaySeconds: 60
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  path: /api/readiness
  checkIntervalSeconds: 10
  initialDelaySeconds: 10
  timeoutSeconds: 5
  failureThreshold: 2
```

And update the handlers:
```python
@bp.route("/api/health")
def health():
    """Lightweight liveness check"""
    return {"ok": True, "timestamp": utcnow()}, 200

@bp.route("/api/readiness")
def readiness():
    """Startup/readiness check - ensures service is ready to receive requests"""
    checks = {
        "database": check_database(),
        "schema": check_schema_version(),
        "configuration": check_required_config(),
        "memory": check_memory_available(),
    }
    
    all_ready = all(check["ok"] for check in checks.values())
    status_code = 200 if all_ready else 503
    
    return {
        "ok": all_ready,
        "checks": checks,
        "timestamp": utcnow(),
    }, status_code
```

---

### 10.3 🟠 HIGH: No Graceful Shutdown Handler

**Location:** WSGI/Gunicorn configuration

**Issue:**
No cleanup on shutdown - tasks may be left incomplete:
- Unsent emails in outbox
- Incomplete transactions
- Active user sessions not properly logged out

**Recommendations:**
Add signal handlers:

```python
# In create_app()
import signal

def shutdown_handler(signum, frame):
    """Handle graceful shutdown"""
    app.logger.info(f"Received signal {signum}, starting graceful shutdown...")
    
    # Flush email queue
    try:
        from .services.mailer import dispatch_queued
        result = dispatch_queued(limit=100)
        app.logger.info(f"Flushed emails: {result['sent']} sent, {result['failed']} failed")
    except Exception as e:
        app.logger.error(f"Error flushing email queue: {e}")
    
    # Cleanup database connections
    try:
        close_db()
        app.logger.info("Database connections closed")
    except Exception as e:
        app.logger.error(f"Error closing database: {e}")
    
    app.logger.info("Graceful shutdown complete")
    exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

return app
```

---

## 11. DOCUMENTATION & KNOWLEDGE ISSUES

### 11.1 🟡 MEDIUM: Architecture Documentation Missing

**Location:** No ADR (Architecture Decision Records)

**Issue:**
No documented rationale for architectural decisions:
- Why string dates instead of TIMESTAMP?
- Why in-memory rate limiting instead of Redis?
- Why raw SQL instead of ORM?

**Recommendations:**
Create ADR (Architecture Decision Record) files:

```markdown
# ADR-001: Database Schema Design

## Decision
Use text-based ISO 8601 timestamps instead of native TIMESTAMP/DATETIME types

## Context
- Support for both SQLite (dev) and PostgreSQL (prod)
- Simpler migration path during development
- Easier to serialize to JSON for APIs

## Consequences
- ❌ Cannot use SQL date functions for queries
- ❌ No database-level date validation
- ❌ Sorting less efficient
- ✓ Format predictable across environments
- ✓ Easier debugging

## Alternatives Considered
1. Use TIMESTAMP with conversion layer - chosen for simplicity
2. Use Unix timestamps - chose ISO 8601 for readability
3. Mixed approach - too complex

## Status
SUPERSEDED - should migrate to native TIMESTAMP in v2

---

# ADR-002: Rate Limiting Strategy

## Decision
Use in-memory Python dictionary for rate limiting instead of Redis

## Context
- MVP doesn't require horizontal scaling
- Keep dependencies minimal
- Fast local memory access

## Consequences
- ❌ Memory leaks with unbounded growth
- ❌ Doesn't work across multiple instances
- ✓ No external dependency
- ✓ Simple implementation

## Alternatives Considered
1. Redis - chosen for MVP simplicity
2. Database table - too slow
3. Distributed cache - overkill for single-instance

## Status
ACTIVE - consider Redis before scaling beyond 1-2 instances

---

# ADR-003: SQL vs ORM

## Decision
Use raw parameterized SQL instead of SQLAlchemy ORM

## Context
- Simpler dependency management
- More control over queries
- Educational transparency

## Consequences
- ❌ More verbose query code
- ❌ No query builder safety
- ❌ Boilerplate for object mapping
- ✓ Explicit query performance
- ✓ Easier to optimize

## Status
ACTIVE - reconsider if query complexity grows
```

---

### 11.2 🟡 MEDIUM: API Documentation Missing

**Location:** No OpenAPI/Swagger docs

**Issue:**
API endpoints lack formal documentation:
- No parameter descriptions
- No response schema definitions
- No error code documentation

**Recommendations:**
Add OpenAPI documentation:

```bash
# Install flask-openapi
pip install flask-openapi3

# Add to app initialization
from flask_openapi3 import OpenAPI

app = OpenAPI(__name__)

# Document endpoints
@app.get(
    "/api/export/students.csv",
    summary="Export student data",
    description="Export list of students with latest wellbeing assessment and open risk events",
    tags=["Export"],
    responses={
        "200": {
            "description": "CSV file with student data",
            "content": {"text/csv": {}}
        },
        "401": {"description": "Unauthorized"},
        "403": {"description": "Insufficient permissions"}
    }
)
@role_required("admin", "counselor")
def export_students():
    ...
```

---

## 12. TESTING & RELIABILITY ISSUES

### 12.1 🟡 MEDIUM: No Chaos Engineering Tests

**Location:** Testing infrastructure

**Issue:**
No tests for failure scenarios:
- Database connection dropped
- Timeout during request
- Memory exhaustion
- Disk full
- Clock skew

**Recommendations:**
Add resilience tests:

```python
class SchoolMindResilienceTests(unittest.TestCase):
    def test_database_connection_failure_recovery(self):
        """Verify app recovers when database becomes unavailable"""
        # Simulate connection error
        with patch('schoolmind.db.get_db') as mock_db:
            mock_db.side_effect = DatabaseError("Connection refused")
            
            response = self.client.get("/api/health")
            self.assertEqual(response.status_code, 503)
            self.assertFalse(response.json["ok"])
    
    def test_request_timeout_handling(self):
        """Verify long queries are terminated"""
        with patch('schoolmind.db.query_all') as mock_query:
            # Simulate timeout
            mock_query.side_effect = TimeoutError("Query exceeded 30 seconds")
            
            response = self.client.get("/api/export/students.csv")
            self.assertIn(response.status_code, [408, 503, 504])
    
    def test_memory_pressure_graceful_degradation(self):
        """Verify app degrades gracefully under memory pressure"""
        # Allocate large object
        large_data = [0] * 100_000_000
        
        # Should still handle requests
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        
        # Clean up
        del large_data
```

---

## CRITICAL ACTION ITEMS

| Priority | Category | Issue | Action | Effort |
|----------|----------|-------|--------|--------|
| 🔴 P0 | Security | Unbounded rate limit memory | Implement cleanup or Redis | Medium |
| 🔴 P0 | Data | String dates instead of TIMESTAMP | Migrate schema | Large |
| 🔴 P0 | Production | Missing env var validation | Add startup checks | Small |
| 🟠 P1 | Security | Weak CSP with unsafe-inline | Extract styles to CSS | Medium |
| 🟠 P1 | Email | No production email delivery | Implement retry logic | Large |
| 🟠 P1 | Performance | No caching strategy | Add Redis caching | Large |
| 🟠 P1 | Performance | N+1 database queries | Optimize queries | Medium |
| 🟠 P1 | Security | Password reset token expiration | Add TTL validation | Small |
| 🟡 P2 | Testing | Limited negative test cases | Add comprehensive tests | Large |
| 🟡 P2 | Docs | No architecture documentation | Create ADRs | Medium |
| 🟡 P2 | Accessibility | WCAG compliance not validated | Add accessibility testing | Medium |

---

## RECOMMENDATIONS BY PRIORITY

### Immediate (Before Production Data)
1. ✅ Implement rate limit cleanup
2. ✅ Add environment variable validation
3. ✅ Fix password reset token expiration
4. ✅ Extract inline CSP styles
5. ✅ Add database connection pooling

### Short-term (Next Sprint)
1. ✅ Implement email retry logic with exponential backoff
2. ✅ Add Redis caching for site settings and preferences
3. ✅ Optimize database queries (eliminate N+1)
4. ✅ Add comprehensive negative test cases
5. ✅ Implement 2FA for admin accounts

### Medium-term (v1.1)
1. ✅ Migrate string dates to TIMESTAMP columns
2. ✅ Add comprehensive accessibility testing
3. ✅ Implement session fingerprinting
4. ✅ Add API documentation (OpenAPI/Swagger)
5. ✅ Create architecture decision records

### Long-term (Future Versions)
1. ✅ Implement full WCAG 2.1 AA compliance
2. ✅ Add GraphQL API layer
3. ✅ Implement multi-school admin dashboard
4. ✅ Add advanced analytics and reporting
5. ✅ Implement machine learning for risk prediction

---

## CONCLUSION

SchoolMind AI is a well-structured, feature-complete MVP with solid security fundamentals. The codebase demonstrates good practices in multi-tenant isolation, CSRF protection, and parameterized SQL.

However, before deploying with real student data, the project should address:
1. **Security**: Rate limiting memory leaks, CSP weakness, token expiration
2. **Reliability**: Database connection pooling, email delivery retry, error handling
3. **Performance**: Caching strategy, query optimization, N+1 elimination
4. **Compliance**: Accessibility testing, data deletion completeness
5. **Operations**: Environment variable validation, graceful shutdown, health checks

With these improvements, the platform would be significantly more robust and production-ready for handling critical educational data at scale.

---

**Review Completed:** July 3, 2026
**Reviewer:** Code Analysis Agent
**Status:** Ready for Operator Implementation
