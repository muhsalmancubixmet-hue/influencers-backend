from django.contrib import admin
from apps.billing.models import Plan, Subscription, Payment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'audience', 'price_cents', 'currency', 'interval', 'is_active', 'created_at')
    list_filter = ('audience', 'interval', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'start_date', 'current_period_end', 'cancel_at_period_end', 'created_at')
    list_filter = ('status', 'cancel_at_period_end', 'plan__audience')
    search_fields = ('user__email', 'plan__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'payment_type', 'amount_cents', 'currency', 'status', 'method', 'gateway_reference', 'created_at')
    list_filter = ('payment_type', 'status', 'method')
    search_fields = ('id', 'user__email', 'gateway_reference')
    readonly_fields = ('created_at', 'updated_at')
