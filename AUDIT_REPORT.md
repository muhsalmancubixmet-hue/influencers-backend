# Comprehensive Security, Scalability & Architecture Audit Report

**Target Codebase:** Influencers.com Multi-Portal Platform (`d:\project\fadi\3`)  
**Audit Date:** November 9, 2026  
**Auditor Role:** Senior Application Security Engineer & Software Architect  
**Audit Scope:** Full codebase read-only analysis (Backend Django REST & Channels, 4x TanStack Start Frontends, Database Schema, Authentication & RBAC, File Uploads, Environment & Secret Handling, Third-Party Integrations).

---

## 1. Project Summary

The **Influencers.com Platform** is a multi-tenant creator-brand marketplace and SaaS platform composed of a unified Django 6.1 REST/ASGI backend and four dedicated frontend applications:
1. **Public Marketplace Portal** (`kerala-creator-collab`): Discovery feed, campaign opportunities, and public collaboration inquiry dispatch.
2. **Creator Workspace** (`creator-hub`): Creator portfolio builder, rates/services, social profile linkers, direct inquiry messaging, and custom website builder.
3. **Brand / Business Portal** (`creator-connect-hub`): Brand onboarding, campaign management, creator shortlisting, analytics, and inquiry management.
4. **Admin Control Panel** (`pixel-perfect-replication`): System operations, 6-tier RBAC role templates, 14-module clearance matrix, domain verification, and financial ledger.

The backend leverages Django REST Framework (DRF), SimpleJWT authentication, Django Channels with Daphne (WebSockets), Celery task queuing, and Upstash Redis. Frontends are constructed on TanStack Start (React 19, TypeScript, Vite, Tailwind CSS v4, Nitro/Cloudflare Wrangler).

---

## 2. Executive Summary

| Dimension | Score | Status |
| :--- | :---: | :--- |
| **Security Score** | **2.5 / 10** | **CRITICAL RISKS** |
| **Scalability Score** | **2.0 / 10** | **UNSUITABLE FOR CONCURRENT PRODUCTION** |
| **Maintainability Score** | **5.5 / 10** | **MODERATE (Clean model structure, 0% test coverage)** |

### Is this project production-ready?
> [!CAUTION]
> **NO, IT IS NOT PRODUCTION-READY.**
> 
> The codebase contains a **CVSS 10.0 Critical Authentication Bypass** in the email verification endpoint that allows anyone to log into any user or administrator account knowing only their email address. Furthermore, live Google SMTP credentials and Upstash Redis connection strings are stored in an ungitignored `.env` file, wildcard CORS credentials are enabled (`CORS_ALLOW_ALL_ORIGINS = True` with `CORS_ALLOW_CREDENTIALS = True`), file uploads accept arbitrary extensions without validation (Stored XSS / RCE risk), financial refunds have concurrency race conditions, WebSockets fail for creators due to model attribute mismatches, and the backend is wired to a local SQLite database with an in-memory Channels layer and 0% test coverage.

---

## 3. Comprehensive Findings Table

| ID | Severity | Category | File Path and Line Number | Issue | Why It Matters | Recommended Fix |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-CRIT-01** | **Critical** | Authentication | [services.py](file:///d:/project/fadi/3/backend/apps/accounts/api/v1/services.py#L484-L493) | Complete authentication bypass via invalid token fallback | Anyone can log in as any user (including Super Admin) by providing an invalid token and the victim's email. | Remove fallback email user resolution; reject requests with invalid/expired tokens. |
| **SEC-CRIT-02** | **Critical** | Secrets Management | [.env](file:///d:/project/fadi/3/backend/.env#L12-L71) | Plaintext credentials & secrets stored in ungitignored file | Live Google App Password, Redis URI with password, and Django SECRET_KEY are exposed. | Rotate credentials immediately, add `.gitignore` to backend, use secret manager or inject via environment. |
| **SEC-CRIT-03** | **Critical** | Network / CORS | [settings.py](file:///d:/project/fadi/3/backend/core/settings.py#L222-L223) | `CORS_ALLOW_ALL_ORIGINS = True` with `CORS_ALLOW_CREDENTIALS = True` | Cross-origin credential theft and CSRF-like data exfiltration from any arbitrary third-party site. | Set `CORS_ALLOW_ALL_ORIGINS = False` and strictly restrict to whitelisted portal origins. |
| **SEC-CRIT-04** | **Critical** | File Upload / XSS | [views.py](file:///d:/project/fadi/3/backend/apps/creators/api/v1/views.py#L446-L454) | Unrestricted file upload extension & MIME type | Allows uploading `.html`, `.svg`, `.exe`, or scripts served directly from `/media/`, enabling Stored XSS and server resource exhaustion. | Enforce file extension whitelist, validate file magic bytes with `python-magic`, and enforce maximum upload size. |
| **SEC-HIGH-01** | **High** | Rate Limiting | [settings.py](file:///d:/project/fadi/3/backend/core/settings.py#L235-L250) | Total absence of API rate limiting across entire application | Attackers can brute-force passwords, trigger mass registration, spam SMS/email, and DoS the application. | Configure `DEFAULT_THROTTLE_CLASSES` and `DEFAULT_THROTTLE_RATES` (e.g., Anon 10/min, User 100/min). |
| **SEC-HIGH-02** | **High** | WebSocket / RBAC | [consumers.py](file:///d:/project/fadi/3/backend/apps/campaigns/consumers.py#L38-L41) | Attribute mismatch `influencer_profile` instead of `creator_profile` | WebSocket chat closes with 4403 for all creators; creators cannot participate in real-time inquiry chats. | Change `user.influencer_profile` to `user.creator_profile` and use `photo_url` instead of `profile_photo_url`. |
| **SEC-HIGH-03** | **High** | Data Exposure / Auth | [ws_auth.py](file:///d:/project/fadi/3/backend/apps/common/ws_auth.py#L41-L58), [use-inquiry-socket.ts](file:///d:/project/fadi/3/creator-hub/src/lib/use-inquiry-socket.ts#L56) | JWT bearer token sent in URL query parameters over unencrypted `ws://` | Tokens are persisted in proxy logs, server access logs, browser history, and exposed in plain transit. | Authenticate via WebSocket subprotocol or cookie; dynamically resolve protocol (`wss://`) and host. |
| **SEC-HIGH-04** | **High** | Financial Safety | [services.py](file:///d:/project/fadi/3/backend/apps/billing/api/v1/services.py#L31-L60) | Concurrency race condition in refund processing without row locking | Simultaneous refund requests can exceed total payment balance, causing financial loss. | Wrap query in `transaction.atomic()` with `select_for_update()` on the `Payment` record. |
| **SEC-HIGH-05** | **High** | Authorization / IDOR | [services.py](file:///d:/project/fadi/3/backend/apps/campaigns/api/v1/services.py#L214-L236) | Unauthenticated user account & profile hijacking via public inquiry | Public inquiry endpoint automatically attaches a `BusinessProfile` to existing user accounts without credentials. | Require authentication or guest account verification before linking inquiries to existing registered emails. |
| **SEC-HIGH-06** | **High** | Information Disclosure | [__root.tsx](file:///d:/project/fadi/3/kerala-creator-collab/src/routes/__root.tsx#L79-L83) | Production error boundary leaks full JavaScript stack trace to users | System paths, code structure, component hierarchies, and internal errors are displayed in the browser. | Conditionally hide `error.stack` in production environments (`import.meta.env.PROD`). |
| **SEC-MED-01** | **Medium** | Scalability / DB | [settings.py](file:///d:/project/fadi/3/backend/core/settings.py#L115-L120) | SQLite configured as production database engine | Database file locking under concurrent writes halts application; cannot be horizontally clustered. | Migrate to PostgreSQL with connection pooling (e.g. PgBouncer or Django persistent connections). |
| **SEC-MED-02** | **Medium** | Scalability / Channels | [settings.py](file:///d:/project/fadi/3/backend/core/settings.py#L105-L109) | `InMemoryChannelLayer` used for Django Channels | Real-time messages fail to route across multiple Daphne workers, containers, or host instances. | Switch `CHANNEL_LAYERS` backend to `channels_redis.core.RedisChannelLayer`. |
| **SEC-MED-03** | **Medium** | Performance / DB | [views.py](file:///d:/project/fadi/3/backend/apps/common/api/v1/views.py#L698-L733) | N+1 database queries in admin dashboard analytics endpoint | Executes 45+ unindexed SQL queries on every dashboard page view, saturating database I/O. | Use single aggregated query with conditional annotations and cache result in Redis for 5-15 minutes. |
| **SEC-MED-04** | **Medium** | Dependency / Build | [package.json](file:///d:/project/fadi/3/creator-hub/package.json#L17-L72) | Undeclared dependency `axios` in `creator-hub` | Fresh clone and install fails to compile `src/lib/api-client.ts`. | Add `axios: "^1.21.0"` to `creator-hub/package.json`. |
| **SEC-MED-05** | **Medium** | CI/CD / DevOps | [backend/](file:///d:/project/fadi/3/backend/) | Missing `requirements.txt` or `pyproject.toml` | Deployments are non-deterministic and reproducible container builds cannot be created. | Generate `requirements.txt` with pinned package versions via `pip freeze`. |
| **SEC-MED-06** | **Medium** | Authentication | [services.py](file:///d:/project/fadi/3/backend/apps/accounts/api/v1/services.py#L230-L232) | Bypassing Django password validators in onboarding services | Allows weak passwords (e.g. `12345678`) despite strict validators configured in `settings.py`. | Use `django.contrib.auth.password_validation.validate_password(password, user)`. |
| **SEC-MED-07** | **Medium** | Auth Hygiene | [auth.ts](file:///d:/project/fadi/3/pixel-perfect-replication/src/lib/auth.ts#L11-L16), [demo-auth.ts](file:///d:/project/fadi/3/creator-hub/src/lib/demo-auth.ts#L25) | Hardcoded mock passwords (`Password123!`) and mock sessions in production frontend bundles | Confusion between demo mocks and live auth; potential false client-side authorization. | Remove static demo accounts and bypass flags from production builds. |
| **SEC-MED-08** | **Medium** | Audit / Logging | [services.py](file:///d:/project/fadi/3/backend/apps/common/api/v1/services.py#L161-L165) | Untrusted `X-Forwarded-For` header parsed for audit logging | Attackers can spoof client IP addresses in compliance and security audit logs. | Validate proxy trust or use trusted reverse proxy middleware (`django-ipware`). |
| **SEC-MED-09** | **Medium** | Performance / DB | [views.py](file:///d:/project/fadi/3/backend/apps/accounts/api/v1/views.py#L67-L72) | Unbounded querysets without pagination in admin and domain views | Large datasets will cause memory spikes and slow response times. | Apply DRF pagination to `RoleTemplateListView`, `StaffInvitationListView`, and `CreatorWebsiteDomainView`. |
| **SEC-MED-10** | **Medium** | Business Logic | [services.py](file:///d:/project/fadi/3/backend/apps/websites/services.py#L80-L90) | Custom domain DNS verification defaults to `simulated=True` | Domains are marked `VERIFIED` and SSL marked `ACTIVE` without validating live DNS records. | Implement live DNS resolver using `dnspython` and disable simulation in production mode. |
| **SEC-LOW-01** | **Low** | Code Quality / QA | [tests.py](file:///d:/project/fadi/3/backend/apps/accounts/tests.py#L1-L3) | Zero unit, integration, or security tests in the backend (0% coverage) | High regression risk during updates, bugfixes, or refactoring. | Write unit and integration test suite covering auth, RBAC decorators, services, and transactions. |
| **SEC-LOW-02** | **Low** | Security Headers | [settings.py](file:///d:/project/fadi/3/backend/core/settings.py#L73-L82) | Missing security headers (HSTS, CSP, X-Content-Type-Options) | Vulnerable to clickjacking, MIME-sniffing, and downgrade attacks. | Enable `SECURE_HSTS_SECONDS`, `SECURE_CONTENT_TYPE_NOSNIFF`, and configure `django-csp`. |
| **SEC-LOW-03** | **Low** | Media Serving | [urls.py](file:///d:/project/fadi/3/backend/core/urls.py#L35-L36) | Media served via Django only when `DEBUG=True` | When `DEBUG=False` in production, all media URLs return 404. | Configure AWS S3, Cloudflare R2, or reverse-proxy media serving via Nginx. |
| **SEC-LOW-04** | **Low** | Token Storage | [api-client.ts](file:///d:/project/fadi/3/creator-hub/src/lib/api-client.ts#L16) | JWT Access & Refresh tokens stored in browser `localStorage` | If an XSS vulnerability occurs, tokens can be stolen by malicious scripts. | Move JWT tokens to `HttpOnly`, `Secure`, `SameSite=Strict` cookies. |
| **SEC-LOW-05** | **Low** | Network Security | [.env](file:///d:/project/fadi/3/backend/.env#L70-L71) | Redis connection configured with `ssl_cert_reqs=CERT_NONE` | TLS certificate is not validated, making Redis connections vulnerable to Man-in-the-Middle (MitM) attacks. | Set `ssl_cert_reqs=CERT_REQUIRED` and supply trusted CA root. |
| **SEC-LOW-06** | **Low** | DevOps | [backend/](file:///d:/project/fadi/3/backend/) | Missing `.gitignore` in `backend` root | High risk of committing `db.sqlite3` with personal user data and `.env` with API keys to Git. | Add comprehensive `.gitignore` ignoring `.env`, `*.sqlite3`, `media/`, and `__pycache__/`. |
| **SEC-LOW-07** | **Low** | Config Alignment | [.env.example](file:///d:/project/fadi/3/backend/.env.example#L10-L13) | Port mismatches between `.env.example` and Vite dev server configs | Developer confusion and broken local redirects. | Align ports in documentation and configuration files. |

---

## 4. Deep-Dive: Critical & High Findings with Remediation Code

### SEC-CRIT-01: Critical Authentication Bypass via Email Fallback
- **Location:** [apps/accounts/api/v1/services.py:479-493](file:///d:/project/fadi/3/backend/apps/accounts/api/v1/services.py#L479-L493)
- **Vulnerability Breakdown:** When verifying email magic links, if the signature fails (`BadSignature`), the code catches the exception and checks `if email:`. If provided, it retrieves the user matching that email and immediately issues an active JWT access and refresh token pair without verifying signature or password.

#### Vulnerable Code
```python
# backend/apps/accounts/api/v1/services.py
try:
    user_id = signer.unsign(token, max_age=172800)
    user = User.objects.get(id=user_id, is_deleted=False)
except SignatureExpired:
    raise ValidationError("Verification token has expired.")
except (BadSignature, ValueError, User.DoesNotExist):
    # CRITICAL FLAW: Falls back to email without cryptographic verification!
    if email:
        try:
            user = User.objects.get(email__iexact=email.strip(), is_deleted=False)
        except User.DoesNotExist:
            raise ValidationError("Invalid verification token or email address.")
    else:
        raise ValidationError("Invalid or corrupted verification token.")
```

#### Remediation Code
```python
# Fixed: Strictly require cryptographic signature validation
try:
    user_id = signer.unsign(token, max_age=172800)
    user = User.objects.get(id=user_id, is_deleted=False)
except SignatureExpired:
    raise ValidationError("Verification token has expired. Please request a new magic link.")
except (BadSignature, ValueError, User.DoesNotExist):
    raise ValidationError("Invalid or corrupted verification token.")
```

---

### SEC-CRIT-02: Hardcoded Production Secrets & Google App Password in Unprotected `.env`
- **Location:** [backend/.env:12, 57, 61, 70-71](file:///d:/project/fadi/3/backend/.env#L12-L71)
- **Vulnerability Breakdown:** Live production third-party secrets are committed on disk without a `.gitignore`.

#### Vulnerable Credentials Found (REDACTED)
```ini
# backend/.env
SECRET_KEY=djan*************************************************
EMAIL_HOST_USER=muhs*******************
EMAIL_HOST_PASSWORD=hkjh************
DEFAULT_FROM_EMAIL=Influencers <muhs*******************>
CELERY_BROKER_URL=redi*****************************************************************************************
CELERY_RESULT_BACKEND=redi*****************************************************************************************
ALLOWED_HOSTS=localhost,127.0.0.1,*
```

#### Remediation Steps
1. Immediately revoke the Google App Password (`hkjh************`) in the associated Google account.
2. Rotate the Upstash Redis credentials (`fond-puma-206966.upstash.io`).
3. Generate a new cryptographically secure `SECRET_KEY`:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
4. Create `backend/.gitignore`:
   ```gitignore
   .env
   .env.*
   db.sqlite3
   media/
   __pycache__/
   *.pyc
   venv/
   ```

---

### SEC-CRIT-03: Insecure CORS Configuration with Wildcard Credentials
- **Location:** [backend/core/settings.py:222-223](file:///d:/project/fadi/3/backend/core/settings.py#L222-L223)
- **Vulnerability Breakdown:** `CORS_ALLOW_ALL_ORIGINS = True` is set together with `CORS_ALLOW_CREDENTIALS = True`.

#### Vulnerable Code
```python
# backend/core/settings.py
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True
```

#### Remediation Code
```python
# backend/core/settings.py
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

_cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in _cors_env.split(',') if origin.strip()
] if _cors_env else [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://localhost:8082",
    "http://localhost:8083",
]
```

---

### SEC-CRIT-04: Unrestricted File Upload Leading to Stored XSS / RCE
- **Location:** [backend/apps/creators/api/v1/views.py:446-454](file:///d:/project/fadi/3/backend/apps/creators/api/v1/views.py#L446-L454)
- **Vulnerability Breakdown:** File uploads trust client-provided file names and MIME types without extension restrictions or payload validation.

#### Vulnerable Code
```python
# backend/apps/creators/api/v1/views.py
ext = os.path.splitext(uploaded_file.name)[1].lower()
unique_name = f"creators/{profile.id}/{uuid.uuid4().hex}{ext}"
saved_path = default_storage.save(unique_name, uploaded_file)
relative_url = default_storage.url(saved_path)
full_url = request.build_absolute_uri(relative_url)
```

#### Remediation Code
```python
# backend/apps/creators/api/v1/views.py
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf', '.mp4'}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

if uploaded_file.size > MAX_UPLOAD_SIZE_BYTES:
    return Response({'detail': "File exceeds maximum 10MB limit."}, status=status.HTTP_400_BAD_REQUEST)

ext = os.path.splitext(uploaded_file.name)[1].lower()
if ext not in ALLOWED_EXTENSIONS:
    return Response({'detail': f"File type '{ext}' is not permitted."}, status=status.HTTP_400_BAD_REQUEST)

# Validate magic bytes for image uploads
if ext in {'.jpg', '.jpeg', '.png', '.webp'}:
    from PIL import Image
    try:
        img = Image.open(uploaded_file)
        img.verify()
        uploaded_file.seek(0)
    except Exception:
        return Response({'detail': "Invalid image content."}, status=status.HTTP_400_BAD_REQUEST)

unique_name = f"creators/{profile.id}/{uuid.uuid4().hex}{ext}"
saved_path = default_storage.save(unique_name, uploaded_file)
```

---

### SEC-HIGH-01: Absence of Rate Limiting on Authentication and Public Endpoints
- **Location:** [backend/core/settings.py:235-250](file:///d:/project/fadi/3/backend/core/settings.py#L235-L250)
- **Vulnerability Breakdown:** No throttle classes or limits are defined in `REST_FRAMEWORK` settings or on any individual API views.

#### Remediation Code
```python
# backend/core/settings.py
REST_FRAMEWORK = {
    # ... existing settings ...
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '120/minute',
        'auth': '5/minute',
    },
}
```

```python
# backend/apps/accounts/api/v1/views.py
from rest_framework.throttling import ScopedRateThrottle

class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'
```

---

### SEC-HIGH-02: Attribute Mismatch Breaking WebSocket Chat for Creators
- **Location:** [backend/apps/campaigns/consumers.py:38-41, 88-91](file:///d:/project/fadi/3/backend/apps/campaigns/consumers.py#L38-L41)
- **Vulnerability Breakdown:** The consumer queries `user.influencer_profile`, but the `User` model defines `creator_profile` ([apps/creators/models.py:34](file:///d:/project/fadi/3/backend/apps/creators/models.py#L34)). Creators are rejected with HTTP 4403 on connection.

#### Vulnerable Code
```python
# backend/apps/campaigns/consumers.py
if hasattr(user, 'influencer_profile') and inquiry.creator_id == user.influencer_profile.id:
    is_creator = True
    sender_name = user.influencer_profile.display_name or sender_name
    sender_avatar = user.influencer_profile.profile_photo_url or ""
```

#### Remediation Code
```python
# backend/apps/campaigns/consumers.py
if hasattr(user, 'creator_profile') and inquiry.creator_id == user.creator_profile.id:
    is_creator = True
    sender_name = user.creator_profile.display_name or sender_name
    sender_avatar = user.creator_profile.photo_url or ""
```

---

### SEC-HIGH-03: Plaintext JWT in WebSocket Query String over Hardcoded `ws://`
- **Location:** [apps/common/ws_auth.py:50-56](file:///d:/project/fadi/3/backend/apps/common/ws_auth.py#L50-L56), [creator-hub/src/lib/use-inquiry-socket.ts:56](file:///d:/project/fadi/3/creator-hub/src/lib/use-inquiry-socket.ts#L56)
- **Vulnerability Breakdown:** WebSocket clients connect via `ws://127.0.0.1:8000/ws/inquiries/<id>/?token=<jwt>`, transmitting sensitive tokens in query strings and hardcoding local plaintext protocols.

#### Vulnerable Code
```typescript
// creator-hub/src/lib/use-inquiry-socket.ts
const wsUrl = `ws://127.0.0.1:8000/ws/inquiries/${inquiryId}/?token=${token}`;
const ws = new WebSocket(wsUrl);
```

#### Remediation Code
```typescript
// creator-hub/src/lib/use-inquiry-socket.ts
const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const host = import.meta.env.VITE_WS_HOST || window.location.host;
const wsUrl = `${protocol}//${host}/ws/inquiries/${inquiryId}/`;
// Pass token as Sec-WebSocket-Protocol or authenticate via HttpOnly session cookie
const ws = new WebSocket(wsUrl, ["bearer", token]);
```

---

### SEC-HIGH-04: Concurrency Race Condition in Financial Refund Processing
- **Location:** [backend/apps/billing/api/v1/services.py:31-60](file:///d:/project/fadi/3/backend/apps/billing/api/v1/services.py#L31-L60)
- **Vulnerability Breakdown:** `Payment` balance calculation and update happen without row-level database locking (`select_for_update()`). Two concurrent refund requests can both pass validation and over-refund the payment.

#### Vulnerable Code
```python
# backend/apps/billing/api/v1/services.py
payment = Payment.objects.get(id=payment_id, is_deleted=False)
remaining_balance = payment.amount_cents - payment.refunded_amount_cents
if refund_amount_cents > remaining_balance:
    raise ValidationError("Refund amount exceeds balance.")

with transaction.atomic():
    payment.refunded_amount_cents += refund_amount_cents
    payment.save()
```

#### Remediation Code
```python
# backend/apps/billing/api/v1/services.py
with transaction.atomic():
    payment = Payment.objects.select_for_update().get(id=payment_id, is_deleted=False)
    remaining_balance = payment.amount_cents - payment.refunded_amount_cents
    if refund_amount_cents > remaining_balance:
        raise ValidationError("Refund amount exceeds refundable balance.")
    
    payment.refunded_amount_cents += refund_amount_cents
    if payment.refunded_amount_cents >= payment.amount_cents:
        payment.status = PaymentStatus.REFUNDED
    payment.save(update_fields=['refunded_amount_cents', 'refund_reason', 'status', 'updated_at'])
```

---

### SEC-HIGH-05: Unauthenticated User Association & Profile Poisoning in Public Inquiries
- **Location:** [backend/apps/campaigns/api/v1/services.py:214-236](file:///d:/project/fadi/3/backend/apps/campaigns/api/v1/services.py#L214-L236)
- **Vulnerability Breakdown:** Any unauthenticated visitor can call `/api/v1/public/inquiries/` with any existing user's email. The backend fetches that existing `User` and binds a `BusinessProfile` to them without checking credentials or email ownership.

#### Vulnerable Code
```python
# backend/apps/campaigns/api/v1/services.py
user = User.objects.filter(email=email).first()
if not user:
    user = User.objects.create(...)
business_profile = BusinessProfile.objects.filter(user=user).first()
if not business_profile:
    business_profile = BusinessProfile.objects.create(user=user, ...)
```

#### Remediation Code
```python
# backend/apps/campaigns/api/v1/services.py
# If email belongs to an existing user, require authentication
user = User.objects.filter(email=email).first()
if user:
    request_user = validated_data.get('request_user')
    if not request_user or request_user != user:
        raise ValidationError("An account with this email already exists. Please sign in to submit inquiries.")
```

---

### SEC-HIGH-06: Production Full Stack Trace Leakage in Frontend Root Error Boundaries
- **Location:** [kerala-creator-collab/src/routes/__root.tsx:79-83](file:///d:/project/fadi/3/kerala-creator-collab/src/routes/__root.tsx#L79-L83), [creator-hub/src/routes/__root.tsx:80-84](file:///d:/project/fadi/3/creator-hub/src/routes/__root.tsx#L80-L84)
- **Vulnerability Breakdown:** The error component renders `{error.stack}` directly to users in production builds.

#### Vulnerable Code
```tsx
// src/routes/__root.tsx
{error.stack && (
  <pre className="mt-2 max-h-40 overflow-auto font-mono text-[10px] text-muted-foreground whitespace-pre-wrap">
    {error.stack}
  </pre>
)}
```

#### Remediation Code
```tsx
// src/routes/__root.tsx
{!import.meta.env.PROD && error?.stack && (
  <pre className="mt-2 max-h-40 overflow-auto font-mono text-[10px] text-muted-foreground whitespace-pre-wrap">
    {error.stack}
  </pre>
)}
```

---

## 5. Scalability & Performance Analysis

### Database Bottlenecks
1. **SQLite in Production (`db.sqlite3`):**  
   SQLite locks the entire database file during writes. At concurrent registration, inquiry posting, or bid submission spikes, requests will throw `sqlite3.OperationalError: database is locked`. SQLite also lacks connection pooling and cannot be horizontally distributed.
2. **N+1 Query Explosion in Admin Dashboard:**  
   In [apps/common/api/v1/views.py:698-733](file:///d:/project/fadi/3/backend/apps/common/api/v1/views.py#L698-L733), `AdminDashboardStatsView` loops over 6 months and performs 5 individual query counts per iteration plus Category counts, executing 45+ unindexed SQL queries on every hit without caching.

### Concurrency Stress Projections

| Concurrency Tier | Expected Behavior | Failure Points |
| :---: | :--- | :--- |
| **100 Concurrent Users** | High latency on write endpoints, occasional 500 errors. | **SQLite write locking** causes request timeouts during simultaneous signups or messages. **Synchronous Celery (`CELERY_ALWAYS_EAGER=True`)** blocks web workers for 1-2 seconds per email dispatch via Google SMTP. |
| **1,000 Concurrent Users** | Severe degradation, cascading 504 Gateway Timeouts. | **Daphne/ASGI thread exhaustion** due to synchronous SMTP operations. **In-Memory Channel Layer** crashes or drops WebSocket connections across worker processes. **Disk I/O saturation** from unthrottled media uploads. |
| **10,000 Concurrent Users** | Complete system outage / permanent denial of service. | Complete database failure (SQLite corrupted or locked indefinitely). Memory exhaustion from uncached dashboard queries and missing pagination on role/invitation endpoints. Host header poisoning and unthrottled endpoint flooding. |

---

## 6. Code Quality & Architecture Review

### Strengths & Done Well
- **Strict Domain Separation:** The backend adopts a clean modular structure (`apps/accounts`, `apps/creators`, `apps/businesses`, `apps/campaigns`, `apps/taxonomies`, `apps/billing`, `apps/websites`, `apps/common`).
- **Comprehensive Inline Documentation:** Models and services adhere strictly to the engineering standard with descriptive docstrings and parameter annotations.
- **ORM Discipline:** All queries use the Django ORM; zero raw SQL injection vectors (`raw()`, `extra()`) were identified.
- **UUID Primary Keys & Soft-Deletes:** `BaseModel` enforces UUIDv4 primary keys and non-destructive logical deletion across models.
- **Modern Frontend Architecture:** Frontends use TanStack Router with type-safe route trees, Tailwind CSS v4, Lucide icons, and Radix UI primitives.

### Critical Architecture Flaws
- **0% Backend Test Coverage:** All 8 `tests.py` files in `backend/apps/*/` are empty 3-line stubs.
- **Missing Build Dependency Manifests:** No `requirements.txt` exists in `backend/`, and `axios` is missing from `creator-hub/package.json`.
- **Statelessness Broken:** WebSocket channels layer uses `InMemoryChannelLayer`, breaking horizontal scaling across multiple instances.
- **Mock / Prototype Artifacts in Production Code:** Production bundles retain prototype bypasses (`demoAuth`, `DEMO_SESSION`, `quickLogin` with hardcoded `Password123!`).

---

## 7. Quick Wins (< 30 Minutes Fixes)

1. **Fix Authentication Bypass:** Delete lines 484-492 in `backend/apps/accounts/api/v1/services.py` so invalid tokens immediately raise `ValidationError`.
2. **Fix Creator WebSocket Consumer:** In `backend/apps/campaigns/consumers.py` (lines 38 and 88), change `user.influencer_profile` to `user.creator_profile` and `profile_photo_url` to `photo_url`.
3. **Lock Down CORS:** In `backend/core/settings.py` (line 223), set `CORS_ALLOW_ALL_ORIGINS = False`.
4. **Hide Production Error Stacks:** In `src/routes/__root.tsx` across frontends, wrap `{error.stack}` with `!import.meta.env.PROD &&`.
5. **Add Missing Dependency:** Run `bun add axios` or `npm install axios` in `creator-hub`.
6. **Create Backend `.gitignore`:** Add `.env`, `db.sqlite3`, and `media/` to a new `backend/.gitignore`.
7. **Freeze Python Dependencies:** Run `pip freeze > requirements.txt` in `backend/`.

---

## 8. Must-Fix Before Launch Checklist

- [ ] **SEC-01:** Remove fallback user lookup in `verify_creator_email` to eliminate authentication bypass.
- [ ] **SEC-02:** Revoke and rotate Google App Password and Upstash Redis credentials.
- [ ] **SEC-03:** Remove wildcard `*` from `ALLOWED_HOSTS` and disable `CORS_ALLOW_ALL_ORIGINS`.
- [ ] **SEC-04:** Enforce file extension whitelist, MIME check, and 10MB limit in `CreatorMediaUploadView`.
- [ ] **SEC-05:** Configure Django REST Framework rate limiting (`AnonRateThrottle`, `UserRateThrottle`).
- [ ] **SEC-06:** Wrap `process_payment_refund` in `select_for_update()` to prevent race condition over-refunds.
- [ ] **DATA-01:** Migrate from SQLite to PostgreSQL with connection pooling.
- [ ] **SCAL-01:** Switch `CHANNEL_LAYERS` from `InMemoryChannelLayer` to Redis (`channels_redis`).
- [ ] **ASYNC-01:** Set `CELERY_ALWAYS_EAGER=False` in production and run a dedicated Celery worker daemon.
- [ ] **AUTH-01:** Align WebSocket consumer to use `creator_profile` and remove `demo-auth.ts` mock bypasses.
- [ ] **TEST-01:** Implement automated test suite covering authentication, RBAC decorators, and refund transactions.
- [ ] **INFRA-01:** Configure Cloudflare R2 / AWS S3 or Nginx for serving media files when `DEBUG=False`.

---

## 9. Verification Limitations (Items Requiring Runtime / Infra Access)

The following items could not be verified statically and must be checked manually in staging/infrastructure:
1. **Google SMTP App Password Validity:** Requires active network probe to confirm whether `hkjh************` is currently active.
2. **Upstash Redis Quota & Latency:** Needs live connection test to ensure TLS handshake succeeds without `CERT_NONE`.
3. **Cloudflare Worker / Wrangler Deployment Routing:** Requires deployment testing to ensure Nitro server routes correctly proxy `/api/v1/` and `/ws/` to backend host.
4. **Nginx / Ingress Header Stripping:** Requires verifying that reverse proxies correctly strip or sanitize client-provided `X-Forwarded-For` and `X-Target-Portal` headers before reaching Django.
5. **Database Migration State on Production DB:** Migrations are applied in local `db.sqlite3`, but production database migration history must be verified independently.

