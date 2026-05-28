from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.token import Token
from schemas.user import UserCreate, UserResponse
from security import create_access_token, hash_password, verify_password
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    注册新用户。
    - 邮箱唯一性检查
    - 密码 bcrypt hash 后存储，原文不落库
    """
    # 1. 检查邮箱是否已被注册
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # 2. 创建 User ORM 对象，密码哈希
    db_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
    )

    # 3. 写入数据库
    db.add(db_user)
    db.commit()
    db.refresh(db_user)  # 刷新拿到 DB 生成的 id/created_at

    return db_user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    用户登录，返回 JWT access token。
    OAuth2PasswordRequestForm 要求表单字段：username / password
    这里 username 字段实际存的是邮箱。
    """
    # 1. 用邮箱查用户（form_data.username 就是邮箱）
    user = db.query(User).filter(User.email == form_data.username).first()

    # 2. 用户不存在 or 密码错误 → 统一报同一个错误（防止枚举攻击）
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 检查账户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # 4. 生成 JWT，sub 放 user_id（字符串）。role 不进 token，
    #    由 get_current_user 实时从 DB 读，避免角色变更后 token 不一致。
    access_token = create_access_token(subject=str(user.id))

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    """
    返回当前登录用户信息。受保护端点：必须带有效 Bearer token。
    这是验证整条鉴权链是否通的最小端点。
    """
    return current_user
