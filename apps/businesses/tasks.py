"""
Asynchronous Celery tasks for brand and business lifecycle events.
Adheres strictly to BACKEND_ENGINEERING_RULES.md standards with typed signatures and full docstrings.
"""

import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_business_welcome_email_task(
    self,
    user_id: str,
    email: str,
    company_name: str,
    contact_name: str = ""
) -> bool:
    """
    Dispatch a branded HTML & text welcome email to a newly registered business / brand.

    :param self: Celery task execution instance for retry control.
    :param user_id: UUID string primary key of the User account.
    :param email: Recipient electronic mail address of the business.
    :param company_name: Legal or trading company name of the brand.
    :param contact_name: Optional contact person name.
    :return: True if the email dispatch succeeded, False otherwise.
    :raises Exception: Propagates mail dispatch errors to Celery retry handler.
    """
    greeting_name = contact_name.strip() if contact_name.strip() else company_name.strip()
    brand_suite_url = getattr(settings, 'BRAND_SUITE_URL', 'http://localhost:8083').rstrip('/')
    login_url = f"{brand_suite_url}/login"

    subject = f"Welcome to Influencers.com — Your Brand Workspace is Ready ({company_name})"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '"Influencers.com" <support@influencers.com>')
    if '<' in from_email and not from_email.startswith('"'):
        name, addr = from_email.split('<', 1)
        name = name.strip()
        from_email = f'"{name}" <{addr}' if '.' in name else f'{name} <{addr}'

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Welcome to Influencers.com</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.6;">
  <div style="max-width: 600px; margin: 32px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);">
    
    <!-- Header Banner -->
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 32px 24px; text-align: center;">
      <span style="display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38bdf8; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; padding: 4px 12px; border-radius: 20px;">
        Brand & Business Suite
      </span>
      <h1 style="color: #ffffff; font-size: 24px; font-weight: 700; margin: 12px 0 0 0; letter-spacing: -0.5px;">
        Influencers<span style="color: #10b981;">.com</span>
      </h1>
      <p style="color: #94a3b8; font-size: 13px; margin: 6px 0 0 0;">
        Enterprise Creator Discovery & Campaign Infrastructure
      </p>
    </div>

    <!-- Main Content -->
    <div style="padding: 32px 28px;">
      <h2 style="font-size: 18px; font-weight: 600; color: #0f172a; margin: 0 0 16px 0;">
        Welcome to Influencers.com, {greeting_name}!
      </h2>
      <p style="font-size: 14px; color: #334155; margin: 0 0 16px 0;">
        Your official brand management workspace for <strong>{company_name}</strong> has been successfully provisioned. You now have instant access to our curated network of verified creators, structured collaboration tools, and transparent analytics.
      </p>

      <!-- Account Summary Card -->
      <div style="background-color: #f1f5f9; border-radius: 12px; padding: 18px 20px; margin: 24px 0;">
        <h3 style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #64748b; margin: 0 0 12px 0;">
          Workspace Details
        </h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 4px 0; color: #64748b; width: 140px;">Company:</td>
            <td style="padding: 4px 0; font-weight: 600; color: #0f172a;">{company_name}</td>
          </tr>
          <tr>
            <td style="padding: 4px 0; color: #64748b;">Account Email:</td>
            <td style="padding: 4px 0; font-weight: 600; color: #0f172a;">{email}</td>
          </tr>
          <tr>
            <td style="padding: 4px 0; color: #64748b;">Portal Access:</td>
            <td style="padding: 4px 0; font-weight: 600; color: #10b981;">Active & Ready</td>
          </tr>
        </table>
      </div>

      <!-- Action Button -->
      <div style="text-align: center; margin: 32px 0 24px 0;">
        <a href="{login_url}" style="display: inline-block; background-color: #047857; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; padding: 14px 32px; border-radius: 10px; box-shadow: 0 2px 6px rgba(4, 120, 87, 0.25);">
          Open Brand Suite Workspace →
        </a>
      </div>

      <p style="font-size: 12px; color: #64748b; text-align: center; margin: 0 0 24px 0;">
        Or sign in directly at <a href="{login_url}" style="color: #047857; text-decoration: underline;">{login_url}</a> using your registered email and password.
      </p>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />

      <p style="font-size: 12px; color: #94a3b8; margin: 0; line-height: 1.5;">
        Need assistance setting up your initial campaign or finding matched talent? Reply directly to this email or reach our team at <a href="mailto:{from_email}" style="color: #64748b;">support@influencers.com</a>.
      </p>
    </div>

    <!-- Footer -->
    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center;">
      <p style="font-size: 11px; color: #94a3b8; margin: 0;">
        © 2026 Influencers.com Inc. All rights reserved. This email was sent to {email}.
      </p>
    </div>

  </div>
</body>
</html>"""

    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[email]
        )
        msg.attach_alternative(html_content, "text/html")
        sent = msg.send(fail_silently=False)
        logger.info(f"Successfully sent welcome email to {email} (sent={sent})")
        return True
    except Exception as exc:
        logger.error(f"Failed to dispatch welcome email to {email}: {exc}")
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            raise self.retry(exc=exc)
        return False

