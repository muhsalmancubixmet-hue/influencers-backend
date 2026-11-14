# SaaS Django REST Backend Engineering & Architecture Rules

## 1. Senior Engineering Mindset & Code Restraint
- THINK LIKE A SENIOR ARCHITECT: Prioritize maintainability, readability, zero technical debt, and zero duplicate code.
- REUSE & MODIFY FIRST: Never generate duplicate models, helper functions, or views if an existing one can be cleanly extended or modified.
- STRICT BLAST RADIUS: Never touch, refactor, or alter unrelated files or functions outside the immediate scope of the current task.
- COMPREHENSIVE DOCUMENTATION: Every single Django Model, Database Field, Serializer, Service function, and API View MUST have clear, meaningful `# comments` and Python docstrings (`"""..."""`) explaining purpose, parameters, and return types.

## 2. Architecture & Modular Layout (Cubelogs Standard)
- All domain applications reside under `backend/apps/<domain_name>/`.
- Adopt the Service Layer Pattern:
  - `models.py`: Database schema definitions, indexes, constraints, and string representations.
  - `api/v1/serializers.py`: Input validation and payload contract serialization.
  - `services.py` & `api/v1/services.py`: All heavy business logic, calculations, database transactions, and third-party integrations.
  - `api/v1/views.py`: Slim views handling HTTP requests, permission checks, calling services, and returning structured JSON responses.
  - `api/v1/urls.py`: Nested versioned routing (`/api/v1/<portal>/<resource>/`).

## 3. Security, Auth & Python Method Decorators
- JWT AUTHENTICATION: Use SimpleJWT with fresh database verification on every single protected request.
- RBAC ENFORCEMENT VIA PYTHON DECORATORS:
  - Protect view methods using explicit custom Python decorators: `@require_permission('module.action')` or `@require_module_access('resource', min_level='MANAGE')`.
  - The decorator must query the user's active role template dynamically from the database.
  - Immediate `403 Forbidden` response (`{"detail": "You lack the required permission"}`) if permission is revoked or missing.
  - Auto-bypass only for authenticated, active Super Admins (`is_superuser=True`, `is_active=True`, not soft-deleted).
- ROLE & TENANT BOUNDARIES:
  - Admin endpoints (`/api/v1/admin/*`): Strictly restricted to `SUPER_ADMIN` and `STAFF`.
  - Creator endpoints (`/api/v1/creator/*`): Strictly constrained to `request.user.creator_profile`. Never expose or cross-query other creators' data.

## 4. API Pagination & Filtering Standards
- Standardize all collection responses using DRF `PageNumberPagination`, with `PAGE_SIZE` and `max_page_size` set:
  ```json
  {
    "count": 120,
    "next": "http://api.../?page=3",
    "previous": "http://api.../?page=1",
    "results": []
  }
  ```

## 5. Security Hardening Rules (Mandatory)
- SECRETS: Never hardcode secrets, keys, passwords or tokens. Read everything from environment variables. No default fallback for SECRET_KEY; the app must fail to start if it is missing. `.env.example` contains placeholders only. Never print or log secrets.
- DEFAULT DENY: DRF DEFAULT_PERMISSION_CLASSES must be IsAuthenticated. Any AllowAny endpoint must be justified in a comment and must have throttling.
- OBJECT-LEVEL OWNERSHIP (anti-IDOR): Every queryset returning user-owned data must be filtered by owner/tenant (e.g. profile=request.user.creator_profile). Never fetch by id alone. Always filter is_deleted=False.
- PROFILE NAMING: The creator profile relation is `creator_profile`. Never use `influencer_profile`.
- NEVER TRUST THE CLIENT: Do not use client-supplied headers (X-Forwarded-For, X-Target-Portal), ids, roles, prices or amounts for authorization or business decisions. Derive them server-side.
- NO AUTH SHORTCUTS: Tokens, magic links and OTPs must be validated cryptographically and fail closed. Never fall back to identifying a user by email, phone or id alone.
- INPUT VALIDATION: Validate all input in serializers. Every password set or change must go through django.contrib.auth.password_validation.validate_password. Enforce request size limits.
- FILE UPLOADS: Extension whitelist, max size, content verification (Pillow / magic bytes), random server-generated filenames. Never allow .html, .svg, .js, .exe. Serve media from separate storage (S3/R2) with X-Content-Type-Options: nosniff.
- RATE LIMITING: Throttle every public and auth endpoint (login, signup, password reset, OTP, public inquiry) with stricter scopes than the default.
- MONEY & CONCURRENCY: Any balance, refund, payout or counter update runs inside transaction.atomic() with select_for_update() on the row.
- CORS & HOSTS: Never CORS_ALLOW_ALL_ORIGINS=True or ALLOWED_HOSTS=['*'] outside local dev. Origins and hosts come from env vars.
- ERRORS & LOGGING: Return generic error messages to clients. Never expose stack traces, SQL or internals. Never log passwords, tokens or PII.
- DATABASE: ORM only, no raw()/extra() with string formatting. Use select_related/prefetch_related to avoid N+1. Index fields used in filter/order. No unbounded querysets: pagination is mandatory, with PAGE_SIZE and max_page_size set.
- SLOW WORK: Email, SMS, image processing and third-party API calls go through Celery tasks, never inline in a request. CELERY_ALWAYS_EAGER must be False outside tests.
- DEPENDENCIES: Do not add a new package without stating why. Verify it exists and is well known. Pin versions in requirements.txt.
- NO DEMO CODE: No mock sessions, demo accounts or hardcoded test passwords in production code paths.
- FOUND ISSUES: If you notice a security problem outside the current task, do NOT fix it silently (blast radius rule). Report it at the end of your response.

## 6. Mandatory Documentation & Commenting Standard
- STRICT MODEL COMMENTS: Every single Django Model class MUST have a high-level docstring explaining its domain purpose. Every database field (`models.Field`) MUST have an inline `# comment` explaining its business context, constraints, and relationships.
- STRICT FUNCTION COMMENTS: Every function, method, service action, and API view MUST have Python docstrings (`"""..."""`) declaring:
  * Purpose of the routine
  * Parameter types and descriptions (`:param <name>: ...`)
  * Return type and structure (`:return: ...`)
  * Possible raised exceptions (`:raises <Exception>: ...`)
- STRICT SERVICE COMMENTS: Complex database transactions, multi-table mutations, or external API queries must have step-by-step numbered inline `# comments` documenting each logical step.

## 7. Testing & Delivery Standard
- Every service function and permission decorator gets tests, including failure cases: invalid token, wrong owner, missing permission, over-limit refund, invalid upload.
- Every security fix needs a regression test that fails before the fix and passes after it.
- Run the test suite before declaring a task done. At the end, list changed files and anything uncertain.