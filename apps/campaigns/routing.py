"""
WebSocket URL Routing for Campaigns and Inquiries.
"""

from django.urls import re_path
from apps.campaigns.consumers import InquiryChatConsumer

websocket_urlpatterns = [
    re_path(r'^ws/inquiries/(?P<inquiry_id>[0-9a-f-]+)/?$', InquiryChatConsumer.as_asgi(), name='ws_inquiry_chat'),
]

