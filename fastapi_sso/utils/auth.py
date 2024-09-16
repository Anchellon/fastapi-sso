from authlib.integrations.starlette_client import OAuthError
async def handleToken(token ,client):
    if(client.name == 'google'):
        user_info = token.get('userinfo')
        



        return user
    elif(client.name == 'github'):
        try:
            resp = await client.get('user', token=token)
            # resp.raise_for_status()
            user_info = resp.json()
            email_resp = await client.get('user/emails', token=token)
            print(email_resp)
            user = {
                'user_info':user_info,
                'email':email_resp.json()
            }
            return user
        except OAuthError as error:
            return f"OAuth error: {error.error}"