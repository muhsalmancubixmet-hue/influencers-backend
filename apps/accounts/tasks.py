"""
Asynchronous Celery tasks for account lifecycle events, notifications, and verification emails.
Adheres strictly to BACKEND_ENGINEERING_RULES.md standards with typed signatures and full docstrings.
"""
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(
    self,
    user_id: str,
    email: str,
    verification_token: str,
    temporary_password: str = ""
) -> bool:
    """
    Dispatch a branded HTML & text welcome/magic link email to a newly registered creator.

    The email contains:
    1. A one-click direct login 'Log In to Dashboard' button linked to the creator portal.
    2. The creator's registered email address and generated temporary password.
    3. An instant account revocation button if the registration was unexpected.

    :param self: Celery task execution instance for retry control.
    :param user_id: UUID string primary key of the User account.
    :param email: Recipient electronic mail address of the creator.
    :param verification_token: Cryptographically signed token for verification and authentication.
    :param temporary_password: Plaintext temporary password generated at registration.
    :return: True if the email dispatch succeeded.
    :raises Exception: Propagates mail dispatch errors to Celery retry handler.
    """
    # -------------------------------------------------------------------------
    # STEP 1: Determine Portal Base URLs and action targets
    # -------------------------------------------------------------------------
    frontend_base = getattr(settings, 'CREATOR_HUB_URL', 'http://localhost:8080').rstrip('/')
    magic_link_url = f"{frontend_base}/verify-email?token={verification_token}"
    revoke_url = f"{frontend_base}/revoke?token={verification_token}"

    subject = "Welcome to Influencers.com - Log In to Your Dashboard"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '"Influencers.com" <support@influencers.com>')
    if '<' in from_email and not from_email.startswith('"'):
        name, addr = from_email.split('<', 1)
        name = name.strip()
        if '.' in name:
            from_email = f'"{name}" <{addr}'

    # -------------------------------------------------------------------------
    # STEP 2: Prepare template rendering context
    # -------------------------------------------------------------------------
    context = {
        'user_id': user_id,
        'email': email,
        'password': temporary_password,
        'magic_link_url': magic_link_url,
        'revoke_url': revoke_url,
    }

    try:
        # Render rich HTML email template matching the approved visual mockup
        html_content = render_to_string('emails/welcome_magic_link.html', context)
    except Exception as render_err:
        logger.warning(f"Failed to render welcome_magic_link.html template: {render_err}. Falling back to inline HTML.")
        html_content = f"""
        <html><body>
        <h2>Welcome to Influencers.com</h2>
        <p>Your creator account is ready. Log in to your dashboard below:</p>
        <p><a href="{magic_link_url}" style="background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;">Log In to Dashboard</a></p>
        <p>Email: {email}<br/>Password: {temporary_password}</p>
        </body></html>
        """

    try:
        # Render plain text alternative
        text_content = render_to_string('emails/welcome_magic_link.txt', context)
    except Exception:
        text_content = strip_tags(html_content)

    # -------------------------------------------------------------------------
    # STEP 3: Dispatch multi-part email
    # -------------------------------------------------------------------------
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        logger.info(f"Welcome magic link email successfully dispatched to {email} (User {user_id})")
        return True

    except Exception as exc:
        logger.error(f"Failed to dispatch welcome email to {email}: {exc}")
        # When running in asynchronous Celery worker mode, retry with exponential backoff
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            raise self.retry(exc=exc)
        raise exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_staff_invitation_email_task(
    self,
    email: str,
    invitation_token: str,
    role_name: str = "Admin Staff",
    invited_by_name: str = "A Super Admin",
    temporary_password: str = ""
) -> bool:
    """
    Dispatch an onboarding invitation email to a prospective administrative team member.

    Follows the unified Influencers.com design standard (identical to creator registration email),
    featuring:
    1. Branded header with logo mark.
    2. Welcome banner and personalized inviter greeting.
    3. Dedicated Account Credentials container displaying email, role, and temporary password.
    4. Primary action button: 'Log In to Dashboard'.
    5. Direct 'Revoke Registration' link/button if the invitation is unintended.

    :param self: Celery task execution instance for retry control.
    :param email: Electronic mail address of the invited staff member.
    :param invitation_token: Unguessable UUID token identifying the StaffInvitation record.
    :param role_name: Name of the assigned operational role template (e.g. 'Support', 'Manager').
    :param invited_by_name: Display name or email of the inviting administrator.
    :param temporary_password: Plaintext temporary password generated for initial onboarding.
    :return: True if the invitation email was successfully dispatched.
    :raises Exception: Propagates mail dispatch errors to the Celery retry handler.
    """
    # -------------------------------------------------------------------------
    # STEP 1: Determine Control Panel Base URLs and action targets
    # -------------------------------------------------------------------------
    admin_base = getattr(settings, 'ADMIN_PORTAL_URL', 'http://localhost:8081').rstrip('/')
    invite_url = f"{admin_base}/invite/accept?token={invitation_token}"
    revoke_url = f"{admin_base}/invite/accept?token={invitation_token}&action=revoke"

    subject = f"Welcome to Influencers.com - Log In to Your Dashboard"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '"Influencers.com" <support@influencers.com>')
    if '<' in from_email and not from_email.startswith('"'):
        name, addr = from_email.split('<', 1)
        name = name.strip()
        if '.' in name:
            from_email = f'"{name}" <{addr}'

    # -------------------------------------------------------------------------
    # STEP 2: Prepare template rendering context
    # -------------------------------------------------------------------------
    context = {
        'email': email,
        'role_name': role_name,
        'invited_by': invited_by_name,
        'temporary_password': temporary_password,
        'invite_url': invite_url,
        'revoke_url': revoke_url,
    }

    try:
        html_content = render_to_string('emails/staff_invitation.html', context)
    except Exception as render_err:
        logger.warning(f"Template rendering failed ({render_err}). Falling back to inline markup.")
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Welcome to Influencers.com - Admin Console</title>
          <style>
            body {{ margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155; -webkit-font-smoothing: antialiased; }}
            .wrapper {{ width: 100%; background-color: #f1f5f9; padding: 30px 10px; }}
            .container {{ max-width: 580px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06); }}
            .header {{ background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 50%, #3b82f6 100%); padding: 38px 30px; text-align: center; color: #ffffff; }}
            .brand-tag {{ font-size: 13px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase; opacity: 0.9; margin-bottom: 8px; }}
            .header-title {{ font-size: 26px; font-weight: 700; margin: 0; letter-spacing: -0.5px; }}
            .content {{ padding: 36px 36px 28px 36px; background-color: #ffffff; }}
            .greeting {{ font-size: 19px; font-weight: 700; color: #0f172a; margin-bottom: 16px; }}
            .body-text {{ font-size: 14.5px; line-height: 1.65; color: #475569; margin: 0 0 16px 0; }}
            .btn-container {{ text-align: center; margin: 28px 0 24px 0; }}
            .btn-primary {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; text-decoration: none; font-size: 15px; font-weight: 700; padding: 13px 32px; border-radius: 6px; box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35); }}
            .credentials-box {{ text-align: center; font-size: 14.5px; line-height: 1.8; color: #334155; margin-bottom: 24px; }}
            .credentials-box a {{ color: #2563eb; text-decoration: underline; }}
            .credentials-box code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-weight: 700; color: #0f172a; background-color: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
            .divider {{ border: 0; border-top: 1px dashed #cbd5e1; margin: 28px 0; }}
            .revoke-section {{ text-align: center; margin-bottom: 12px; }}
            .revoke-text {{ font-size: 13px; line-height: 1.5; color: #64748b; margin-bottom: 16px; }}
            .btn-revoke {{ display: inline-block; background-color: #ef4444; color: #ffffff !important; text-decoration: none; font-size: 13px; font-weight: 700; padding: 10px 22px; border-radius: 6px; }}
            .footer {{ background-color: #f8fafc; border-top: 1px solid #f1f5f9; padding: 26px 20px; text-align: center; font-size: 12px; line-height: 1.7; color: #64748b; }}
          </style>
        </head>
        <body>
          <div class="wrapper">
            <div class="container">
              <div class="header">
                <div class="brand-tag">INFLUENCERS.COM</div>
                <h1 class="header-title">Welcome to the Team</h1>
              </div>
              <div class="content">
                <div class="greeting">Hello,</div>
                <p class="body-text">Welcome to our company! {invited_by_name} has invited you to join the Influencers.com SaaS Management Console with the <strong>{role_name}</strong> role.</p>
                <p class="body-text">You can securely log in to your dashboard by clicking the button below:</p>
                <div class="btn-container">
                  <a href="{invite_url}" class="btn-primary" target="_blank">Log In to Dashboard</a>
                </div>
                <div class="credentials-box">
                  <div><strong>Email:</strong> <a href="mailto:{email}">{email}</a></div>
                  <div><strong>Role:</strong> <code>{role_name}</code></div>
                  {"<div><strong>Password:</strong> <code>" + temporary_password + "</code></div>" if temporary_password else ""}
                </div>
                <hr class="divider" />
                <div class="revoke-section">
                  <p class="revoke-text">If you did not expect this or believe it was a mistake, please revoke this registration instantly:</p>
                  <a href="{revoke_url}" class="btn-revoke" target="_blank">It's Not Me - Revoke</a>
                </div>
              </div>
              <div class="footer">
                <div>&copy; 2026 Influencers.com Inc.. All rights reserved.</div>
                <div>Need help? Contact <a href="mailto:support@influencers.com">support@influencers.com</a> | Visit <a href="https://influencers.com">https://influencers.com</a></div>
                <div style="margin-top: 4px; font-size: 11px; color: #94a3b8;">This is an automated transactional message. Please do not reply directly.</div>
              </div>
            </div>
          </div>
        </body>
        </html>
        """

    try:
        text_content = render_to_string('emails/staff_invitation.txt', context)
    except Exception:
        text_content = (
            f"Welcome to the Influencers.com Team\n\n"
            f"{invited_by_name} has invited you to join the Influencers.com Management Console with the {role_name} role.\n\n"
            f"Account Credentials:\n"
            f"- Email: {email}\n"
            f"- Role: {role_name}\n"
            f"{f'- Initial Password: {temporary_password}' if temporary_password else ''}\n\n"
            f"Log In to Dashboard:\n{invite_url}\n\n"
            f"Revoke Registration:\n{revoke_url}\n\n"
            f"This link expires in 7 days."
        )

    # -------------------------------------------------------------------------
    # STEP 3: Dispatch email via configured transport
    # -------------------------------------------------------------------------
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        logger.info(f"Staff onboarding invitation email dispatched to {email} (Role: {role_name})")
        return True

    except Exception as exc:
        logger.error(f"Failed to dispatch staff invitation email to {email}: {exc}")
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            raise self.retry(exc=exc)
        raise exc
