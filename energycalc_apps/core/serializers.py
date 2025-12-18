from rest_framework import serializers
from .models import Device, CalculationRequest, DeviceInRequest, MyUser
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from .utils import get_minio_url
from django.conf import settings

class DeviceSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Device
        fields = ['id', 'name', 'category', 'image_url', 'power', 'consumption', 
                  'peak_power', 'voltage', 'work_per_day', 'energy_class']
    
    def get_image_url(self, obj):
        """
        Генерирует URL изображения с текущим IP и протоколом
        """
        if not obj.image_url:
            return None
        
        if obj.image_url.startswith('http://') or obj.image_url.startswith('https://'):
            image_name = obj.image_url.split('/')[-1]
        else:
            image_name = obj.image_url
        
        return get_minio_url(image_name)

class DeviceInRequestSerializer(serializers.ModelSerializer):
    device = DeviceSerializer(read_only=True)
    
    class Meta:
        model = DeviceInRequest
        fields = ["device", "quantity"]

class CalculationRequestSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client.username', read_only=True)
    moderator_username = serializers.CharField(source='moderator.username', read_only=True, allow_null=True)

    class Meta:
        model = CalculationRequest
        fields = ["id", "status", "residents", "temperature", "result", 
                  "creation_datetime", "formation_datetime", "completion_datetime", 
                  "client_username", "moderator_username"]
        read_only_fields = ["id", "status", "creation_datetime", "formation_datetime", 
                           "completion_datetime", "client_username", "moderator_username"]

class CalculationRequestListSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client.username', read_only=True)
    devices_count = serializers.SerializerMethodField()

    class Meta:
        model = CalculationRequest
        fields = ["id", "status", "residents", "temperature", "result", 
                  "creation_datetime", "formation_datetime", "client_username", "devices_count"]

    def get_devices_count(self, obj):
        return DeviceInRequest.objects.filter(calculation_request=obj).count()

class CalculationRequestDetailSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client.username', read_only=True)
    moderator_username = serializers.CharField(source='moderator.username', read_only=True, allow_null=True)
    devices = serializers.SerializerMethodField()

    class Meta:
        model = CalculationRequest
        fields = ["id", "status", "residents", "temperature", "result", 
                  "creation_datetime", "formation_datetime", "completion_datetime", 
                  "client_username", "moderator_username", "devices"]

    def get_devices(self, obj):
        devices_in_request = DeviceInRequest.objects.filter(calculation_request=obj)
        return DeviceInRequestSerializer(devices_in_request, many=True).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if representation.get('result') == 0:
            representation['result'] = None
        return representation

class MyUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyUser
        fields = ["id", "username", "first_name", "last_name", "email", "is_moderator"]
        read_only_fields = ["is_moderator"]

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = MyUser
        fields = ["username", "password", "first_name", "last_name", "email"]
    
    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)