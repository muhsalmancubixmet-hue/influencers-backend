"""
WebSocket Consumers for Campaigns & Direct Collaboration Inquiries.

Provides real-time bidirectional WebSocket communication between Creators and Brands
with strict tenant boundaries, message persistence, typing indicators, and read receipts.
"""

import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


@database_sync_to_async
def verify_inquiry_access(inquiry_id: str, user):
    """
    Verify whether the authenticated user is an authorized participant
    in the inquiry thread (either the Creator, Brand owner, or Super Admin).

    :param inquiry_id: UUID of the inquiry.
    :param user: Authenticated User entity.
    :return: Tuple of (has_access: bool, sender_info: dict, error_msg: str)
    """
    from apps.campaigns.models import Inquiry

    try:
        inquiry = Inquiry.objects.select_related(
            'creator__user', 'business__user'
        ).get(id=inquiry_id, is_deleted=False)
    except (Inquiry.DoesNotExist, ValueError):
        return False, {}, "Inquiry not found."

    is_creator = False
    is_business = False
    sender_name = user.get_full_name() or user.email
    sender_avatar = ""

    if hasattr(user, 'creator_profile') and inquiry.creator_id == user.creator_profile.id:
        is_creator = True
        sender_name = user.creator_profile.display_name or sender_name
        sender_avatar = user.creator_profile.photo_url or ""
    elif hasattr(user, 'business_profile') and inquiry.business_id == user.business_profile.id:
        is_business = True
        sender_name = user.business_profile.company_name or sender_name
        sender_avatar = user.business_profile.logo_url or ""
    elif user.is_staff or user.is_superuser:
        sender_name = f"Support ({user.email})"
    else:
        return False, {}, "You are not a participant in this collaboration thread."

    sender_info = {
        'sender_role': 'creator' if is_creator else ('business' if is_business else 'admin'),
        'sender_name': sender_name,
        'sender_avatar': sender_avatar,
    }
    return True, sender_info, ""


@database_sync_to_async
def persist_inquiry_message(inquiry_id: str, user, body: str, attachment_url: str = ""):
    """
    Persist new incoming chat message to database and update inquiry activity timestamp.

    :param inquiry_id: UUID string of the inquiry thread.
    :param user: Authenticated sender User.
    :param body: Text content of the message.
    :param attachment_url: Optional media attachment URL.
    :return: Serialized message dictionary ready for broadcast.
    """
    from apps.campaigns.models import Inquiry, InquiryMessage

    inquiry = Inquiry.objects.get(id=inquiry_id)
    msg = InquiryMessage.objects.create(
        inquiry=inquiry,
        sender=user,
        body=body.strip(),
        attachment_url=attachment_url or "",
        is_read=False
    )
    inquiry.updated_at = timezone.now()
    inquiry.save(update_fields=['updated_at'])

    # Determine sender role and presentation name
    sender_role = 'admin'
    sender_name = user.get_full_name() or user.email
    sender_avatar = ""

    if hasattr(user, 'creator_profile') and inquiry.creator_id == user.creator_profile.id:
        sender_role = 'creator'
        sender_name = user.creator_profile.display_name or sender_name
        sender_avatar = user.creator_profile.photo_url or ""
    elif hasattr(user, 'business_profile') and inquiry.business_id == user.business_profile.id:
        sender_role = 'business'
        sender_name = user.business_profile.company_name or sender_name
        sender_avatar = user.business_profile.logo_url or ""

    # Wire automated notification trigger on chat message (REQ-NOTIF-02)
    try:
        from apps.common.api.v1.services import create_user_notification
        from apps.common.models import NotificationKind
        target_user = (
            inquiry.business.user
            if (inquiry.creator and user == inquiry.creator.user)
            else (inquiry.creator.user if inquiry.creator else None)
        )
        if target_user and target_user != user:
            create_user_notification(
                recipient=target_user,
                title=f"New Chat Message: {inquiry.subject}",
                message=f"You received a message from {sender_name}.",
                kind=NotificationKind.USER
            )
    except Exception:
        pass

    return {
        'id': str(msg.id),
        'inquiry_id': str(inquiry_id),
        'sender_id': str(user.id),
        'sender_role': sender_role,
        'sender_name': sender_name,
        'sender_avatar': sender_avatar,
        'body': msg.body,
        'attachment_url': msg.attachment_url,
        'is_read': False,
        'created_at': msg.created_at.isoformat(),
    }


@database_sync_to_async
def mark_inquiry_messages_as_read(inquiry_id: str, user):
    """
    Mark all unread messages sent by the counterparty as read.

    :param inquiry_id: UUID of the inquiry.
    :param user: Current authenticated reader.
    :return: Count of newly read messages.
    """
    from apps.campaigns.models import InquiryMessage

    updated_count = InquiryMessage.objects.filter(
        inquiry_id=inquiry_id,
        is_read=False
    ).exclude(sender=user).update(is_read=True)

    return updated_count


class InquiryChatConsumer(AsyncJsonWebsocketConsumer):
    """
    Async WebSocket consumer managing live chat threads for collaboration inquiries.
    
    Supported Inbound Actions:
    - {"action": "send_message", "body": "Hello", "attachment_url": ""}
    - {"action": "mark_read"}
    - {"action": "typing", "is_typing": true}
    """

    async def connect(self):
        """
        Handle WebSocket handshake and authenticate connecting client.
        """
        self.inquiry_id = self.scope['url_route']['kwargs'].get('inquiry_id')
        self.user = self.scope.get('user')

        # 0. Reject disallowed origin
        if self.scope.get('origin_rejected'):
            await self.close(code=4403)
            return

        # 1. Reject unauthenticated anonymous connections
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        # 2. Strict tenant authorization check
        has_access, sender_info, err = await verify_inquiry_access(self.inquiry_id, self.user)
        if not has_access:
            await self.close(code=4403)
            return

        self.sender_info = sender_info
        self.room_group_name = f"inquiry_{self.inquiry_id}"

        # 3. Join broadcast channel group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 4. Accept handshake with selected subprotocol (bearer) or default (never raw token)
        subprotocol = self.scope.get('subprotocol')
        if subprotocol:
            await self.accept(subprotocol=subprotocol)
        else:
            await self.accept()

        # 5. Notify connecting client of active real-time session
        await self.send_json({
            'type': 'connection_established',
            'inquiry_id': str(self.inquiry_id),
            'user_id': str(self.user.id),
            'sender_role': self.sender_info.get('sender_role')
        })

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnect and leave channel group.
        """
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        """
        Process inbound JSON frames from the frontend client.
        """
        action = content.get('action')

        if action == 'send_message':
            body = content.get('body', '').strip()
            attachment_url = content.get('attachment_url', '').strip()
            if not body and not attachment_url:
                await self.send_json({'error': 'Message body or attachment required.'})
                return

            # Save message to database
            message_data = await persist_inquiry_message(
                inquiry_id=self.inquiry_id,
                user=self.user,
                body=body,
                attachment_url=attachment_url
            )

            # Broadcast to channel group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )

        elif action == 'mark_read':
            read_count = await mark_inquiry_messages_as_read(self.inquiry_id, self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'messages_read',
                    'inquiry_id': str(self.inquiry_id),
                    'reader_id': str(self.user.id),
                    'read_count': read_count
                }
            )

        elif action == 'typing':
            is_typing = bool(content.get('is_typing', False))
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'user_id': str(self.user.id),
                    'sender_name': self.sender_info.get('sender_name'),
                    'is_typing': is_typing
                }
            )

    async def chat_message(self, event):
        """
        Deliver broadcasted chat message to WebSocket client.
        """
        await self.send_json({
            'type': 'new_message',
            'message': event['message']
        })

    async def messages_read(self, event):
        """
        Deliver read receipts to WebSocket client.
        """
        await self.send_json({
            'type': 'messages_read',
            'inquiry_id': event['inquiry_id'],
            'reader_id': event['reader_id'],
            'read_count': event['read_count']
        })

    async def user_typing(self, event):
        """
        Deliver typing notifications to client (suppressed for self).
        """
        if event['user_id'] != str(self.user.id):
            await self.send_json({
                'type': 'user_typing',
                'user_id': event['user_id'],
                'sender_name': event['sender_name'],
                'is_typing': event['is_typing']
            })

