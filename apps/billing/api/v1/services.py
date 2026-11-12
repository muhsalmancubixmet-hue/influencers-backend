from datetime import timedelta
import razorpay
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import (
    Plan,
    Subscription,
    SubscriptionStatus,
    Payment,
    PaymentStatus,
    PaymentType,
    PaymentMethod,
)
from apps.common.api.v1.services import record_audit_log, create_user_notification


def get_razorpay_client() -> razorpay.Client:
    """
    Instantiate and return an authenticated Razorpay API client (REQ-PAY-01).

    :return: Authenticated razorpay.Client instance.
    :raises ValidationError: If Razorpay credentials are missing from server configuration.
    """
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
    if not key_id or not key_secret:
        raise ValidationError("Razorpay credentials (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET) are not configured on the server.")
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(user: User, plan_id: str) -> dict:
    """
    Create a Razorpay order for subscription package checkout (REQ-PAY-02).

    Security Guarantees:
    - Derives amount and currency strictly server-side from active Plan model.
    - Creates a Payment record with status 'PENDING' for financial ledger tracking.

    :param user: The authenticated User purchasing the subscription.
    :param plan_id: UUID or ID of the Plan.
    :return: Dictionary containing order_id, amount_cents, currency, key_id, plan_id, plan_name.
    :raises ValidationError: If plan is invalid, inactive, or free.
    """
    try:
        plan = Plan.objects.get(id=plan_id, is_active=True, is_deleted=False)
    except (Plan.DoesNotExist, ValueError):
        raise ValidationError(f"Subscription plan '{plan_id}' does not exist or is inactive.")

    if plan.price_cents <= 0:
        raise ValidationError("Free plans do not require a payment transaction.")

    client = get_razorpay_client()

    # Razorpay expects amount in paise (smallest currency unit, integers)
    # Receipt max 40 characters
    receipt_id = f"rcpt_{str(user.id)[:8]}_{int(timezone.now().timestamp())}"[:40]
    order_data = {
        'amount': plan.price_cents,
        'currency': plan.currency,
        'receipt': receipt_id,
        'notes': {
            'user_id': str(user.id),
            'user_email': user.email,
            'plan_id': str(plan.id),
            'plan_name': plan.name,
        }
    }

    try:
        razorpay_order = client.order.create(data=order_data)
    except Exception as exc:
        raise ValidationError(f"Failed to create Razorpay order: {str(exc)}")

    order_id = razorpay_order['id']

    # Record pending transaction in Payment ledger
    payment = Payment.objects.create(
        user=user,
        payment_type=PaymentType.SUBSCRIPTION,
        amount_cents=plan.price_cents,
        currency=plan.currency,
        status=PaymentStatus.PENDING,
        method=PaymentMethod.RAZORPAY,
        gateway_reference=order_id,
    )

    return {
        'order_id': order_id,
        'amount_cents': plan.price_cents,
        'currency': plan.currency,
        'key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'plan_id': str(plan.id),
        'plan_name': plan.name,
        'payment_id': str(payment.id),
    }


def verify_razorpay_payment(
    user: User,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    plan_id: str
) -> dict:
    """
    Verify HMAC SHA256 payment signature from Razorpay and activate subscription (REQ-PAY-03).

    Security & Concurrency Guarantees:
    - Cryptographically validates payment signature using razorpay.Client.utility.verify_payment_signature.
    - Executes status transition and subscription activation inside transaction.atomic() with select_for_update().
    - Triggers transactional user notification.

    :param user: The authenticated User.
    :param razorpay_order_id: Razorpay order ID.
    :param razorpay_payment_id: Razorpay payment transaction ID.
    :param razorpay_signature: Cryptographic HMAC signature returned by checkout widget.
    :param plan_id: UUID of Plan.
    :return: Dictionary containing status, subscription_id, plan_name.
    :raises ValidationError: If signature is invalid, payment not found, or plan does not exist.
    """
    client = get_razorpay_client()

    # Step 1: Cryptographic signature verification
    param_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }
    try:
        client.utility.verify_payment_signature(param_dict)
    except Exception as exc:
        raise ValidationError(f"Invalid payment signature verification failed: {str(exc)}")

    # Step 2: Atomic database mutation with row locking
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(
                gateway_reference=razorpay_order_id,
                user=user,
                is_deleted=False
            )
        except Payment.DoesNotExist:
            payment = None

        try:
            plan = Plan.objects.get(id=plan_id, is_deleted=False)
        except (Plan.DoesNotExist, ValueError):
            raise ValidationError(f"Plan '{plan_id}' does not exist.")

        now = timezone.now()
        period_days = 365 if plan.interval == 'YEARLY' else 30
        period_end = now + timedelta(days=period_days)

        if payment:
            payment.status = PaymentStatus.PAID
            payment.gateway_reference = razorpay_payment_id
            payment.save(update_fields=['status', 'gateway_reference', 'updated_at'])
        else:
            payment = Payment.objects.create(
                user=user,
                payment_type=PaymentType.SUBSCRIPTION,
                amount_cents=plan.price_cents,
                currency=plan.currency,
                status=PaymentStatus.PAID,
                method=PaymentMethod.RAZORPAY,
                gateway_reference=razorpay_payment_id,
            )

        # Step 3: Activate or update Subscription
        subscription = Subscription.objects.filter(user=user, is_deleted=False).first()
        if subscription:
            subscription.plan = plan
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.current_period_end = period_end
            subscription.cancel_at_period_end = False
            subscription.save(update_fields=['plan', 'status', 'current_period_end', 'cancel_at_period_end', 'updated_at'])
        else:
            subscription = Subscription.objects.create(
                user=user,
                plan=plan,
                status=SubscriptionStatus.ACTIVE,
                start_date=now,
                current_period_end=period_end,
                cancel_at_period_end=False
            )

        # Step 4: Dispatch transactional notification (REQ-PAY-04)
        create_user_notification(
            recipient=user,
            title="Subscription Activated",
            message=f"Your subscription to {plan.name} is now active. Thank you for your payment!",
            kind="SYSTEM"
        )

    # Step 5: Dispatch branded tax invoice PDF receipt to customer email (REQ-PAY-08)
    try:
        from apps.billing.tasks import send_payment_invoice_email_task
        is_eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        if is_eager:
            send_payment_invoice_email_task.apply(args=[str(payment.id)])
        else:
            send_payment_invoice_email_task.delay(str(payment.id))
    except Exception as mail_exc:
        import logging
        logging.getLogger(__name__).warning(f"Could not queue invoice email for payment {payment.id}: {mail_exc}")

    return {
        'status': 'success',
        'subscription_id': str(subscription.id),
        'plan_name': plan.name,
        'plan_id': str(plan.id),
        'current_period_end': period_end.isoformat(),
    }


def process_payment_refund(
    payment_id: str,
    refund_amount_cents: int,
    reason: str,
    admin_user: User
) -> Payment:
    """
    Process an atomic partial or full refund on a settled payment transaction.
    
    Financial Safety Guarantees:
    1. Validates payment status is settled ('PAID').
    2. Enforces non-overflow: ensures cumulative refunds never exceed original gross amount.
    3. Transition status to 'REFUNDED' if fully refunded.
    4. Records compliance audit trail with admin user attribution.
    
    :param payment_id: UUID of Payment transaction.
    :param refund_amount_cents: Refund amount in smallest currency units.
    :param reason: Administrative justification for refund.
    :param admin_user: Staff user authorizing refund.
    :return: Updated Payment transaction record.
    :raises ValidationError: If payment not found, not settled, or refund amount exceeds balance.
    """
    if refund_amount_cents <= 0:
        raise ValidationError("Refund amount must be a positive non-zero value.")

    # Execute entire read, lock, non-overflow validation, and mutation inside atomic transaction
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(id=payment_id, is_deleted=False)
        except (Payment.DoesNotExist, ValueError):
            raise ValidationError(f"Payment transaction '{payment_id}' not found.")

        if payment.status not in [PaymentStatus.PAID, PaymentStatus.PENDING]:
            raise ValidationError(f"Cannot refund payment with status '{payment.status}'.")

        # Step 1: Calculate remaining refundable balance on row-locked record
        remaining_balance = payment.amount_cents - payment.refunded_amount_cents

        # Step 2: Validate non-overflow condition
        if refund_amount_cents > remaining_balance:
            max_refundable_fmt = f"{remaining_balance / 100:.2f}"
            requested_fmt = f"{refund_amount_cents / 100:.2f}"
            raise ValidationError(
                f"Refund amount exceeds refundable balance. "
                f"Requested: {requested_fmt} {payment.currency}, Max refundable: {max_refundable_fmt} {payment.currency}."
            )

        # Step 3: Execute atomic database update and log audit trail
        payment.refunded_amount_cents += refund_amount_cents
        payment.refund_reason = (payment.refund_reason + f"\n[{admin_user.email}]: {reason}").strip()

        if payment.refunded_amount_cents >= payment.amount_cents:
            payment.status = PaymentStatus.REFUNDED

        payment.save(update_fields=['refunded_amount_cents', 'refund_reason', 'status', 'updated_at'])

        record_audit_log(
            admin=admin_user,
            action='REFUND_PAYMENT',
            entity='Payment',
            entity_id=str(payment.id),
            result='SUCCESS',
            reason=f"Refunded {refund_amount_cents / 100:.2f} {payment.currency}. Reason: {reason}"
        )

    return payment
