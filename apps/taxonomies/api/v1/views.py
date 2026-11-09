from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.accounts.decorators import require_module_access
from apps.accounts.models import ModuleChoice
from apps.taxonomies.models import Category, Location
from apps.taxonomies.api.v1.serializers import (
    CategorySerializer,
    LocationSerializer,
    CategoryReorderSerializer
)
from apps.taxonomies.api.v1.services import reorder_categories
from apps.common.api.v1.services import record_audit_log


class PublicCategoryListView(APIView):
    """
    Public directory endpoint listing all active categories for frontends.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """
        List active categories ordered by display order and name.
        
        :param request: HTTP request.
        :return: JSON list of active categories.
        """
        categories = Category.objects.filter(is_active=True, is_deleted=False).order_by('order', 'name')
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminCategoryListCreateView(APIView):
    """
    Control panel view for managing categories (listing all, creating new).
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.TAXONOMIES, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        List all categories including inactive ones for administrative management.
        
        :param request: Authenticated HTTP request.
        :return: Paginated categories.
        """
        categories = Category.objects.filter(is_deleted=False).order_by('order', 'name')
        search = request.query_params.get('search', '').strip()
        if search:
            categories = categories.filter(name__icontains=search)

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(categories, request)
        serializer = CategorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @require_module_access(ModuleChoice.TAXONOMIES, 'MANAGE')
    def post(self, request, *args, **kwargs):
        """
        Create a new category.
        
        :param request: Authenticated HTTP request containing category payload.
        :return: Created category details.
        """
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cat = serializer.save()
        record_audit_log(
            admin=request.user,
            action='CREATE_CATEGORY',
            entity='Category',
            entity_id=str(cat.id),
            request=request,
            reason=f"Created category {cat.name}"
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    """
    Retrieve, update, or soft-delete a specific category.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.TAXONOMIES, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        """Retrieve category details."""
        try:
            category = Category.objects.get(id=pk, is_deleted=False)
        except (Category.DoesNotExist, ValueError):
            return Response({'detail': 'Category not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.TAXONOMIES, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        """Update category attributes (name, order, is_active)."""
        try:
            category = Category.objects.get(id=pk, is_deleted=False)
        except (Category.DoesNotExist, ValueError):
            return Response({'detail': 'Category not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        cat = serializer.save()
        record_audit_log(
            admin=request.user,
            action='UPDATE_CATEGORY',
            entity='Category',
            entity_id=str(cat.id),
            request=request,
            reason=f"Updated category {cat.name}"
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.TAXONOMIES, 'MANAGE')
    def delete(self, request, pk, *args, **kwargs):
        """Soft-delete a category."""
        try:
            category = Category.objects.get(id=pk, is_deleted=False)
        except (Category.DoesNotExist, ValueError):
            return Response({'detail': 'Category not found.'}, status=status.HTTP_404_NOT_FOUND)

        category.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCategoryReorderView(APIView):
    """
    Bulk reordering of categories via drag-and-drop UI.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.TAXONOMIES, 'MANAGE')
    def post(self, request, *args, **kwargs):
        """
        Execute atomic order updates.
        
        :param request: Authenticated HTTP request containing array of {id, order}.
        :return: Success response.
        """
        serializer = CategoryReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reorder_categories(serializer.validated_data['orders'])
        return Response({'detail': 'Categories reordered successfully.'}, status=status.HTTP_200_OK)


class PublicLocationListView(APIView):
    """
    Public directory and autocomplete search endpoint for global locations.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """
        Query locations filtered by parent, type, country_code, or autocomplete search query.
        
        :param request: HTTP request with optional query params (search, type, parent_id, country_code).
        :return: Paginated list of matching locations.
        """
        locations = Location.objects.select_related('parent').filter(
            is_active=True,
            is_deleted=False
        ).order_by('name')

        search = request.query_params.get('search', '').strip()
        loc_type = request.query_params.get('type', '').strip()
        parent_id = request.query_params.get('parent_id', '').strip()
        country_code = request.query_params.get('country_code', '').strip()

        if search:
            locations = locations.filter(name__icontains=search)
            if not locations.exists() and len(search) >= 3:
                from apps.taxonomies.api.v1.services import discover_and_cache_external_location
                discovered = discover_and_cache_external_location(search)
                if discovered:
                    locations = Location.objects.select_related('parent').filter(
                        id=discovered.id,
                        is_active=True,
                        is_deleted=False
                    )
        if loc_type:
            locations = locations.filter(type=loc_type.upper())
        if parent_id:
            locations = locations.filter(parent_id=parent_id)
        if country_code:
            locations = locations.filter(country_code=country_code.upper())

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(locations, request)
        serializer = LocationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminTaxonomySummaryView(APIView):
    """
    Combined taxonomy overview endpoint returning active categories and hierarchical locations.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.TAXONOMIES, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        Return categories and top-level locations in a single payload.
        """
        categories = Category.objects.filter(is_deleted=False).order_by('order', 'name')
        locations = Location.objects.filter(is_deleted=False).order_by('name')

        cat_serializer = CategorySerializer(categories, many=True)
        loc_serializer = LocationSerializer(locations, many=True)

        return Response({
            'categories': cat_serializer.data,
            'locations': loc_serializer.data,
            'categories_count': categories.count(),
            'locations_count': locations.count()
        }, status=status.HTTP_200_OK)


class AdminLocationListView(APIView):
    """
    Administrative list and create endpoint for locations hierarchy.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.TAXONOMIES, 'VIEW')
    def get(self, request, *args, **kwargs):
        locations = Location.objects.select_related('parent').filter(is_deleted=False).order_by('name')

        search = request.query_params.get('search', '').strip()
        loc_type = request.query_params.get('type', '').strip()
        if search:
            locations = locations.filter(name__icontains=search)
            if not locations.exists() and len(search) >= 3:
                from apps.taxonomies.api.v1.services import discover_and_cache_external_location
                discovered = discover_and_cache_external_location(search)
                if discovered:
                    locations = Location.objects.select_related('parent').filter(
                        id=discovered.id,
                        is_active=True,
                        is_deleted=False
                    )
        if loc_type:
            locations = locations.filter(type=loc_type.upper())

        paginator = PageNumberPagination()
        paginator.page_size = 100
        page = paginator.paginate_queryset(locations, request)
        serializer = LocationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @require_module_access(ModuleChoice.TAXONOMIES, 'MANAGE')
    def post(self, request, *args, **kwargs):
        serializer = LocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loc = serializer.save()
        record_audit_log(
            admin=request.user,
            action='CREATE_LOCATION',
            entity='Location',
            entity_id=str(loc.id),
            request=request,
            reason=f"Created location {loc.name} ({loc.type})"
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminLocationDetailView(APIView):
    """
    Retrieve, update or delete a location node.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.TAXONOMIES, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            loc = Location.objects.get(id=pk, is_deleted=False)
        except (Location.DoesNotExist, ValueError):
            return Response({'detail': 'Location not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = LocationSerializer(loc)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.TAXONOMIES, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        try:
            loc = Location.objects.get(id=pk, is_deleted=False)
        except (Location.DoesNotExist, ValueError):
            return Response({'detail': 'Location not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = LocationSerializer(loc, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        loc = serializer.save()
        record_audit_log(
            admin=request.user,
            action='UPDATE_LOCATION',
            entity='Location',
            entity_id=str(loc.id),
            request=request,
            reason=f"Updated location {loc.name}"
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.TAXONOMIES, 'MANAGE')
    def delete(self, request, pk, *args, **kwargs):
        try:
            loc = Location.objects.get(id=pk, is_deleted=False)
        except (Location.DoesNotExist, ValueError):
            return Response({'detail': 'Location not found.'}, status=status.HTTP_404_NOT_FOUND)

        loc.soft_delete()
        record_audit_log(
            admin=request.user,
            action='DELETE_LOCATION',
            entity='Location',
            entity_id=str(loc.id),
            request=request,
            reason=f"Soft deleted location {loc.name}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

