# DragonForge Platform API

Phase 1 foundation for the DragonForge market-analysis and decision-support platform. This API is separate from the legacy research-results server. It contains no broker connection or trade-execution endpoint.

## Local setup

Requirements: Docker Compose, Python 3.12+, Node.js 18+.

1. From this directory, copy `.env.example` to `.env`. Set `POSTGRES_PASSWORD` to a random URL-safe value, generate `DRAGONFORGE_SESSION_SECRET` and the one-time `DRAGONFORGE_BOOTSTRAP_TOKEN` with `openssl rand -hex 32`, and generate `DRAGONFORGE_TOTP_ENCRYPTION_KEY` with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Do not commit `.env`.
2. Start PostgreSQL with `docker compose up -d db`.
3. Create an environment and install the API: `python -m venv .venv`, `source .venv/bin/activate`, then `pip install -r requirements-dev.txt`.
4. Apply database migrations from this directory: `alembic upgrade head`.
5. Run the API: `uvicorn app.main:app --reload --port 8000`.
6. In another terminal, from the repository root, run `npm --prefix frontend/client ci` and `npm --prefix frontend/client run dev -- --host 0.0.0.0`. The Vite development proxy sends `/api` requests to port 8000.

For a containerized API, copy the environment file first, then use `docker compose up --build -d`. Apply migrations as a one-off release step with `docker compose run --rm api alembic upgrade head`. Do not run migrations independently in every production API replica.

Set `DRAGONFORGE_DOMAIN` to change the working domain without rebuilding. Set `DRAGONFORGE_ALLOWED_ORIGINS` to a JSON array of exact browser origins. Production must use HTTPS and `DRAGONFORGE_SESSION_COOKIE_SECURE=true`; terminate TLS at a trusted reverse proxy. Keep all secret values in the deployment secret manager.

## Implemented in this phase

- PostgreSQL relational schema and Alembic migrations for users, roles, permissions, admin accounts, sessions, devices, login attempts, platform configuration, and audit events.
- Operator-authorized first-owner bootstrap; the token is checked in constant time and never returned by the API.
- Single-owner bootstrap with a database-level uniqueness guard, Argon2id password hashes, per-session random tokens stored only as hashes, secure HTTP-only/SameSite cookies, session listing/revocation, failed-login throttling, and security response headers.
- TOTP setup with encrypted-at-rest authenticator secrets, short setup expiry, one-use hashed recovery codes, and re-authentication for sensitive owner actions.
- Owner-only configuration APIs and setup completion checks; publishing configuration does not enable member registration.
- Owner-created individual admin accounts with explicit allowlisted permissions and a database-constrained maximum of five accounts.
- Append-only-by-API audit event recording and honest safe/degraded health reporting.

## Not implemented; do not treat as production-ready

- Member signup, email verification, membership applications/review, and account activation. Public registration intentionally remains disabled, even after platform configuration is published.
- Admin application-review actions, an owner/admin approval workflow for sensitive changes, or admin invitations/password reset delivery. The current admin screen shows only the administrator's assigned permission names.
- Production-grade distributed rate limiting, email delivery, external secret-manager integration, database backup automation/restore drills, monitoring/alert delivery, or disaster recovery.
- Market-data providers, financial-market analysis, charting, risk analysis, subscriptions/payments, broker connections, paper trading, backtesting, AI, and user-facing audit retention/immutability controls.

Never expose this API publicly until those required launch controls and production infrastructure are implemented and independently reviewed. `PUBLISH PLATFORM` publishes the configured owner settings only; it does not turn on public registration. The platform must not be described as production-ready on the basis of this Phase 1 foundation alone.