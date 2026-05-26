
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_HOURS, ADMIN_USERNAME, ADMIN_PASSWORD


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


security = HTTPBearer()


def verify_password(plain_password: str, stored_password: str) -> bool:
    """비밀번호 검증 (안전한 해시 비교만 수행)"""
    try:
        return pwd_context.verify(plain_password, stored_password)
    except Exception:
        # 평문 비교 로직 삭제 (보안 강화)
        return False


def get_password_hash(password: str) -> str:
...


def authenticate_admin(username: str, password: str) -> bool:
    
    if username != ADMIN_USERNAME:
        return False
    return verify_password(password, ADMIN_PASSWORD)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta
        else timedelta(hours=JWT_EXPIRE_HOURS)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
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
