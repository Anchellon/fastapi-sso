from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.concurrency import asynccontextmanager
from starlette.config import Config
from starlette.requests import Request
from authlib.integrations.starlette_client import OAuth,OAuthError
# from .config import CLIENT_ID, CLIENT_SECRET
from starlette.middleware.sessions import SessionMiddleware
from fastapi_sso.services.group_management_service import GroupManagementService
from fastapi_sso.services.startup.initialize_database import ensure_file_exists, init_sqlite_database
from fastapi_sso.utils.auth import handleToken

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_file_exists("../db/user.db")
    init_sqlite_database("../db/user.db")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="add any string...")

def get_group_management_service():
    return GroupManagementService()

# Configuration
config = Config('../.env')
print(config.file_values)
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
    #  Normalize user 
    user = await handleToken(token,client, group_mgt_serv)
    if(user.is_verified):
        # create a JWT session token and return the session user info in this 
        pass
    return {'message': f'Successfully authenticated with {provider}', 'user': user}


