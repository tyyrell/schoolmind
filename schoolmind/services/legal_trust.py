"""Public legal/trust content helpers for SchoolMind AI.

These structures keep public trust pages consistent. They are product-readiness
content, not jurisdiction-specific legal advice.
"""

LEGAL_NOTICE = (
    "These pages are product-readiness drafts for school evaluation. A production "
    "deployment should be reviewed by qualified counsel for the countries, school "
    "types, student ages, and data processors involved."
)

PRIVACY_COMMITMENTS = [
    {
        "title": "School-controlled workspaces",
        "body": "SchoolMind AI is designed so each school operates in its own workspace with role-based access and school-owned governance decisions.",
    },
    {
        "title": "Student data minimization",
        "body": "Collect only what the school needs for supervised educational support. Avoid importing real student data during evaluation until consent and policy are ready.",
    },
    {
        "title": "Role privacy by default",
        "body": "Teachers should work from aggregate classroom indicators. Private journals, counselor notes, and sensitive workflows belong behind stricter permissions.",
    },
    {
        "title": "Human review before action",
        "body": "AI-assisted indicators support review; they do not make final decisions, assign diagnoses, or replace school support staff.",
    },
    {
        "title": "Retention with a reason",
        "body": "Support records should have a school-approved retention window, export process, and deletion workflow instead of staying forever by accident.",
    },
    {
        "title": "Provider transparency",
        "body": "Hosting, database, email, billing, analytics, and optional AI providers must be listed before production use.",
    },
]

DATA_RIGHTS_WORKFLOW = [
    "Identify the requester and the school workspace involved.",
    "Confirm whether the school, guardian, student, or authorized staff member can make the request.",
    "Locate relevant account, support, journal, consent, audit, and export records.",
    "Review safety, legal hold, and school policy constraints before deletion or export.",
    "Record the action in an audit trail and notify the authorized school contact.",
]

DPA_SECTIONS = [
    {
        "title": "Roles and instructions",
        "body": "The school defines permitted use, student scope, staff access, consent requirements, and data processing instructions.",
    },
    {
        "title": "Processing purpose",
        "body": "Processing is limited to educational wellbeing indicators, support workflows, account administration, security, billing, and support.",
    },
    {
        "title": "Confidentiality and access",
        "body": "Access should be restricted to authorized personnel, protected by authentication, and logged for sensitive administrative actions.",
    },
    {
        "title": "Subprocessors",
        "body": "The production operator must publish enabled infrastructure, email, billing, analytics, and AI providers before live deployment.",
    },
    {
        "title": "Retention and deletion",
        "body": "The school and operator should define retention windows, export handling, backup expiry, and deletion request procedures.",
    },
    {
        "title": "Security incidents",
        "body": "Suspected incidents should be triaged, contained, documented, and communicated to affected schools under a defined incident workflow.",
    },
]

STUDENT_NOTICE_POINTS = [
    {
        "title": "What students should know",
        "body": "SchoolMind AI is a school support tool. It helps authorized adults understand patterns and coordinate help; it is not a private social network or medical service.",
    },
    {
        "title": "Who may see information",
        "body": "Visibility depends on the school role. Teachers receive limited educational context; counselors and admins may have broader support access where school policy allows.",
    },
    {
        "title": "What not to enter",
        "body": "Students should not use the platform for emergencies or share information they would not want handled under school support policy.",
    },
    {
        "title": "Questions and requests",
        "body": "Students and guardians should know who at the school can answer privacy questions, correct records, or help with access requests.",
    },
]

INCIDENT_RESPONSE_STEPS = [
    {
        "title": "1. Triage",
        "body": "Classify the report, affected workspace, data category, user roles, and likely severity.",
    },
    {
        "title": "2. Contain",
        "body": "Disable affected credentials, restrict risky routes, rotate secrets where needed, and preserve logs.",
    },
    {
        "title": "3. Investigate",
        "body": "Review audit events, application logs, database access, email queue events, and provider dashboards.",
    },
    {
        "title": "4. Notify",
        "body": "Notify the school contact and required parties according to the signed agreement and local obligations.",
    },
    {
        "title": "5. Remediate",
        "body": "Patch the cause, verify isolation, restore safe operations, and document lessons learned.",
    },
]

LEGAL_READINESS_MATRIX = [
    ("Privacy policy", "Drafted in product", "Needs jurisdiction and school-contract review"),
    ("DPA", "Template structure provided", "Needs final controller/processor terms"),
    ("Subprocessors", "Categories listed", "Must list actual enabled providers and regions"),
    ("Retention", "Policy and product settings prepared", "Must align with school policy and backups"),
    ("Student notice", "Plain-language page provided", "Must adapt to age, language, and school rules"),
    ("Incident response", "Public overview and runbook direction", "Needs named owner, SLA, and provider contacts"),
]
