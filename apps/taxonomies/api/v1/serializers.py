from rest_framework import serializers
from apps.taxonomies.models import Category, Location, LocationType


class CategorySerializer(serializers.ModelSerializer):
    """Serializer representing taxonomy niche category with creator count metrics."""
    creator_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'order', 'is_active', 'creator_count', 'created_at']
        read_only_fields = ['id', 'creator_count', 'created_at']



class LocationSerializer(serializers.ModelSerializer):
    """Serializer representing hierarchical location node with ancestor path and creator metrics."""
    full_path = serializers.CharField(source='get_full_path', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    creators = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            'id',
            'name',
            'type',
            'parent',
            'parent_name',
            'country_code',
            'latitude',
            'longitude',
            'full_path',
            'is_active',
            'creators'
        ]
        read_only_fields = ['id', 'full_path', 'parent_name', 'creators']

    def get_creators(self, obj) -> int:
        """
        Compute total number of creators associated with this location or its direct children.

        :param obj: Location model instance.
        :return: Integer count of creators.
        """
        from apps.creators.models import CreatorProfile
        direct_count = CreatorProfile.objects.filter(
            primary_location=obj,
            is_deleted=False
        ).count()
        child_ids = list(Location.objects.filter(parent=obj, is_deleted=False).values_list('id', flat=True))
        if child_ids:
            sub_count = CreatorProfile.objects.filter(
                primary_location_id__in=child_ids,
                is_deleted=False
            ).count()
            return direct_count + sub_count
        return direct_count

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.parent:
            ret['parent'] = {
                'id': str(instance.parent.id),
                'name': instance.parent.name
            }
        else:
            ret['parent'] = None
        return ret

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'type' in mutable_data and isinstance(mutable_data['type'], str):
            mutable_data['type'] = mutable_data['type'].upper().strip()

        parent_val = mutable_data.get('parent')
        if parent_val and isinstance(parent_val, str):
            clean_parent = parent_val.strip()
            import uuid
            try:
                uuid.UUID(clean_parent)
            except ValueError:
                parent_obj = Location.objects.filter(name__iexact=clean_parent, is_deleted=False).first()
                if parent_obj:
                    mutable_data['parent'] = str(parent_obj.id)
                    if not mutable_data.get('country_code'):
                        mutable_data['country_code'] = parent_obj.country_code
                else:
                    mutable_data.pop('parent', None)

        if not mutable_data.get('country_code'):
            mutable_data['country_code'] = 'IN'

        return super().to_internal_value(mutable_data)


class CategoryReorderSerializer(serializers.Serializer):
    """Payload contract for bulk category drag-and-drop reordering."""
    orders = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())
    )
