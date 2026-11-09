from django.db import transaction
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.billing.models import Payment, PaymentStatus
from apps.common.api.v1.services import record_audit_log


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
    try:
        payment = Payment.objects.get(id=payment_id, is_deleted=False)
    except (Payment.DoesNotExist, ValueError):
        raise ValidationError(f"Payment transaction '{payment_id}' not found.")

    if payment.status not in [PaymentStatus.PAID, PaymentStatus.PENDING]:
        raise ValidationError(f"Cannot refund payment with status '{payment.status}'.")

    # Step 1: Calculate remaining refundable balance
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
    with transaction.atomic():
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
