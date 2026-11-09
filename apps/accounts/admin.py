from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.accounts.models import (
    User,
    StaffProfile,
    RoleTemplate,
    RolePermission,
    StaffInvitation
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Administrative representation for platform User accounts."""
    list_display = ('email', 'username', 'role', 'first_name', 'last_name', 'is_active', 'is_staff', 'created_at')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Tenancy & Roles', {'fields': ('role',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    """Administrative profile governing staff member access."""
    list_display = ('user', 'role_template', 'is_active', 'last_active_at', 'created_at')
    list_filter = ('is_active', 'role_template')
    search_fields = ('user__email', 'user__username', 'role_template__name')
    readonly_fields = ('created_at', 'updated_at')


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 1


@admin.register(RoleTemplate)
class RoleTemplateAdmin(admin.ModelAdmin):
    """Administrative role archetype governance."""
    list_display = ('name', 'is_system_role', 'created_at')
    list_filter = ('is_system_role',)
    search_fields = ('name', 'description')
    inlines = [RolePermissionInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Granular module access tier mapping."""
    list_display = ('role_template', 'module', 'access_level', 'created_at')
    list_filter = ('module', 'access_level', 'role_template')
    search_fields = ('role_template__name', 'module')


@admin.register(StaffInvitation)
class StaffInvitationAdmin(admin.ModelAdmin):
    """Pending administrative onboarding invitations."""
    list_display = ('email', 'role_template', 'invited_by', 'is_accepted', 'expires_at', 'created_at')
    list_filter = ('is_accepted', 'role_template')
    search_fields = ('email', 'role_template__name', 'invited_by__email')
    readonly_fields = ('token', 'created_at', 'updated_at')
