"""
多重验证系统
- 密码验证 (bcrypt)
- TOTP 2FA (Google Authenticator)
- IP 白名单
- JWT 会话管理
"""

import hashlib
import hmac
import os
import time
import struct
import base64
import secrets
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("nexus.web.auth")

# === 配置 ===
SECRET_KEY = os.getenv("WEB_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("WEB_JWT_EXPIRE_HOURS", "24"))
MAX_LOGIN_ATTEMPTS = int(os.getenv("WEB_MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("WEB_LOCKOUT_MINUTES", "15"))

# IP 白名单 (空=允许所有)
IP_WHITELIST_RAW = os.getenv("WEB_IP_WHITELIST", "")
IP_WHITELIST: List[str] = [ip.strip() for ip in IP_WHITELIST_RAW.split(",") if ip.strip()]

# === 密码管理 ===
# 使用 PBKDF2 代替 bcrypt 以减少依赖
ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("WEB_ADMIN_PASSWORD_HASH", "")

# TOTP
TOTP_SECRET = os.getenv("WEB_TOTP_SECRET", "")  # Base32 编码
TOTP_ENABLED = os.getenv("WEB_TOTP_ENABLED", "false").lower() == "true"

# Bearer 安全方案
security = HTTPBearer(auto_error=False)

# 会话存储 (内存，生产环境应用 Redis)
_sessions: Dict[str, Dict[str, Any]] = {}
_login_attempts: Dict[str, Dict[str, Any]] = {}


def _pbkdf2_hash(password: str, salt: Optional[str] = None) -> str:
    """PBKDF2 密码哈希"""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${dk.hex()}"


def _verify_pbkdf2(password: str, stored_hash: str) -> bool:
    """验证 PBKDF2 哈希"""
    if "$" not in stored_hash:
        # 兼容旧版 SHA256 哈希
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    parts = stored_hash.split("$", 1)
    if len(parts) != 2:
        return False
    salt, _ = parts
    return _pbkdf2_hash(password, salt) == stored_hash


def hash_password(password: str) -> str:
    """生成密码哈希"""
    return _pbkdf2_hash(password)


def verify_password(password: str) -> bool:
    """验证管理员密码"""
    if not ADMIN_PASSWORD_HASH:
        # 未设置密码哈希，使用默认密码
        default_hash = hashlib.sha256("nexus_admin_2026".encode()).hexdigest()
        return hashlib.sha256(password.encode()).hexdigest() == default_hash
    return _verify_pbkdf2(password, ADMIN_PASSWORD_HASH)


# === TOTP 实现 ===

def _hotp(secret_bytes: bytes, counter: int) -> str:
    """HOTP 算法"""
    msg = struct.pack(">Q", counter)
    h = hmac.HMAC(secret_bytes, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1000000).zfill(6)


def generate_totp_secret() -> str:
    """生成 TOTP 密钥 (Base32)"""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode().rstrip("=")


def verify_totp(code: str, secret: Optional[str] = None) -> bool:
    """验证 TOTP 码 (允许 ±1 窗口)"""
    if not TOTP_ENABLED:
        return True  # 未启用直接通过

    secret = secret or TOTP_SECRET
    if not secret:
        return True  # 未配置密钥直接通过

    try:
        # 补全 Base32 填充
        padded = secret + "=" * (8 - len(secret) % 8) if len(secret) % 8 else secret
        secret_bytes = base64.b32decode(padded.upper())
    except Exception:
        logger.error("Invalid TOTP secret")
        return False

    current_time = int(time.time()) // 30
    for offset in [-1, 0, 1]:
        counter = current_time + offset
        msg = struct.pack(">Q", counter)
        h = hmac.HMAC(secret_bytes, msg, hashlib.sha1).digest()
        o = h[-1] & 0x0F
        otp = str((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000).zfill(6)
        if otp == code:
            return True
    return False


def get_totp_uri(username: str = "admin", issuer: str = "AltcoinNexus") -> str:
    """生成 TOTP URI (用于生成二维码)"""
    secret = TOTP_SECRET or generate_totp_secret()
    return f"otpauth://totp/{issuer}:{username}?secret={secret}&issuer={issuer}&digits=6&period=30"


# === IP 白名单 ===

def check_ip_whitelist(request: Request) -> bool:
    """检查 IP 白名单"""
    if not IP_WHITELIST:
        return True  # 空白名单=不限制

    client_ip = _get_client_ip(request)

    # 支持 CIDR 和精确匹配
    for allowed in IP_WHITELIST:
        if allowed == client_ip:
            return True
        # 简单的子网匹配
        if "/" in allowed:
            if _ip_in_cidr(client_ip, allowed):
                return True
        # 127.0.0.1 和 localhost 总是允许
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return True

    return False


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    # 检查代理头
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _ip_in_cidr(ip: str, cidr: str) -> bool:
    """简单 CIDR 匹配"""
    try:
        network, prefix_len = cidr.split("/")
        prefix_len = int(prefix_len)
        ip_parts = [int(p) for p in ip.split(".")]
        net_parts = [int(p) for p in network.split(".")]
        ip_int = (ip_parts[0] << 24) | (ip_parts[1] << 16) | (ip_parts[2] << 8) | ip_parts[3]
        net_int = (net_parts[0] << 24) | (net_parts[1] << 16) | (net_parts[2] << 8) | net_parts[3]
        mask = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF
        return (ip_int & mask) == (net_int & mask)
    except Exception:
        return False


# === 登录限速 ===

def _check_login_rate(client_ip: str) -> bool:
    """检查登录频率限制"""
    now = datetime.now(timezone.utc)
    attempt = _login_attempts.get(client_ip)

    if not attempt:
        return True

    # 检查锁定
    if attempt.get("locked_until"):
        locked = attempt["locked_until"]
        if now < locked:
            return False
        # 锁定过期，重置
        _login_attempts.pop(client_ip, None)
        return True

    return attempt.get("count", 0) < MAX_LOGIN_ATTEMPTS


def _record_login_attempt(client_ip: str, success: bool) -> None:
    """记录登录尝试"""
    now = datetime.now(timezone.utc)

    if success:
        _login_attempts.pop(client_ip, None)
        return

    if client_ip not in _login_attempts:
        _login_attempts[client_ip] = {"count": 0, "first_attempt": now}

    _login_attempts[client_ip]["count"] += 1
    _login_attempts[client_ip]["last_attempt"] = now

    if _login_attempts[client_ip]["count"] >= MAX_LOGIN_ATTEMPTS:
        _login_attempts[client_ip]["locked_until"] = now + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning(f"IP {client_ip} locked out for {LOCKOUT_MINUTES} minutes")


# === JWT 会话 ===

def _create_jwt(payload: Dict[str, Any]) -> str:
    """创建简单 JWT (HS256)"""
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    payload_encoded = base64.urlsafe_b64encode(
        json.dumps(payload, default=str).encode()
    ).rstrip(b"=").decode()

    signing_input = f"{header}.{payload_encoded}"
    signature = hmac.HMAC(
        SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_encoded = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    return f"{header}.{payload_encoded}.{sig_encoded}"


def _verify_jwt(token: str) -> Optional[Dict[str, Any]]:
    """验证 JWT"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header, payload_encoded, sig_received = parts

        # 验证签名
        signing_input = f"{header}.{payload_encoded}"
        expected_sig = base64.urlsafe_b64encode(
            hmac.HMAC(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()

        if not hmac.compare_digest(sig_received, expected_sig):
            return None

        # 解码 payload
        padding = 4 - len(payload_encoded) % 4
        if padding != 4:
            payload_encoded += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_encoded))

        # 检查过期
        exp = payload.get("exp")
        if exp and datetime.fromisoformat(exp) < datetime.now(timezone.utc):
            return None

        return payload
    except Exception:
        return None


def create_session(username: str) -> str:
    """创建会话，返回 JWT token"""
    session_id = secrets.token_urlsafe(16)
    expires = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)

    payload = {
        "sub": username,
        "sid": session_id,
        "exp": expires.isoformat(),
        "iat": datetime.now(timezone.utc).isoformat(),
    }

    token = _create_jwt(payload)

    _sessions[session_id] = {
        "username": username,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires,
        "last_active": datetime.now(timezone.utc),
    }

    return token


def revoke_session(session_id: str) -> None:
    """撤销会话"""
    _sessions.pop(session_id, None)


def get_active_sessions() -> List[Dict[str, Any]]:
    """获取所有活跃会话"""
    now = datetime.now(timezone.utc)
    active = []
    expired_ids = []

    for sid, session in _sessions.items():
        if session["expires_at"] < now:
            expired_ids.append(sid)
        else:
            active.append({
                "session_id": sid,
                "username": session["username"],
                "created_at": session["created_at"].isoformat(),
                "last_active": session["last_active"].isoformat(),
            })

    # 清理过期会话
    for sid in expired_ids:
        _sessions.pop(sid, None)

    return active


# === FastAPI 依赖 ===

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """获取当前认证用户"""
    # 1. IP 白名单检查
    if not check_ip_whitelist(request):
        client_ip = _get_client_ip(request)
        logger.warning(f"IP not in whitelist: {client_ip}")
        raise HTTPException(status_code=403, detail="IP not allowed")

    # 2. Token 验证
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _verify_jwt(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 验证会话是否仍然有效
    session_id = payload.get("sid")
    if session_id and session_id in _sessions:
        _sessions[session_id]["last_active"] = datetime.now(timezone.utc)
    elif session_id:
        raise HTTPException(status_code=401, detail="Session revoked")

    return payload.get("sub", "admin")


async def require_auth(user: str = Depends(get_current_user)) -> str:
    """要求认证的快捷依赖"""
    return user


# === 登录验证入口 ===

def authenticate(
    username: str,
    password: str,
    totp_code: Optional[str],
    request: Request,
) -> Dict[str, Any]:
    """
    完整认证流程:
    1. IP 白名单
    2. 登录频率限制
    3. 用户名密码验证
    4. TOTP 2FA 验证
    5. 创建会话
    """
    client_ip = _get_client_ip(request)

    # IP 白名单
    if not check_ip_whitelist(request):
        raise HTTPException(status_code=403, detail="IP not allowed")

    # 频率限制
    if not _check_login_rate(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Try again in {LOCKOUT_MINUTES} minutes.",
        )

    # 用户名验证
    if username != ADMIN_USERNAME:
        _record_login_attempt(client_ip, False)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 密码验证
    if not verify_password(password):
        _record_login_attempt(client_ip, False)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # TOTP 验证
    if TOTP_ENABLED:
        if not totp_code:
            raise HTTPException(status_code=401, detail="2FA code required")
        if not verify_totp(totp_code):
            _record_login_attempt(client_ip, False)
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

    # 成功
    _record_login_attempt(client_ip, True)
    token = create_session(username)

    logger.info(f"Login successful: {username} from {client_ip}")

    return {
        "token": token,
        "username": username,
        "expires_in": JWT_EXPIRE_HOURS * 3600,
        "totp_enabled": TOTP_ENABLED,
    }
