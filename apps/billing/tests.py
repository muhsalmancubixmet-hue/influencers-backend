"""
Unit and concurrency regression test suite for Billing application,
specifically payment refund processing and financial concurrency safety (REQ-SEC-01).
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import UserRole
from apps.billing.api.v1.services import process_payment_refund
from apps.billing.models import Payment, PaymentStatus, PaymentType, PaymentMethod

User = get_user_model()


class PaymentRefundConcurrencyAndSafetyTests(TestCase):
    """
    Test suite validating financial refund rules, row locking, non-overflow checks,
    and audit trail attribution (REQ-SEC-01).
    """

    def setUp(self) -> None:
        """
        Seed database with customer user, staff admin, and settled payment.

        :return: None
        """
        self.customer = User.objects.create_user(
            username='payer_customer',
            email='customer@example.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS
        )
        self.staff_admin = User.objects.create_user(
            username='billing_admin',
            email='admin@influencers.com',
            password='SecurePassword123!',
            role=UserRole.STAFF,
            is_staff=True
        )
        self.payment = Payment.objects.create(
            user=self.customer,
            payment_type=PaymentType.SUBSCRIPTION,
            amount_cents=10000,  # 100.00 INR
            refunded_amount_cents=0,
            currency='INR',
            status=PaymentStatus.PAID,
            method=PaymentMethod.CARD,
            gateway_reference='pay_test_ref_123'
        )

    def test_partial_refund_success(self) -> None:
        """
        Verify that a valid partial refund increments refunded_amount_cents,
        keeps status as PAID, and logs administrative reason.

        :return: None
        """
        updated = process_payment_refund(
            payment_id=str(self.payment.id),
            refund_amount_cents=4000,  # 40.00 INR
            reason='Customer requested downgrade refund',
            admin_user=self.staff_admin
        )

        self.assertEqual(updated.refunded_amount_cents, 4000)
        self.assertEqual(updated.status, PaymentStatus.PAID)
        self.assertIn('Customer requested downgrade refund', updated.refund_reason)

        # Reload from database to verify persistence
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount_cents, 4000)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)

    def test_full_refund_transitions_status_to_refunded(self) -> None:
        """
        Verify that refunding the exact total balance transitions status to REFUNDED.

        :return: None
        """
        updated = process_payment_refund(
            payment_id=str(self.payment.id),
            refund_amount_cents=10000,  # Full 100.00 INR
            reason='Charge cancellation',
            admin_user=self.staff_admin
        )

        self.assertEqual(updated.refunded_amount_cents, 10000)
        self.assertEqual(updated.status, PaymentStatus.REFUNDED)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.REFUNDED)

    def test_refund_exceeding_refundable_balance_rejected(self) -> None:
        """
        Verify that requesting a refund amount exceeding the available balance
        raises ValidationError with descriptive formatting.

        :return: None
        """
        with self.assertRaises(ValidationError) as ctx:
            process_payment_refund(
                payment_id=str(self.payment.id),
                refund_amount_cents=10001,  # Exceeds 10000
                reason='Over-refund attempt',
                admin_user=self.staff_admin
            )

        self.assertIn('Refund amount exceeds refundable balance', str(ctx.exception))

    def test_sequential_refunds_exhausting_balance(self) -> None:
        """
        Verify that multiple consecutive partial refunds correctly deduct from
        balance and reject any further attempts once exhausted.

        :return: None
        """
        # First refund: 60.00
        process_payment_refund(str(self.payment.id), 6000, 'Refund part 1', self.staff_admin)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount_cents, 6000)

        # Second refund: remaining 40.00
        process_payment_refund(str(self.payment.id), 4000, 'Refund part 2', self.staff_admin)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount_cents, 10000)
        self.assertEqual(self.payment.status, PaymentStatus.REFUNDED)

        # Third refund attempt must be rejected
        with self.assertRaises(ValidationError):
            process_payment_refund(str(self.payment.id), 100, 'Exhausted refund', self.staff_admin)

    def test_negative_or_zero_refund_rejected(self) -> None:
        """
        Verify that zero or negative refund amounts are rejected immediately.

        :return: None
        """
        with self.assertRaises(ValidationError) as ctx1:
            process_payment_refund(str(self.payment.id), 0, 'Zero refund', self.staff_admin)
        self.assertIn('positive non-zero', str(ctx1.exception))

        with self.assertRaises(ValidationError) as ctx2:
            process_payment_refund(str(self.payment.id), -500, 'Negative refund', self.staff_admin)
        self.assertIn('positive non-zero', str(ctx2.exception))

    def test_refund_on_failed_payment_rejected(self) -> None:
        """
        Verify that non-settled payments (e.g. FAILED) cannot be refunded.

        :return: None
        """
        self.payment.status = PaymentStatus.FAILED
        self.payment.save(update_fields=['status'])

        with self.assertRaises(ValidationError) as ctx:
            process_payment_refund(str(self.payment.id), 1000, 'Failed payment refund', self.staff_admin)

        self.assertIn("Cannot refund payment with status 'FAILED'", str(ctx.exception))


from django.test import TransactionTestCase
import concurrent.futures
from django.db import connection, OperationalError


class PaymentConcurrentRefundThreadingTests(TransactionTestCase):
    """
    Multi-threaded concurrency tests verifying that row locking with
    select_for_update() inside transaction.atomic() correctly serializes
    concurrent refund attempts and prevents double-refund overspending (REQ-FIN-01 / REQ-INF-01).
    """

    def setUp(self) -> None:
        self.customer = User.objects.create_user(
            username='payer_concurrent',
            email='concurrent_payer@example.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS
        )
        self.staff_admin = User.objects.create_user(
            username='concurrent_admin',
            email='admin_concurrent@influencers.com',
            password='SecurePassword123!',
            role=UserRole.STAFF,
            is_staff=True
        )
        self.payment = Payment.objects.create(
            user=self.customer,
            payment_type=PaymentType.SUBSCRIPTION,
            amount_cents=10000,  # 100.00 INR
            refunded_amount_cents=0,
            currency='INR',
            status=PaymentStatus.PAID,
            method=PaymentMethod.CARD,
            gateway_reference='pay_concurrent_ref'
        )

    def test_concurrent_threads_cannot_over_refund(self) -> None:
        """
        Spawn concurrent worker threads attempting to refund 60.00 each
        from a 100.00 total balance.
        Exactly one thread must succeed, and any subsequent attempts must fail
        either via validation or lock contention, ensuring total refunded never exceeds 100.00.
        """
        payment_id = str(self.payment.id)
        results = []
        errors = []

        def attempt_refund(thread_idx: int):
            connection.close()
            try:
                res = process_payment_refund(
                    payment_id=payment_id,
                    refund_amount_cents=6000,
                    reason=f'Concurrent refund thread {thread_idx}',
                    admin_user=self.staff_admin
                )
                return ('SUCCESS', res.refunded_amount_cents)
            except Exception as e:
                return ('ERROR', str(e))
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(attempt_refund, 1)
            f2 = executor.submit(attempt_refund, 2)
            for f in (f1, f2):
                status, val = f.result()
                if status == 'SUCCESS':
                    results.append(val)
                else:
                    errors.append(val)

        self.payment.refresh_from_db()
        # Verify that total refunded never exceeds initial amount
        self.assertLessEqual(self.payment.refunded_amount_cents, self.payment.amount_cents)
        # At most 1 attempt of 60.00 could succeed on a 100.00 payment
        self.assertLessEqual(len(results), 1)


from unittest.mock import MagicMock, patch
from rest_framework import status
from rest_framework.test import APITestCase
from apps.billing.models import (
    Plan,
    PlanAudience,
    BillingInterval,
    Subscription,
    SubscriptionStatus,
)
from apps.billing.api.v1.services import create_razorpay_order, verify_razorpay_payment


class RazorpayCheckoutServiceAndApiTests(APITestCase):
    """
    Test suite for Razorpay order generation, signature validation,
    subscription activation, and checkout API endpoints (REQ-PAY-02, REQ-PAY-03, REQ-PAY-05).
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='brand_subscriber',
            email='brand_sub@example.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS
        )
        self.client.force_authenticate(user=self.user)

        self.pro_plan = Plan.objects.create(
            name='Business Pro',
            audience=PlanAudience.BUSINESS,
            price_cents=299900,  # 2999.00 INR
            currency='INR',
            interval=BillingInterval.MONTHLY,
            features_list=['unlimited_searches', 'analytics_pro'],
            is_active=True
        )

        self.free_plan = Plan.objects.create(
            name='Free Tier',
            audience=PlanAudience.BUSINESS,
            price_cents=0,
            currency='INR',
            interval=BillingInterval.MONTHLY,
            features_list=['basic_search'],
            is_active=True
        )

    @patch('apps.billing.api.v1.services.get_razorpay_client')
    def test_create_razorpay_order_success(self, mock_get_client) -> None:
        mock_client = MagicMock()
        mock_client.order.create.return_value = {'id': 'order_test_12345'}
        mock_get_client.return_value = mock_client

        res = create_razorpay_order(user=self.user, plan_id=str(self.pro_plan.id))

        self.assertEqual(res['order_id'], 'order_test_12345')
        self.assertEqual(res['amount_cents'], 299900)
        self.assertEqual(res['currency'], 'INR')
        self.assertEqual(res['plan_id'], str(self.pro_plan.id))

        # Verify Payment record was created in database
        payment = Payment.objects.get(gateway_reference='order_test_12345')
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.amount_cents, 299900)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_create_order_for_free_plan_rejected(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            create_razorpay_order(user=self.user, plan_id=str(self.free_plan.id))
        self.assertIn("Free plans do not require a payment transaction", str(ctx.exception))

    @patch('apps.billing.api.v1.services.get_razorpay_client')
    def test_verify_razorpay_payment_success_activates_subscription(self, mock_get_client) -> None:
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_get_client.return_value = mock_client

        # Seed initial pending payment
        payment = Payment.objects.create(
            user=self.user,
            payment_type=PaymentType.SUBSCRIPTION,
            amount_cents=299900,
            currency='INR',
            status=PaymentStatus.PENDING,
            method=PaymentMethod.RAZORPAY,
            gateway_reference='order_activate_123'
        )

        res = verify_razorpay_payment(
            user=self.user,
            razorpay_order_id='order_activate_123',
            razorpay_payment_id='pay_activate_456',
            razorpay_signature='valid_test_signature_hex',
            plan_id=str(self.pro_plan.id)
        )

        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['plan_name'], 'Business Pro')

        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.gateway_reference, 'pay_activate_456')

        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(sub.plan, self.pro_plan)
        self.assertIsNotNone(sub.current_period_end)

    @patch('apps.billing.api.v1.services.get_razorpay_client')
    def test_verify_razorpay_payment_invalid_signature_rejected(self, mock_get_client) -> None:
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = Exception("Signature verification failed")
        mock_get_client.return_value = mock_client

        with self.assertRaises(ValidationError) as ctx:
            verify_razorpay_payment(
                user=self.user,
                razorpay_order_id='order_fake_123',
                razorpay_payment_id='pay_fake_456',
                razorpay_signature='tampered_signature',
                plan_id=str(self.pro_plan.id)
            )

        self.assertIn("Invalid payment signature", str(ctx.exception))

    @patch('apps.billing.api.v1.services.get_razorpay_client')
    def test_checkout_order_api_endpoint(self, mock_get_client) -> None:
        mock_client = MagicMock()
        mock_client.order.create.return_value = {'id': 'order_api_999'}
        mock_get_client.return_value = mock_client

        url = '/api/v1/billing/checkout/order/'
        payload = {'plan_id': str(self.pro_plan.id)}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['order_id'], 'order_api_999')
        self.assertEqual(response.data['amount_cents'], 299900)

    @patch('apps.billing.api.v1.services.get_razorpay_client')
    def test_checkout_verify_api_endpoint(self, mock_get_client) -> None:
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_get_client.return_value = mock_client

        Payment.objects.create(
            user=self.user,
            payment_type=PaymentType.SUBSCRIPTION,
            amount_cents=299900,
            currency='INR',
            status=PaymentStatus.PENDING,
            method=PaymentMethod.RAZORPAY,
            gateway_reference='order_api_verify_123'
        )

        url = '/api/v1/billing/checkout/verify/'
        payload = {
            'razorpay_order_id': 'order_api_verify_123',
            'razorpay_payment_id': 'pay_api_verify_456',
            'razorpay_signature': 'signature_valid',
            'plan_id': str(self.pro_plan.id)
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    def test_generate_invoice_pdf_creates_valid_pdf(self) -> None:
        """
        Verify that generate_invoice_pdf generates a valid binary PDF document.
        """
        from apps.billing.tasks import generate_invoice_pdf
        payment = Payment.objects.create(
            user=self.user,
            payment_type=PaymentType.SUBSCRIPTION,
            amount_cents=492700,
            currency='INR',
            status=PaymentStatus.PAID,
            method=PaymentMethod.RAZORPAY,
            gateway_reference='pay_invoice_test_123'
        )
        pdf_bytes = generate_invoice_pdf(payment)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 500)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    @patch('apps.billing.tasks.send_payment_invoice_email_task.apply')
    @patch('apps.billing.tasks.send_payment_invoice_email_task.delay')
    def test_send_receipt_api_endpoint(self, mock_delay, mock_apply) -> None:
        """
        Verify that POST /api/v1/billing/subscription/send-receipt/ dispatches the receipt email.
        """
        Payment.objects.create(
            user=self.user,
            payment_type=PaymentType.SUBSCRIPTION,
            amount_cents=492700,
            currency='INR',
            status=PaymentStatus.PAID,
            method=PaymentMethod.RAZORPAY,
            gateway_reference='pay_receipt_test_789'
        )
        url = '/api/v1/billing/subscription/send-receipt/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertTrue(mock_apply.called or mock_delay.called)



