from django.urls import path
from apps.billing.api.v1.views import (
    AdminPlanListCreateView,
    AdminPlanDetailView,
    AdminPaymentListView,
    AdminPaymentDetailView,
    AdminPaymentRefundView,
    AdminBillingReportsView,
    PlanListView,
    UserSubscriptionDetailView,
    BillingCheckoutOrderView,
    BillingCheckoutVerifyView,
    BusinessSubscriptionSendReceiptView,
)

urlpatterns = [
    # Customer Subscription & Plans
    path('billing/plans/', PlanListView.as_view(), name='billing_plans_list'),
    path('billing/subscription/', UserSubscriptionDetailView.as_view(), name='billing_user_subscription'),
    path('billing/subscription/send-receipt/', BusinessSubscriptionSendReceiptView.as_view(), name='billing_subscription_send_receipt'),

    # Razorpay Checkout & Verification (REQ-PAY-02, REQ-PAY-03)
    path('billing/checkout/order/', BillingCheckoutOrderView.as_view(), name='billing_checkout_order'),
    path('billing/checkout/verify/', BillingCheckoutVerifyView.as_view(), name='billing_checkout_verify'),

    # Admin Plans management
    path('admin/billing/plans/', AdminPlanListCreateView.as_view(), name='admin_billing_plans_list_create'),
    path('admin/billing/plans/<uuid:pk>/', AdminPlanDetailView.as_view(), name='admin_billing_plans_detail'),

    # Admin Payments Ledger & Refunds
    path('admin/billing/payments/', AdminPaymentListView.as_view(), name='admin_billing_payments_list'),
    path('admin/billing/payments/<uuid:pk>/', AdminPaymentDetailView.as_view(), name='admin_billing_payments_detail'),
    path('admin/billing/payments/<uuid:pk>/refund/', AdminPaymentRefundView.as_view(), name='admin_billing_payments_refund'),

    # Admin Analytics & Revenue Reports
    path('admin/billing/reports/', AdminBillingReportsView.as_view(), name='admin_billing_reports'),
]
