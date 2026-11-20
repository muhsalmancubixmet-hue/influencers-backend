"""
Master URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)


urlpatterns = [
    # Django Admin Site
    path('admin/', admin.site.urls),

    # OpenAPI 3.0 Documentation & Swagger UI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Modular Domain REST APIs (v1)
    path('api/v1/', include('apps.accounts.api.v1.urls')),
    path('api/v1/', include('apps.taxonomies.api.v1.urls')),
    path('api/v1/', include('apps.common.api.v1.urls')),
    path('api/v1/', include('apps.creators.api.v1.urls')),
    path('api/v1/', include('apps.businesses.api.v1.urls')),
    path('api/v1/', include('apps.campaigns.api.v1.urls')),
    path('api/v1/', include('apps.websites.api.v1.urls')),
    path('api/v1/', include('apps.billing.api.v1.urls')),
]

# Media files serving (active in all environments as fallback when S3 is disabled)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

