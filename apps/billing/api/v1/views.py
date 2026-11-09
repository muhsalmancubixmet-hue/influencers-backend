from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import ValidationError

from apps.accounts.decorators import require_module_access
from apps.accounts.models import ModuleChoice
from apps.billing.models import Plan, Payment, Subscription
from apps.billing.api.v1.serializers import (
    PlanSerializer,
    PaymentSerializer,
    SubscriptionSerializer,
    RefundPaymentSerializer
)
from apps.billing.api.v1.services import process_payment_refund


class AdminPlanListCreateView(APIView):
    """Control panel view listing all subscription plans and creating new packages."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SUBSCRIPTIONS, 'VIEW')
    def get(self, request, *args, **kwargs):
        plans = Plan.objects.filter(is_deleted=False).order_by('audience', 'price_cents')
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SUBSCRIPTIONS, 'MANAGE')
    def post(self, request, *args, **kwargs):
        serializer = PlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminPlanDetailView(APIView):
    """Update or archive a subscription plan package."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SUBSCRIPTIONS, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            plan = Plan.objects.get(id=pk, is_deleted=False)
        except (Plan.DoesNotExist, ValueError):
            return Response({'detail': 'Plan not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlanSerializer(plan)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SUBSCRIPTIONS, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        try:
            plan = Plan.objects.get(id=pk, is_deleted=False)
        except (Plan.DoesNotExist, ValueError):
            return Response({'detail': 'Plan not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlanSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminPaymentListView(APIView):
    """Control panel monetary transaction ledger view."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.PAYMENTS, 'VIEW')
    def get(self, request, *args, **kwargs):
        payments = Payment.objects.select_related('user').filter(is_deleted=False).order_by('-created_at')

        status_param = request.query_params.get('status')
        type_param = request.query_params.get('type')
        search = request.query_params.get('search', '').strip()

        if status_param:
            payments = payments.filter(status=status_param.upper())
        if type_param:
            payments = payments.filter(payment_type=type_param.upper())
        if search:
            payments = payments.filter(
                user__email__icontains=search
            ) | payments.filter(
                gateway_reference__icontains=search
            )

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(payments, request)
        serializer = PaymentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminPaymentDetailView(APIView):
    """Inspect payment transaction details."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.PAYMENTS, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            payment = Payment.objects.select_related('user').get(id=pk, is_deleted=False)
        except (Payment.DoesNotExist, ValueError):
            return Response({'detail': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminPaymentRefundView(APIView):
    """Process atomic refund with balance overflow validation."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.PAYMENTS, 'MANAGE')
    def post(self, request, pk, *args, **kwargs):
        serializer = RefundPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = process_payment_refund(
                payment_id=str(pk),
                refund_amount_cents=serializer.validated_data['refund_amount_cents'],
                reason=serializer.validated_data['reason'],
                admin_user=request.user
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = PaymentSerializer(payment)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class AdminBillingReportsView(APIView):
    """
    Administrative analytics report endpoint aggregating MRR, plan distribution,
    and revenue growth trajectories.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.PAYMENTS, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        Aggregate revenue streams, subscription tiers, and transaction trends.

        :param request: Authenticated administrative HTTP request.
        :return: JSON response with monthly trends, plan breakdowns, and account type totals.
        """
        from datetime import datetime, timedelta
        from django.utils import timezone
        from django.db.models import Sum, Count

        now = timezone.now()

        # -------------------------------------------------------------
        # 1. 6-Month Monthly Revenue Trends
        # -------------------------------------------------------------
        revenue_trend = []
        for i in range(5, -1, -1):
            target_date = now - timedelta(days=i * 30)
            month_label = target_date.strftime("%b")
            start_m = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if target_date.month == 12:
                end_m = target_date.replace(year=target_date.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                end_m = target_date.replace(month=target_date.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

            # Sum succeeded payments in this window
            sub_rev = Payment.objects.filter(
                status='SUCCEEDED',
                payment_type='SUBSCRIPTION',
                created_at__gte=start_m,
                created_at__lt=end_m,
                is_deleted=False
            ).aggregate(total=Sum('amount_cents'))['total'] or 0

            svc_rev = Payment.objects.filter(
                status='SUCCEEDED',
                payment_type__in=['SERVICE_ESCROW', 'CAMPAIGN_ESCROW'],
                created_at__gte=start_m,
                created_at__lt=end_m,
                is_deleted=False
            ).aggregate(total=Sum('amount_cents'))['total'] or 0

            ref_rev = Payment.objects.filter(
                status='REFUNDED',
                created_at__gte=start_m,
                created_at__lt=end_m,
                is_deleted=False
            ).aggregate(total=Sum('refunded_amount_cents'))['total'] or 0

            revenue_trend.append({
                'month': month_label,
                'subscription': sub_rev,
                'services': svc_rev,
                'refunds': ref_rev,
            })

        # -------------------------------------------------------------
        # 2. Revenue by Active Plan
        # -------------------------------------------------------------
        revenue_by_plan = []
        plans = Plan.objects.filter(is_deleted=False)
        for p in plans:
            sub_count = p.subscriptions.filter(status='ACTIVE', is_deleted=False).count()
            monthly_val = sub_count * p.price_cents
            if monthly_val > 0 or sub_count > 0:
                revenue_by_plan.append({
                    'name': f"{p.audience.title()} {p.name}",
                    'value': monthly_val or p.price_cents
                })

        # -------------------------------------------------------------
        # 3. Revenue by Tenant Account Type (Influencer vs Business)
        # -------------------------------------------------------------
        inf_rev = Payment.objects.filter(
            status='SUCCEEDED',
            user__role='CREATOR',
            is_deleted=False
        ).aggregate(total=Sum('amount_cents'))['total'] or 0

        biz_rev = Payment.objects.filter(
            status='SUCCEEDED',
            user__role='BUSINESS',
            is_deleted=False
        ).aggregate(total=Sum('amount_cents'))['total'] or 0

        revenue_by_account_type = [
            {'name': 'Influencers', 'value': inf_rev},
            {'name': 'Businesses', 'value': biz_rev},
        ]

        # -------------------------------------------------------------
        # 4. Global Summary Totals
        # -------------------------------------------------------------
        total_rev = Payment.objects.filter(
            status='SUCCEEDED',
            is_deleted=False
        ).aggregate(total=Sum('amount_cents'))['total'] or 0

        total_refunded = Payment.objects.filter(
            is_deleted=False
        ).aggregate(total=Sum('refunded_amount_cents'))['total'] or 0

        active_subs = Subscription.objects.filter(
            status='ACTIVE',
            is_deleted=False
        ).count()

        payload = {
            'revenueTrend': revenue_trend,
            'revenueByPlan': revenue_by_plan,
            'revenueByAccountType': revenue_by_account_type,
            'totalRevenue': total_rev,
            'totalRefunds': total_refunded,
            'netRevenue': max(0, total_rev - total_refunded),
            'activeSubscribers': active_subs,
        }

        return Response(payload, status=status.HTTP_200_OK)
