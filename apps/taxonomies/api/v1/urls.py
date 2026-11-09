from django.urls import path
from apps.taxonomies.api.v1.views import (
    PublicCategoryListView,
    AdminCategoryListCreateView,
    AdminCategoryDetailView,
    AdminCategoryReorderView,
    PublicLocationListView,
    AdminTaxonomySummaryView,
    AdminLocationListView,
    AdminLocationDetailView
)

urlpatterns = [
    # Public taxonomy endpoints
    path('public/taxonomies/categories/', PublicCategoryListView.as_view(), name='public_categories_list'),
    path('public/taxonomies/locations/', PublicLocationListView.as_view(), name='public_locations_list'),

    # Admin taxonomy endpoints
    path('admin/taxonomies/', AdminTaxonomySummaryView.as_view(), name='admin_taxonomies_summary'),
    path('admin/taxonomies/categories/', AdminCategoryListCreateView.as_view(), name='admin_categories_list_create'),
    path('admin/taxonomies/categories/reorder/', AdminCategoryReorderView.as_view(), name='admin_categories_reorder'),
    path('admin/taxonomies/categories/<uuid:pk>/', AdminCategoryDetailView.as_view(), name='admin_categories_detail'),
    path('admin/taxonomies/locations/', AdminLocationListView.as_view(), name='admin_locations_list'),
    path('admin/taxonomies/locations/<uuid:pk>/', AdminLocationDetailView.as_view(), name='admin_locations_detail'),
]

