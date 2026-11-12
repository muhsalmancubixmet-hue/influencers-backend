"""
Asynchronous Celery tasks for creator domain operations, including branded Media Kit PDF dispatch.
Adheres strictly to BACKEND_ENGINEERING_RULES.md standards with typed signatures and full docstrings.
"""

import os
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_media_kit_email_task(
    self,
    creator_id: str,
    requester_email: str,
    requester_name: str = "",
    pdf_path: str = ""
) -> bool:
    """
    Dispatch a branded Media Kit & Rate Card PDF email to an inquiring brand or client.

    :param self: Celery task execution instance for retry handling.
    :param creator_id: UUID string of the target CreatorProfile.
    :param requester_email: Recipient email address of the inquiring brand/client.
    :param requester_name: Optional contact name of the requester.
    :param pdf_path: Absolute filesystem path to the pre-rendered PDF document.
    :return: True if the dispatch succeeded.
    """
    from apps.creators.models import CreatorProfile

    try:
        creator = CreatorProfile.objects.select_related('user').get(id=creator_id)
    except (CreatorProfile.DoesNotExist, ValueError) as err:
        logger.error(f"Failed to find creator {creator_id} for media kit dispatch: {err}")
        return False

    display_name = creator.display_name or creator.handle
    subject = f"Influencers.com Media Kit & Rate Card — @{creator.handle}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '"Influencers.com" <support@influencers.com>')
    if '<' in from_email and not from_email.startswith('"'):
        name, addr = from_email.split('<', 1)
        from_email = f'"{name.strip()}" <{addr}'

    html_content = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 24px;">
      <div style="background: #0f172a; padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
        <span style="color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase;">INFLUENCERS.COM</span>
        <h1 style="color: #ffffff; font-size: 20px; margin: 8px 0 0;">Official Creator Media Kit</h1>
      </div>
      <div style="background: #ffffff; padding: 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 12px 12px;">
        <p>Hello{f' {requester_name}' if requester_name else ''},</p>
        <p>Thank you for your interest in collaborating with <strong>{display_name}</strong> (<code>@{creator.handle}</code>).</p>
        <p>Attached to this email is the official, verified Media Kit and commercial Rate Card featuring audience demographics, platform reach, and service packages.</p>
        <div style="background: #f8fafc; border-left: 4px solid #0284c7; padding: 12px 16px; margin: 20px 0; border-radius: 4px;">
          <p style="margin: 0; font-size: 13px; color: #334155;">
            Ready to initiate a collaboration? Book directly through our secure platform to benefit from escrow payment protection and milestone tracking.
          </p>
        </div>
        <p style="font-size: 12px; color: #64748b; margin-top: 24px;">
          &copy; 2026 Influencers.com Inc. All rights reserved.
        </p>
      </div>
    </body>
    </html>
    """
    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[requester_email]
        )
        msg.attach_alternative(html_content, "text/html")

        # Attach PDF if file exists
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                msg.attach(
                    filename=f"MediaKit_{creator.handle}.pdf",
                    content=f.read(),
                    mimetype='application/pdf'
                )
        else:
            # Fallback inline generation if file not yet on disk
            from apps.creators.api.v1.services import generate_creator_media_kit_pdf
            pdf_bytes = generate_creator_media_kit_pdf(creator)
            msg.attach(
                filename=f"MediaKit_{creator.handle}.pdf",
                content=pdf_bytes,
                mimetype='application/pdf'
            )

        msg.send(fail_silently=False)
        logger.info(f"Media kit PDF successfully dispatched to {requester_email} for @{creator.handle}")
        return True

    except Exception as exc:
        logger.error(f"Failed to dispatch media kit email to {requester_email}: {exc}")
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            try:
                raise self.retry(exc=exc)
            except Exception:
                pass
        return False
