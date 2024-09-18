from authlib.integrations.starlette_client import OAuthError

from fastapi_sso.models.user import UserCreate
from fastapi_sso.services.group_management_service import GroupManagementService
async def handleToken(token ,client, group_management_service: GroupManagementService):
    # To Normalize The user we must create the user and also assign roles that will be required for the user 
    if(client.name == 'google'):
        user_info = token.get('userinfo')
        # Find the user if exists
        user = group_management_service.get_user_by_email_and_provider(user_info['email'],'google')
        if(user):
            return user
        # Creating a repr of the user
        else:
            user_create = UserCreate(
                id=-1, # needs to be revisted
                email=user_info['email'],
                full_name=user_info['name'],
                auth_provider='google'
            )
            
    elif(client.name == 'github'):
        try:
            resp = await client.get('user', token=token)
            # resp.raise_for_status()
            user_info = resp.json()
            email_resp = await client.get('user/emails', token=token)
            email_info = email_resp.json()
            emailAddr = None
            for profile in email_info:
                if profile['primary'] and profile['verified']:
                    emailAddr = profile['email']
            user = group_management_service.get_user_by_email_and_provider(emailAddr,'github')
            if(user):
                return user
            user_create = UserCreate(
                id=-1,  # Assuming -1 is a placeholder for auto-increment
                email=emailAddr,
                full_name=user_info['name'],
                auth_provider='github'
            )
        except OAuthError as error:
            return f"OAuth error: {error.error}"
    user = group_management_service.create_user(user_create)
    # Potentially assign roles here 
    return user