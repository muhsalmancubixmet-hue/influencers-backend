from django.contrib import admin
from apps.taxonomies.models import Category, Location


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Taxonomy discovery verticals."""
    list_display = ('name', 'slug', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    ordering = ('order', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Hierarchical geographic locations."""
    list_display = ('name', 'type', 'parent', 'country_code', 'is_active', 'created_at')
    list_filter = ('type', 'country_code', 'is_active')
    search_fields = ('name', 'country_code')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
