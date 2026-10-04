from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hmac

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import AdminAccount, AuditLog, Device, LoginAttempt, Permission, PlatformConfiguration, Role, User, UserSession
from .security import (
    create_totp_secret, decrypt_totp_secret, encrypt_totp_secret, generate_recovery_codes,
    DUMMY_PASSWORD_HASH, hash_password, hash_token, new_session_token, recovery_code_hash, session_expiry,
    verify_password, verify_totp,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.session_secret or len(settings.session_secret) < 32:
        raise RuntimeError("Set DRAGONFORGE_SESSION_SECRET to a random value of at least 32 characters")
    if not settings.totp_encryption_key:
        raise RuntimeError("DRAGONFORGE_TOTP_ENCRYPTION_KEY must be configured")
    yield


app = FastAPI(title="DragonForge Platform API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1_000_000:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.session_cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def audit(db: Session, event: str, request: Request, actor: User | None = None, details: dict | None = None):
    db.add(AuditLog(actor_user_id=actor.id if actor else None, event_type=event,
                    ip_address=client_ip(request), details=details or {}))


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("dragonforge_session")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = db.scalar(select(UserSession).where(
        UserSession.token_hash == hash_token(token), UserSession.revoked_at.is_(None),
        UserSession.expires_at > datetime.now(timezone.utc),
    ))
    user = db.get(User, session.user_id) if session else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Session expired")
    return user


def owner_user(user: User = Depends(current_user)) -> User:
    if user.account_type != "owner":
        raise HTTPException(status_code=403, detail="Owner permission required")
    return user


def require_reauthentication(request: Request, user: User, password: str | None):
    if not password or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=403, detail="Re-authentication required")


class BootstrapInput(BaseModel):
    bootstrap_token: str = Field(min_length=32, max_length=256)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)
    totp_code: str | None = Field(default=None, min_length=6, max_length=32)


class SetupInput(BaseModel):
    section: str = Field(min_length=1, max_length=60)
    value: dict


class TotpVerifyInput(BaseModel):
    code: str = Field(min_length=6, max_length=8)
    password: str = Field(min_length=1, max_length=256)


class SensitiveActionInput(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class AdminCreateInput(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    permissions: list[str] = Field(max_length=5)


def create_device(db: Session, user: User, request: Request) -> Device:
    agent = request.headers.get("user-agent", "")[:512]
    device = Device(user_id=user.id, label=agent[:120] or "Unknown device", user_agent=agent or None,
                    ip_address=client_ip(request))
    db.add(device)
    db.flush()
    return device


def setup_value_is_safe(value) -> bool:
    forbidden = ("secret", "password", "token", "private_key", "api_key", "credential")
    if isinstance(value, dict):
        return all(not any(word in str(key).lower() for word in forbidden) and setup_value_is_safe(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return all(setup_value_is_safe(item) for item in value)
    return True


REQUIRED_SETUP = {
    "platform": "Platform identity",
    "policies": "Terms, privacy, and risk disclosure",
    "rules": "User and admin rules",
    "membership": "Membership requirements",
    "subscriptions": "Plans, pricing, and currency",
    "payments": "Payment provider configuration",
    "trial": "Free-trial configuration",
    "notifications": "Notification settings",
    "markets": "Supported markets",
    "strategies": "Strategy configuration",
    "security": "Security settings and 2FA",
    "backups": "Backup settings",
    "audit": "Audit logging",
    "branding": "Platform branding",
}

SETUP_REQUIRED_FIELDS = {
    "platform": ("name", "description"),
    "policies": ("terms", "privacy", "risk_disclosure"),
    "rules": ("user_rules", "admin_rules"),
    "membership": ("requirements",),
    "subscriptions": ("plans", "currency"),
    "payments": ("provider", "configuration_status"),
    "trial": ("duration_days",),
    "notifications": ("channels",),
    "markets": ("supported",),
    "strategies": ("enabled",),
    "security": ("session_hours", "password_min_length"),
    "backups": ("frequency", "retention_days", "restore_tested"),
    "audit": ("enabled",),
    "branding": ("brand_color",),
}


def setup_section_complete(section: str, value) -> bool:
    fields = SETUP_REQUIRED_FIELDS[section]
    if not isinstance(value, dict) or any(
        field not in value or value[field] in (None, "", [], {}) for field in fields
    ):
        return False
    if section == "payments" and value["configuration_status"] != "configured":
        return False
    if section == "audit" and value["enabled"] is not True:
        return False
    if section == "backups" and value["restore_tested"] is not True:
        return False
    return True

    if not settings.session_secret or len(settings.session_secret) < 32:
        raise RuntimeError("Set DRAGONFORGE_SESSION_SECRET to a random value of at least 32 characters")
    if not settings.totp_encryption_key:
        raise RuntimeError("Set DRAGONFORGE_TOTP_ENCRYPTION_KEY to a Fernet key")


@app.get("/api/v1/status")
def status(db: Session = Depends(get_db)):
    owner_exists = db.scalar(select(User.id).where(User.account_type == "owner")) is not None
    config = db.scalar(select(PlatformConfiguration).limit(1))
    return {"service": "DragonForge Platform API", "state": "ready", "owner_registered": owner_exists,
            "published": bool(config and config.published_at), "registration_enabled": False,
            "registration_reason": "Member verification and application review are not implemented yet.",
            "domain": settings.domain, "market_data": "NOT CONFIGURED"}


@app.post("/api/v1/auth/bootstrap", status_code=201)
def bootstrap(payload: BootstrapInput, request: Request, response: Response, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.account_type == "owner")) is not None:
        raise HTTPException(status_code=409, detail="Owner bootstrap has already been completed")
    expected_token = settings.bootstrap_token
    if not expected_token or len(expected_token) < 32:
        raise HTTPException(status_code=503, detail="Owner bootstrap has not been provisioned by the operator")
    if not expected_token or not hmac.compare_digest(payload.bootstrap_token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid owner bootstrap authorization")
    try:
        hashed = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if db.scalar(select(User.id).where(func.lower(User.email) == payload.email.lower())):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    owner_role = Role(name="owner")
    owner = User(email=payload.email.lower(), display_name=payload.display_name, password_hash=hashed,
                 account_type="owner", email_verified_at=datetime.now(timezone.utc))
    db.add_all([owner_role, owner])
    db.flush()
    owner.roles.append(owner_role)
    for permission_name in ("platform:configure", "users:manage", "admins:manage", "audit:read", "security:manage"):
        permission = db.scalar(select(Permission).where(Permission.name == permission_name))
        if not permission:
            permission = Permission(name=permission_name, description=permission_name.replace(":", " ").title())
            db.add(permission)
        owner_role.permissions.append(permission)
    db.add(PlatformConfiguration(settings={}))
    token = new_session_token()
    device = create_device(db, owner, request)
    db.add(UserSession(user_id=owner.id, device_id=device.id, token_hash=hash_token(token),
                       user_agent=request.headers.get("user-agent"), ip_address=client_ip(request),
                       expires_at=session_expiry()))
    audit(db, "owner.bootstrap_completed", request, owner)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Owner bootstrap has already been completed") from exc
    response.set_cookie("dragonforge_session", token, httponly=True, secure=settings.session_cookie_secure,
                        samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/")
    return {"id": owner.id, "email": owner.email, "display_name": owner.display_name,
            "account_type": owner.account_type, "totp_enabled": False}


@app.post("/api/v1/auth/login")
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    subject = f"{payload.email.lower()}:{client_ip(request) or 'unknown'}"
    recent = db.scalar(select(func.count(LoginAttempt.id)).where(
        LoginAttempt.subject == subject,
        LoginAttempt.created_at > datetime.now(timezone.utc) - timedelta(minutes=15),
        LoginAttempt.succeeded.is_(False),
    )) or 0
    if recent >= 8:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    valid_password = verify_password(payload.password, user.password_hash) if user else verify_password(
        payload.password, DUMMY_PASSWORD_HASH
    )
    valid = bool(user and user.is_active and valid_password)
    if valid and user.totp_enabled_at:
        code = payload.totp_code or ""
        valid = verify_totp(decrypt_totp_secret(user.totp_secret_encrypted), code)
        if not valid:
            candidate = recovery_code_hash(code)
            if candidate in user.recovery_code_hashes:
                user.recovery_code_hashes = [item for item in user.recovery_code_hashes if item != candidate]
                valid = True
                audit(db, "auth.recovery_code_used", request, user)
    db.add(LoginAttempt(subject=subject, succeeded=valid))
    if not valid:
        audit(db, "auth.login_failed", request, user)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials or verification code")
    token = new_session_token()
    device = create_device(db, user, request)
    db.add(UserSession(user_id=user.id, device_id=device.id, token_hash=hash_token(token),
                       user_agent=request.headers.get("user-agent"), ip_address=client_ip(request),
                       expires_at=session_expiry()))
    audit(db, "auth.login_succeeded", request, user)
    db.commit()
    response.set_cookie("dragonforge_session", token, httponly=True, secure=settings.session_cookie_secure,
                        samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/")
    return {"id": user.id, "email": user.email, "display_name": user.display_name,
            "account_type": user.account_type, "totp_enabled": bool(user.totp_enabled_at)}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    token = request.cookies.get("dragonforge_session")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session:
        session.revoked_at = datetime.now(timezone.utc)
    audit(db, "auth.logout", request, user)
    db.commit()
    response.delete_cookie("dragonforge_session", httponly=True, secure=settings.session_cookie_secure,
                           samesite="strict", path="/")


@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "display_name": user.display_name,
            "account_type": user.account_type, "totp_enabled": bool(user.totp_enabled_at)}


@app.get("/api/v1/auth/sessions")
def list_sessions(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    current_hash = hash_token(request.cookies.get("dragonforge_session", ""))
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id,
                         UserSession.revoked_at.is_(None), UserSession.expires_at > datetime.now(timezone.utc))
                      .order_by(UserSession.created_at.desc())).all()
    return [{"id": row.id, "current": row.token_hash == current_hash, "created_at": row.created_at.isoformat(),
             "expires_at": row.expires_at.isoformat(), "user_agent": row.user_agent,
             "ip_address": row.ip_address} for row in rows]


@app.delete("/api/v1/auth/sessions/{session_id}", status_code=204)
def revoke_session(session_id: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    row.revoked_at = datetime.now(timezone.utc)
    audit(db, "auth.session_revoked", request, user, {"session_id": session_id})
    db.commit()


@app.post("/api/v1/auth/2fa/setup")
def setup_totp(request: Request, x_reauth_password: str | None = Header(default=None, alias="X-Reauth-Password"),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_reauthentication(request, user, x_reauth_password)
    secret = create_totp_secret()
    user.totp_secret_encrypted = encrypt_totp_secret(secret)
    user.totp_enabled_at = None
    user.totp_setup_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    audit(db, "auth.2fa_setup_started", request, user)
    db.commit()
    import pyotp
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="DragonForge")
    return {"secret": secret, "otpauth_uri": uri, "expires_in_seconds": 600}


@app.post("/api/v1/auth/2fa/enable")
def enable_totp(payload: TotpVerifyInput, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_reauthentication(request, user, payload.password)
    setup_expires_at = user.totp_setup_expires_at
    if setup_expires_at and setup_expires_at.tzinfo is None:
        setup_expires_at = setup_expires_at.replace(tzinfo=timezone.utc)
    if not user.totp_secret_encrypted or not setup_expires_at or setup_expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="Start 2FA setup first")
    secret = decrypt_totp_secret(user.totp_secret_encrypted)
    if not verify_totp(secret, payload.code):
        audit(db, "auth.2fa_enable_failed", request, user)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")
    codes = generate_recovery_codes()
    user.recovery_code_hashes = [recovery_code_hash(code) for code in codes]
    user.totp_enabled_at = datetime.now(timezone.utc)
    user.totp_setup_expires_at = None
    audit(db, "auth.2fa_enabled", request, user)
    db.commit()
    return {"enabled": True, "recovery_codes": codes}


@app.get("/api/v1/owner/setup")
def setup_status(_: User = Depends(owner_user), db: Session = Depends(get_db)):
    config = db.scalar(select(PlatformConfiguration).limit(1))
    values = config.settings if config else {}
    sections = {key: {"label": label, "complete": setup_section_complete(key, values.get(key))}
                for key, label in REQUIRED_SETUP.items()}
    user = db.scalar(select(User).where(User.account_type == "owner"))
    sections["security"]["complete"] = bool(sections["security"]["complete"] and user and user.totp_enabled_at)
    completed = [key for key, data in sections.items() if data["complete"]]
    return {"platform_name": values.get("platform", {}).get("name", "DragonForge"), "sections": sections,
            "values": values,
            "completed_count": len(completed), "required_count": len(sections),
            "can_publish": len(completed) == len(sections), "published": bool(config and config.published_at),
            "registration_enabled": False}


@app.put("/api/v1/owner/setup")
def save_setup(payload: SetupInput, request: Request,
               x_reauth_password: str | None = Header(default=None, alias="X-Reauth-Password"),
               user: User = Depends(owner_user), db: Session = Depends(get_db)):
    require_reauthentication(request, user, x_reauth_password)
    if payload.section not in REQUIRED_SETUP:
        raise HTTPException(status_code=422, detail="Unknown setup section")
    if payload.section == "platform" and payload.value.get("domain"):
        raise HTTPException(status_code=422, detail="Set the working domain with DRAGONFORGE_DOMAIN")
    if not setup_value_is_safe(payload.value):
        raise HTTPException(status_code=422, detail="Store credentials in the deployment secret manager, not platform settings")
    config = db.scalar(select(PlatformConfiguration).limit(1))
    if not config:
        config = PlatformConfiguration(settings={})
        db.add(config)
    previous = config.settings.get(payload.section, {})
    config.settings = {**config.settings, payload.section: payload.value}
    config.version += 1
    audit(db, "owner.setup_section_updated", request, user,
          {"section": payload.section, "changed_keys": sorted(set(previous) | set(payload.value))})
    db.commit()
    return {"saved": True, "section": payload.section, "version": config.version}


@app.post("/api/v1/owner/publish")
def publish(request: Request, payload: SensitiveActionInput, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    require_reauthentication(request, user, payload.password)
    config = db.scalar(select(PlatformConfiguration).limit(1))
    values = config.settings if config else {}
    missing = [key for key in SETUP_REQUIRED_FIELDS if not setup_section_complete(key, values.get(key))]
    if not user.totp_enabled_at:
        missing.append("security.2fa")
    if missing:
        raise HTTPException(status_code=409, detail={"message": "Required setup remains incomplete", "missing": missing})
    config.published_at = datetime.now(timezone.utc)
    config.version += 1
    audit(db, "owner.platform_published", request, user, {"version": config.version})
    db.commit()
    return {"published": True, "version": config.version, "registration_enabled": False,
            "registration_reason": "Member verification and application review are not implemented yet."}


ADMIN_PERMISSION_DESCRIPTIONS = {
    "applications:review": "Review member applications",
    "users:support": "Provide user support",
    "users:status_limited": "View limited account status",
    "security:alerts": "Review security alerts",
    "operations:manage": "Manage routine operations",
}


@app.get("/api/v1/owner/admins")
def list_admins(_: User = Depends(owner_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AdminAccount).order_by(AdminAccount.slot)).all()
    result = []
    for row in rows:
        user = db.get(User, row.user_id)
        permissions = [permission.name for role in user.roles for permission in role.permissions]
        result.append({"slot": row.slot, "user_id": user.id, "email": user.email,
                       "display_name": user.display_name, "is_active": user.is_active,
                       "permissions": sorted(set(permissions)), "created_at": row.created_at.isoformat()})
    return {"limit": 5, "admins": result}


@app.get("/api/v1/admin/access")
def admin_access(user: User = Depends(current_user)):
    if user.account_type != "admin":
        raise HTTPException(status_code=403, detail="Administrator account required")
    permissions = sorted({permission.name for role in user.roles for permission in role.permissions})
    return {"account_type": "admin", "permissions": permissions,
            "available_actions": [], "modules": "NOT CONFIGURED"}


@app.post("/api/v1/owner/admins", status_code=201)
def create_admin(payload: AdminCreateInput, request: Request,
                 x_reauth_password: str | None = Header(default=None, alias="X-Reauth-Password"),
                 owner: User = Depends(owner_user), db: Session = Depends(get_db)):
    require_reauthentication(request, owner, x_reauth_password)
    if not payload.permissions or set(payload.permissions) - ADMIN_PERMISSION_DESCRIPTIONS.keys():
        raise HTTPException(status_code=422, detail="Assign one or more explicitly allowed permissions")
    if db.scalar(select(User.id).where(func.lower(User.email) == payload.email.lower())):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    occupied = set(db.scalars(select(AdminAccount.slot)).all())
    slot = next((candidate for candidate in range(1, 6) if candidate not in occupied), None)
    if slot is None:
        raise HTTPException(status_code=409, detail="The maximum of five additional administrators has been reached")
    try:
        hashed_password = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    admin = User(email=payload.email.lower(), display_name=payload.display_name, password_hash=hashed_password,
                 account_type="admin", email_verified_at=datetime.now(timezone.utc))
    db.add(admin)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    role = Role(name=f"admin:{admin.id}")
    db.add(role)
    for permission_name in sorted(set(payload.permissions)):
        permission = db.scalar(select(Permission).where(Permission.name == permission_name))
        if not permission:
            permission = Permission(name=permission_name, description=ADMIN_PERMISSION_DESCRIPTIONS[permission_name])
            db.add(permission)
        role.permissions.append(permission)
    admin.roles.append(role)
    db.add(AdminAccount(user_id=admin.id, created_by_owner_id=owner.id, slot=slot))
    audit(db, "owner.admin_created", request, owner, {"admin_user_id": admin.id, "slot": slot,
          "permissions": sorted(set(payload.permissions))})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Administrator account conflicts with an existing account") from exc
    return {"slot": slot, "user_id": admin.id, "email": admin.email,
            "display_name": admin.display_name, "permissions": sorted(set(payload.permissions))}


@app.get("/api/v1/owner/audit")
def owner_audit(limit: int = 100, _: User = Depends(owner_user), db: Session = Depends(get_db)):
    if not 1 <= limit <= 250:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 250")
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": row.id, "actor_user_id": row.actor_user_id, "event_type": row.event_type,
             "target_type": row.target_type, "target_id": row.target_id, "details": row.details,
             "created_at": row.created_at.isoformat()} for row in rows]


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
        database = "available"
    except Exception:
        database = "unavailable"
    state = "safe_mode" if database != "available" else "degraded"
    return {"status": state, "database": database, "market_data": "NOT CONFIGURED",
            "analysis_engine": "NOT CONFIGURED", "risk_engine": "NOT CONFIGURED",
            "notifications": "NOT CONFIGURED", "backups": "NOT CONFIGURED"}