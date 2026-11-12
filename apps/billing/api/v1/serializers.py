from rest_framework import serializers

from apps.billing.models import (
    Plan,
    Subscription,
    Payment,
    PlanAudience,
    BillingInterval,
    PaymentType,
    PaymentStatus
)


class PlanSerializer(serializers.ModelSerializer):
    """Serializer representing tiered SaaS subscription plans."""

    class Meta:
        model = Plan
        fields = [
            'id',
            'name',
            'audience',
            'price_cents',
            'currency',
            'interval',
            'features_list',
            'is_active',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer representing active customer subscription agreements."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id',
            'user',
            'user_email',
            'plan',
            'plan_name',
            'status',
            'start_date',
            'current_period_end',
            'cancel_at_period_end',
            'created_at'
        ]
        read_only_fields = ['id', 'user_email', 'plan_name', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer representing monetary ledger payment transactions."""
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'user',
            'user_email',
            'payment_type',
            'amount_cents',
            'currency',
            'status',
            'method',
            'gateway_reference',
            'receipt_url',
            'refunded_amount_cents',
            'refund_reason',
            'created_at'
        ]
        read_only_fields = ['id', 'user_email', 'refunded_amount_cents', 'refund_reason', 'created_at']


class RefundPaymentSerializer(serializers.Serializer):
    """Payload contract for processing partial or full payment refunds."""
    refund_amount_cents = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(min_length=5)


class CheckoutOrderCreateSerializer(serializers.Serializer):
    """
    Payload contract for initiating a Razorpay checkout order (REQ-PAY-02).
    """
    plan_id = serializers.CharField(
        max_length=64,
        required=True,
        help_text="UUID or identifier of the target Plan to subscribe to."
    )


class CheckoutPaymentVerifySerializer(serializers.Serializer):
    """
    Payload contract for cryptographically verifying a Razorpay checkout payment (REQ-PAY-03).
    """
    razorpay_order_id = serializers.CharField(max_length=128, required=True)
    razorpay_payment_id = serializers.CharField(max_length=128, required=True)
    razorpay_signature = serializers.CharField(max_length=256, required=True)
    plan_id = serializers.CharField(max_length=64, required=True)

