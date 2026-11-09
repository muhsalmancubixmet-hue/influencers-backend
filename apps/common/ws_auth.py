"""
WebSocket JWT Authentication Middleware for Django Channels.

Intercepts incoming WebSocket connection handshakes, extracts JWT Bearer tokens
from either URL query parameters (?token=<jwt>) or subprotocols/headers,
verifies cryptographic signature against SimpleJWT, and attaches the resolved
authenticated User entity to the ASGI connection scope.
"""

from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def get_user_from_token(token_string: str):
    """
    Cryptographically verify JWT access token and retrieve database User.

    :param token_string: Raw JWT string extracted from connection query params.
    :return: Authenticated User instance or AnonymousUser if invalid/expired.
    """
    from apps.accounts.models import User
    try:
        validated_token = AccessToken(token_string)
        user_id = validated_token.get('user_id')
        if not user_id:
            return AnonymousUser()
        return User.objects.filter(id=user_id, is_active=True).first() or AnonymousUser()
    except (InvalidToken, TokenError, Exception):
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Channels ASGI middleware to authenticate WebSocket handshakes via JWT.
    
    Inspects query string parameters for a `token` key:
    `ws://domain/ws/inquiries/<id>/?token=eyJhbGciOi...`
    Populates `scope['user']` with the active user or `AnonymousUser()`.
    """

    async def __call__(self, scope, receive, send):
        """
        ASGI middleware handler for connection scopes.
        """
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token_list = query_params.get('token', [])

        if token_list:
            raw_token = token_list[0]
            scope['user'] = await get_user_from_token(raw_token)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    """
    Helper function wrapping standard ASGI application with JWT auth middleware.
    """
    return JwtAuthMiddleware(inner)

