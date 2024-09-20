from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.concurrency import asynccontextmanager
from starlette.config import Config
from starlette.requests import Request
from authlib.integrations.starlette_client import OAuth,OAuthError
# from .config import CLIENT_ID, CLIENT_SECRET
from starlette.middleware.sessions import SessionMiddleware
from fastapi_sso.models.user import CurrentUser
from fastapi_sso.models.token import Token
from fastapi_sso.services.group_management_service import GroupManagementService
from fastapi_sso.services.startup.initialize_database import ensure_file_exists, init_sqlite_database, insert_roles
from fastapi_sso.utils.auth import handleToken
from datetime import datetime, timedelta,timezone
from jose import JWTError, jwt
import secrets

# Configuration
config = Config('../.env')
print(config.file_values) 
JWT_SECRET_KEY = config.get('JWT_SECRET_KEY')
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

# oauth = OAuth(config)
oauth = OAuth()
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=config.file_values['GOOGLE_CLIENT_ID'],
    client_secret=config.file_values['GOOGLE_CLIENT_SECRET'],
    client_kwargs={
        'scope': 'email openid profile',
        'redirect_url': 'http://localhost:8000/auth'
    }
)

oauth.register(
    name='github',
    client_id=config.file_values['GITHUB_CLIENT_ID'],
    client_secret=config.file_values['GITHUB_CLIENT_SECRET'],
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'read:user user:email'},
)
# OAuth2 scheme for JWT
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="",  # Not used with Authlib
    tokenUrl="",  # Not used with Authlib
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_file_exists("../db/user.db")
    init_sqlite_database("../db/user.db")
    insert_roles("../db/user.db")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="add any string...")

def get_group_management_service():
    return GroupManagementService()

# Function to create JWT token // this will need to be move to auth.py
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc)+ timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt



async def get_current_user(token: str = Depends(oauth2_scheme),group_mgt_serv : GroupManagementService = Depends(get_group_management_service)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        id: str = payload.get("sub")
        if id is None:
            raise credentials_exception
        user_info = await group_mgt_serv.get_user_by_id(id)
        roles: List[str] = payload.get("roles", [])
        current_user = CurrentUser(
            id=user_info.id,
            username=user_info.username,
            background_information=user_info.background_information,
            email=user_info.email,
            full_name=user_info.full_name,
            profile_picture_url=user_info.profile_picture_url,
            status=user_info.status,
            is_active=user_info.is_active,
            is_verified=user_info.is_verified,
            phone_number=user_info.phone_number,
            auth_provider=user_info.auth_provider,
            roles=roles
        )
    except JWTError:
        raise credentials_exception
    return current_user

def has_role(required_roles: List[str]):
    async def role_checker(current_user: CurrentUser = Depends(get_current_user)):
        for role in required_roles:
            if role in current_user.roles:
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return role_checker


@app.get('/')
async def homepage(request: Request):
    user = request.session.get('user')
    if user:
        return {'message': f'Hello, {user["name"]}!'}
    return {'message': 'Hello, anonymous user!'}

@app.get('/login/{provider}')
async def login(provider: str, request: Request):
    redirect_uri = request.url_for('auth', provider=provider)
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)

@app.get('/auth/{provider}')
async def auth(provider: str, request: Request,group_mgt_serv : GroupManagementService = Depends(get_group_management_service)):
    client = oauth.create_client(provider)
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as error:
        return {'error': error.error}
    # Normalize user 
    user = await handleToken(token,client, group_mgt_serv)
    # Get User roles
    roles =  list(group_mgt_serv.get_user_roles(user.id))
    # create jwt
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "name": user.full_name, "roles":roles, "is_verified":user.is_verified},
        expires_delta=access_token_expires
    )
    
    refresh_token_info = group_mgt_serv.create_refresh_token(user.id)
    
    return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token_info['refresh_token'])

@app.post("/refresh")
async def refresh_token(refresh_token: str,group_mgt_serv : GroupManagementService = Depends(get_group_management_service)):
   
    # Fetch the refresh token 
    token_data = group_mgt_serv.get_refresh_token(refresh_token)
    # check in db
    if not token_data:
        raise HTTPException(status_code=400, detail="Invalid refresh token")
    # Will require re login
    if datetime.now(timezone.utc) > token_data["expires"]:
        group_mgt_serv.delete_refresh_token(refresh_token)
        raise HTTPException(status_code=400, detail="Refresh token expired")
    # Extract user_id from refresh token
    user_id = token_data["user_id"]
    user = group_mgt_serv.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    roles = group_mgt_serv.get_user_roles(user.id)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "name": user.full_name, "roles":roles, "is_verified":user.is_verified},
        expires_delta=access_token_expires
    )
    
    new_refresh_token = group_mgt_serv.create_refresh_token(user.id)
    group_mgt_serv.delete_refresh_token(refresh_token)
    
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": new_refresh_token}



@app.get("/admin-only")
async def admin_only(current_user: CurrentUser = Depends(has_role(["admin"]))):
    return {"message": "Welcome, admin!"}

@app.get("/user-or-admin")
async def user_or_admin(current_user: CurrentUser = Depends(has_role(["user", "admin"]))):
    return {"message": f"Welcome, {current_user.email}!"}


