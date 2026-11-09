from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class PlanAudience(models.TextChoices):
    """Target user classification tier for a subscription plan."""
    INFLUENCER = 'INFLUENCER', 'Influencer / Creator'
    BUSINESS = 'BUSINESS', 'Brand / Business'


class BillingInterval(models.TextChoices):
    """Recurring billing cadence period for subscription renewals."""
    MONTHLY = 'MONTHLY', 'Monthly'
    YEARLY = 'YEARLY', 'Yearly'


class Plan(BaseModel):
    """
    Tiered SaaS subscription membership package for creators or brand businesses.
    
    Defines recurring pricing, billing cadence (monthly/yearly), feature flag
    entitlements, and audience scope (influencer vs brand). Protected from hard
    deletion when active subscriptions reference it.
    """

    # Commercial package name (e.g., 'Free Tier', 'Pro Creator', 'Growth Brand', 'Enterprise')
    name = models.CharField(
        max_length=100,
        help_text="Commercial plan title (e.g. 'Pro Creator', 'Enterprise Brand')."
    )

    # Tenant target audience filtering plan visibility in customer portals
    audience = models.CharField(
        max_length=20,
        choices=PlanAudience.choices,
        default=PlanAudience.INFLUENCER,
        db_index=True,
        help_text="Target audience category restricting plan eligibility."
    )

    # Recurring subscription fee in smallest currency unit (paise/cents) to eliminate float rounding
    price_cents = models.PositiveIntegerField(
        default=0,
        help_text="Recurring subscription cost in smallest currency units (e.g. 290000 paise = 2900.00 INR)."
    )

    # ISO 4217 three-letter currency denomination code (e.g. 'INR', 'USD')
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code."
    )

    # Frequency of recurring renewal billing cycles (monthly vs yearly)
    interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
        help_text="Recurring billing cycle interval."
    )

    # Array of feature entitlement string slugs granted to subscribers (e.g. ['custom_domain', 'analytics_pro'])
    features_list = models.JSONField(
        default=list,
        help_text="Array of feature entitlement string slugs granted to subscribers."
    )

    # Operational availability toggle controlling visibility in checkout flows
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether new users can subscribe to this plan."
    )

    class Meta:
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['audience', 'price_cents']

    def __str__(self) -> str:
        """
        String representation of the subscription plan.
        
        :return: Formatted plan name, audience, price, and billing cadence.
        """
        formatted_price = f"{self.price_cents / 100:.2f}"
        return f"{self.name} ({self.get_audience_display()}) - {formatted_price} {self.currency}/{self.interval.lower()}"


class SubscriptionStatus(models.TextChoices):
    """Lifecycle status of a tenant's subscription agreement."""
    ACTIVE = 'ACTIVE', 'Active'
    PAST_DUE = 'PAST_DUE', 'Past Due'
    CANCELED = 'CANCELED', 'Canceled'
    TRIALING = 'TRIALING', 'Trialing'


class Subscription(BaseModel):
    """
    Active recurring SaaS subscription agreement binding a User to a Plan.
    
    Tracks term limits, renewal cycle deadlines, auto-renewal cancellation flags,
    and account standing (active, past-due, trialing, canceled).
    """

    # Subscriber user account holding this subscription entitlement
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        help_text="The tenant user account holding this active or historical subscription."
    )

    # Plan package defining pricing, limits, and granted features (PROTECT prevents deleting active plans)
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='active_subscriptions',
        help_text="The subscription tier package governing platform entitlements."
    )

    # Operational lifecycle standing of the subscription
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
        help_text="Operational lifecycle state (active, trialing, past due, or canceled)."
    )

    # UTC timestamp when the initial subscription cycle commenced
    start_date = models.DateTimeField(
        help_text="Timestamp when this subscription term originally started."
    )

    # UTC expiration timestamp for the current paid billing cycle
    current_period_end = models.DateTimeField(
        db_index=True,
        help_text="Expiration timestamp for the current billing interval."
    )

    # Flag indicating subscriber requested termination at period expiration without mid-term refund
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="True if subscription will automatically terminate at current_period_end without renewal."
    )

    class Meta:
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of the subscription.
        
        :return: Subscriber email, plan title, and status.
        """
        return f"Subscription: {self.user.email} -> {self.plan.name} [{self.status}]"


class PaymentType(models.TextChoices):
    """Business transaction category classification."""
    SUBSCRIPTION = 'SUBSCRIPTION', 'SaaS Subscription Fee'
    CAMPAIGN_ESCROW = 'CAMPAIGN_ESCROW', 'Campaign Escrow Deposit'
    SERVICE_FEE = 'SERVICE_FEE', 'Creator Marketplace Service Fee'
    DOMAIN = 'DOMAIN', 'Custom Domain Registration'


class PaymentStatus(models.TextChoices):
    """Settlement status of a payment transaction."""
    PAID = 'PAID', 'Paid / Settled'
    PENDING = 'PENDING', 'Pending Settlement'
    FAILED = 'FAILED', 'Payment Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class PaymentMethod(models.TextChoices):
    """Payment settlement rails and provider channels."""
    CARD = 'CARD', 'Credit / Debit Card'
    UPI = 'UPI', 'Unified Payments Interface (UPI)'
    NETBANKING = 'NETBANKING', 'Internet Banking'
    WALLET = 'WALLET', 'Digital Wallet'
    STRIPE = 'STRIPE', 'Stripe Payment Gateway'
    RAZORPAY = 'RAZORPAY', 'Razorpay Payment Gateway'


class Payment(BaseModel):
    """
    Immutable financial transaction record across all billing and marketplace touchpoints.
    
    Serves as the unified monetary ledger for SaaS subscriptions, campaign escrow deposits,
    service bookings, and custom domain registrations with support for partial/full refunds.
    """

    # The payer user account originating the monetary transaction
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="The customer or brand user account executing this transaction."
    )

    # Operational business category of the charge
    payment_type = models.CharField(
        max_length=30,
        choices=PaymentType.choices,
        default=PaymentType.SUBSCRIPTION,
        help_text="Business domain classification of the monetary transaction."
    )

    # Total charged gross transaction amount in smallest currency units (cents/paise)
    amount_cents = models.PositiveIntegerField(
        help_text="Gross transaction amount in smallest currency units (e.g. 500000 paise = 5000.00 INR)."
    )

    # ISO 4217 three-letter currency code (e.g. 'INR', 'USD')
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code."
    )

    # Settlement state of the transaction with payment gateway
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        help_text="Settlement status of the transaction (paid, pending, failed, refunded)."
    )

    # Payment processing rail or instrument utilized for checkout
    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.UPI,
        help_text="Payment processing rail or payment instrument."
    )

    # External transaction reference identifier from gateway provider (e.g. 'pay_Ozj89X12B', 'ch_3Mv...')
    gateway_reference = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Unique external transaction reference from payment processor (Razorpay/Stripe)."
    )

    # Direct canonical URL to downloadable PDF tax invoice / payment receipt
    receipt_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Hosted URL to the customer-facing tax invoice receipt."
    )

    # Cumulative refunded amount in smallest currency units (cents/paise)
    refunded_amount_cents = models.PositiveIntegerField(
        default=0,
        help_text="Cumulative refunded portion in smallest currency units (e.g. paise/cents)."
    )

    # Audit note detailing administrative justification for partial or full refund
    refund_reason = models.TextField(
        blank=True,
        help_text="Administrative justification rationale for processing this refund."
    )

    class Meta:
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of the payment transaction.
        
        :return: Transaction ID, payer email, amount, and settlement status.
        """
        formatted_amount = f"{self.amount_cents / 100:.2f}"
        return f"Payment {self.id}: {self.user.email} - {formatted_amount} {self.currency} [{self.status}]"
