import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext
from bot.config import PANEL_SECRET_KEY, PANEL_USERNAME, PANEL_PASSWORD

router   = APIRouter()
security = HTTPBearer()
pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24  # 24 hours in minutes

class LoginRequest(BaseModel):
    username: str
    password: str

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode(payload, PANEL_SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, PANEL_SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token tidak valid atau sudah expired.")

@router.post("/login")
async def login(req: LoginRequest):
    if req.username != PANEL_USERNAME or req.password != PANEL_PASSWORD:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    token = create_token({"sub": req.username})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
async def me(payload: dict = Depends(verify_token)):
    return {"username": payload.get("sub"), "status": "authenticated"}
