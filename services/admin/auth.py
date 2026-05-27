"""
管理面板认证模块
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 安全配置
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Bearer token 安全方案
security = HTTPBearer()

# 会话存储（生产环境应使用 Redis）
_sessions: dict = {}


def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_credentials(username: str, password: str) -> bool:
    """验证用户名密码"""
    if username != ADMIN_USERNAME:
        return False
    
    # 如果没有设置密码哈希，使用默认密码（仅开发环境）
    if not ADMIN_PASSWORD_HASH:
        default_hash = hash_password("nexus_admin_2026")
        return hash_password(password) == default_hash
    
    return hash_password(password) == ADMIN_PASSWORD_HASH


def create_session(username: str, expires_hours: int = 24) -> str:
    """创建会话 token"""
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "username": username,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    }
    return token


def verify_session(token: str) -> Optional[str]:
    """验证会话 token，返回用户名"""
    session = _sessions.get(token)
    if not session:
        return None
    
    if datetime.now(timezone.utc) > session["expires_at"]:
        del _sessions[token]
        return None
    
    return session["username"]


def revoke_session(token: str) -> None:
    """撤销会话"""
    _sessions.pop(token, None)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """
    FastAPI 依赖项：获取当前认证用户
    
    使用方式:
        @app.get("/api/protected")
        async def protected_endpoint(user: str = Depends(get_current_user)):
            return {"user": user}
    """
    token = credentials.credentials
    username = verify_session(token)
    
    if not username:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return username


async def require_admin(
    user: str = Depends(get_current_user),
) -> str:
    """
    FastAPI 依赖项：要求管理员权限
    
    使用方式:
        @app.post("/api/admin-only")
        async def admin_endpoint(user: str = Depends(require_admin)):
            return {"admin": user}
    """
    if user != ADMIN_USERNAME:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
    return user
