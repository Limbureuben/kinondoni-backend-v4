# serializers.py
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import *

class ReportReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportReply
        fields = ['id', 'report', 'sender', 'message', 'created_at']



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_staff']
        
# class StreetSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Street
#         fields = ['id', 'name']

        
# class UserStreetSerializer(serializers.ModelSerializer):
#     street = StreetSerializer()  # ← This will return { id, name }

#     class Meta:
#         model = CustomUser
#         fields = ['id', 'username', 'email', 'role', 'ward', 'street']


class StreetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Street
        fields = ['name']

class NewUserStreetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role', 'ward', 'street']

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Replace `street` ID with object
        if instance.street:
            rep['street'] = {
                'id': instance.street.id,
                'name': instance.street.name
            }
        else:
            rep['street'] = None

        return rep
    
# serializers.py
class SimpleStreetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Street
        fields = ['id', 'name']



class ProfileImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['profile_image']

class ForwardedBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForwardedBooking
        fields = ['booking', 'ward_executive_description', 'forwarded_by']

# serializers.py
class UserProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'role', 'profile_image']

    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.profile_image and hasattr(obj.profile_image, 'url'):
            return request.build_absolute_uri(obj.profile_image.url)
        return None


class OpenSpaceBookingSerializer(serializers.ModelSerializer):
    space_name = serializers.SerializerMethodField()

    class Meta:
        model = OpenSpaceBooking
        fields = '__all__'
        read_only_fields = ['user', 'username']
        extra_kwargs = {
            'space': {'required': False}
        }

    def get_space_name(self, obj):
        return obj.space.name if obj.space else None

    def validate(self, attrs):
        start_date = attrs.get('startdate')
        end_date = attrs.get('enddate')
        minimum_start_date = timezone.localdate() + timedelta(days=4)

        if start_date and start_date < minimum_start_date:
            raise serializers.ValidationError({
                'startdate': 'The start date must be at least four days from today.'
            })
        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError({
                'enddate': 'The end date must be after the start date.'
            })

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        space_id = request.data.get('space_id') if request else None

        if not space_id:
            raise serializers.ValidationError({"space": "This field is required."})

        with transaction.atomic():
            try:
                space = OpenSpace.objects.select_for_update().get(id=space_id)
            except OpenSpace.DoesNotExist:
                raise serializers.ValidationError({"space": "Open space not found."})

            if space.status == 'unavailable':
                raise serializers.ValidationError({
                    "space": "This open space has already been booked and is unavailable."
                })

            validated_data.pop('space', None)
            validated_data['username'] = request.user.username
            validated_data['user'] = request.user
            booking = OpenSpaceBooking.objects.create(space=space, **validated_data)
            space.status = 'unavailable'
            space.save(update_fields=['status'])
            return booking



class OpenSpaceBookingListSerializer(serializers.ModelSerializer):
    space = serializers.StringRelatedField()

    class Meta:
        model = OpenSpaceBooking
        fields = ['space', 'username', 'contact', 'duration', 'purpose', 'district']
        read_only_fields = ['id', 'created_at']



class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        
        
        
class UserStreetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role', 'ward', 'street']

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = '__all__'
        
        
class ProblemReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = UssdReport
        fields = ['id', 'phone_number', 'open_space', 'description', 'reference_number', 'status']



class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = '__all__'

    def create(self, validated_data):
        if 'report_id' not in validated_data:
            validated_data['report_id'] = ''.join(random.choices(string.digits, k=8))
        return super().create(validated_data)


# class ReportReplySerializer(serializers.ModelSerializer):
#     from_user = serializers.StringRelatedField(read_only=True)

#     class Meta:
#         model = ReportReplyVillageExecutive
#         fields = ['id', 'report', 'from_user', 'message', 'created_at']
#         read_only_fields = ['id', 'from_user', 'created_at']


class ReportReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportReply
        fields = ['id', 'report', 'message', 'replied_by', 'created_at']
        read_only_fields = ['report', 'replied_by', 'created_at']
        

# serializers.py
class ReportNotificationSerializer(serializers.ModelSerializer):
    report_id = serializers.CharField(source="report.report_id", read_only=True)
    replied_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ReportReply
        fields = ['id', 'report_id', 'message', 'replied_by', 'created_at']



class WardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ward
        fields = ['id', 'name']


class StreetSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source='ward.name', read_only=True)

    class Meta:
        model = Street
        fields = ['id', 'name', 'ward', 'ward_name']
        

class ReportForwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportForward
        fields = ['id', 'report', 'from_user', 'to_user', 'forwarded_at']
        read_only_fields = ['id', 'from_user', 'forwarded_at']

