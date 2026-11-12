"""
WebSocket JWT Authentication Middleware for Django Channels.

Intercepts incoming WebSocket connection handshakes, extracts JWT Bearer tokens
from either Sec-WebSocket-Protocol subprotocols, Authorization headers, or
query parameters (?token=<jwt> fallback), validates cryptographic signatures
against SimpleJWT, verifies connection origin against CORS whitelists, and attaches
the resolved authenticated User entity and selected subprotocol to the ASGI scope.
"""

from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def get_user_from_token(token_string: str):
    """
    Cryptographically verify JWT access token and retrieve database User.

    :param token_string: Raw JWT string extracted from connection params/protocols.
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


def is_origin_allowed(origin: str) -> bool:
    """
    Verify whether the WebSocket handshake Origin header is permitted.
    
    :param origin: Origin header URL string (e.g. 'http://localhost:8080').
    :return: True if origin is allowed, False otherwise.
    """
    if not origin:
        return True  # Direct server-to-server or test runner without origin header

    allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
    allow_all = getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)

    if allow_all or '*' in allowed_origins:
        return True

    clean_origin = origin.rstrip('/')
    for allowed in allowed_origins:
        if clean_origin == allowed.rstrip('/'):
            return True

    # If running in DEBUG mode, allow standard local development origins
    if getattr(settings, 'DEBUG', False):
        if 'localhost' in clean_origin or '127.0.0.1' in clean_origin:
            return True

    return False


def extract_token_and_subprotocol(scope: dict):
    """
    Extract JWT token and determine selected response subprotocol.
    
    Priority:
    1. Sec-WebSocket-Protocol: ['bearer', '<jwt>'] or ['<jwt>']
    2. URL query parameters: ?token=<jwt> (deprecated legacy fallback)
    
    :param scope: ASGI connection scope dictionary.
    :return: Tuple of (token_string: str | None, selected_subprotocol: str | None)
    """
    # 1. Inspect subprotocols list
    subprotocols = scope.get('subprotocols', [])
    if subprotocols:
        token = None
        for proto in subprotocols:
            proto_clean = proto.strip()
            if proto_clean.lower() == 'bearer':
                continue
            if proto_clean.count('.') == 2:
                token = proto_clean
                break
            elif not token and proto_clean.lower() != 'bearer':
                token = proto_clean

        if token:
            return token, 'bearer'

    # Also inspect Sec-WebSocket-Protocol raw header if subprotocols is empty
    headers = dict(scope.get('headers', []))
    raw_ws_proto = headers.get(b'sec-websocket-protocol', b'').decode('utf-8').strip()
    if raw_ws_proto:
        parts = [p.strip() for p in raw_ws_proto.split(',') if p.strip()]
        token = None
        for p in parts:
            if p.lower() == 'bearer':
                continue
            if p.count('.') == 2 or not token:
                token = p
        if token:
            return token, 'bearer'

    # 2. Inspect query parameters (?token=<jwt>)
    query_string = scope.get('query_string', b'').decode('utf-8')
    query_params = parse_qs(query_string)
    token_list = query_params.get('token', [])
    if token_list:
        return token_list[0].strip(), None

    return None, None


class JwtAuthMiddleware(BaseMiddleware):
    """
    Channels ASGI middleware to authenticate WebSocket handshakes via JWT.
    
    Supports:
    - Sec-WebSocket-Protocol: ['bearer', '<jwt>']
    - Deprecated query string: `?token=<jwt>`
    - Origin validation against CORS_ALLOWED_ORIGINS
    
    Populates:
    - `scope['user']`: Authenticated User or AnonymousUser
    - `scope['subprotocol']`: 'bearer' if authenticated via subprotocol (never raw token)
    - `scope['origin_rejected']`: True if origin is forbidden
    """

    async def __call__(self, scope, receive, send):
        # 1. Validate Origin header
        headers = dict(scope.get('headers', []))
        origin = headers.get(b'origin', b'').decode('utf-8').strip()

        if origin and not is_origin_allowed(origin):
            scope['origin_rejected'] = True
            scope['user'] = AnonymousUser()
            scope['subprotocol'] = None
            return await super().__call__(scope, receive, send)

        scope['origin_rejected'] = False

        # 2. Extract token from subprotocol or query string
        raw_token, selected_subprotocol = extract_token_and_subprotocol(scope)

        if raw_token:
            scope['user'] = await get_user_from_token(raw_token)
            if scope['user'].is_authenticated and selected_subprotocol:
                scope['subprotocol'] = selected_subprotocol
            else:
                scope['subprotocol'] = None
        else:
            scope['user'] = AnonymousUser()
            scope['subprotocol'] = None

        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    """
    Helper function wrapping standard ASGI application with JWT auth middleware.
    """
    return JwtAuthMiddleware(inner)
