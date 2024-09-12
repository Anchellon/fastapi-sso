from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from starlette.config import Config
from starlette.requests import Request
from authlib.integrations.starlette_client import OAuth,OAuthError
from .config import CLIENT_ID, CLIENT_SECRET
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="add any string...")

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


# Configure multiple OIDC providers
# oauth.register(
#     name='google',
#     server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
#     client_kwargs={
#         'scope': 'openid email profile',
#         'redirect_url' : 'http://localhost:8000/auth'
#     }
    
# )

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
async def auth(provider: str, request: Request):
    try:
        print("hello")
        token = await oauth.create_client(provider).authorize_access_token(request)
    except OAuthError as error:
        return {'error': error.error}
    user = token.get('userinfo')
    request.session['user'] = dict(user)
    print(request.session['user'])
    return {'message': f'Successfully authenticated with {provider}', 'user': user}


