
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_HOURS, ADMIN_USERNAME, ADMIN_PASSWORD


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


security = HTTPBearer()


def verify_password(plain_password: str, stored_password: str) -> bool:
    """비밀번호 검증 (해시 우선, 실패 시 평문 비교 fallback)"""
    try:
        # stored_password가 유효한 해시인지 확인
        if pwd_context.identify(stored_password):
            return pwd_context.verify(plain_password, stored_password)
    except Exception:
        pass
    
    # 해시가 아니거나 검증 실패 시 평문 비교 (보안상 권장되지 않으나 현재 설정을 위해 유지)
    return plain_password == stored_password


def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)


def authenticate_admin(username: str, password: str) -> bool:
    """관리자 인증 - 평문 또는 해시된 비밀번호 모두 지원"""
    if username != ADMIN_USERNAME:
        return False
    
    # ADMIN_PASSWORD가 해시값이면 해시 비교, 평문이면 직접 비교
    if ADMIN_PASSWORD.startswith('$'):
        # 해시된 비밀번호
        return verify_password(password, ADMIN_PASSWORD)
    else:
        # 평문 비밀번호 (개발/테스트용)
        return password == ADMIN_PASSWORD


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta if expires_delta
        else timedelta(hours=JWT_EXPIRE_HOURS)
    )
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "admin_access"
    })
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 토큰입니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        username: str = payload.get("sub")
        token_type: str = payload.get("type")

        if username is None or token_type != "admin_access":
            raise credentials_exception

        return payload

    except JWTError:
        raise credentials_exception


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    
    return verify_token(credentials.credentials)
