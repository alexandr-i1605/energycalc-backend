from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import uuid
import requests
import threading

from .models import Device, CalculationRequest, DeviceInRequest, MyUser
from .serializers import *
from .minio import add_pic, delete_device_image
from .permissions import IsModerator, IsOwner, IsOwnerOrReadOnly
from .utils import identity_user, get_session
from .redis import session_storage

def calculate_base_consumption(calculation_request):
    devices_in_request = DeviceInRequest.objects.filter(calculation_request=calculation_request)
    total_consumption = 0
    
    for device_in_request in devices_in_request:
        consumption_value = device_in_request.device.consumption
        quantity = device_in_request.quantity
        total_consumption += consumption_value * quantity
    
    return total_consumption

ASYNC_SERVICE_URL = "http://localhost:8080/api/calculate"
SECRET_TOKEN = "12345678"

def call_async_service(calculation_request):
    """Вызов асинхронного сервиса для расчета результата"""
    devices_in_request = DeviceInRequest.objects.filter(calculation_request=calculation_request)
    
    devices_data = []
    for device_in_request in devices_in_request:
        devices_data.append({
            "device": {
                "id": device_in_request.device.id,
                "consumption": float(device_in_request.device.consumption)
            },
            "quantity": device_in_request.quantity
        })
    
    request_data = {
        "request_id": calculation_request.id,
        "residents": calculation_request.residents,
        "temperature": calculation_request.temperature,
        "devices": devices_data
    }
    
    try:
        def async_call():
            response = requests.post(ASYNC_SERVICE_URL, json=request_data, timeout=5)

        thread = threading.Thread(target=async_call)
        thread.daemon = True
        thread.start()
    except Exception as e:
        print(f"Error calling async service: {e}")

@swagger_auto_schema(
    method='get',
    operation_description="GET список устройств с фильтрацией",
    manual_parameters=[
        openapi.Parameter('name', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Название устройства')
    ]
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def search_devices(request):
    device_name = request.GET.get("name", "")
    
    devices = Device.objects.all()
    
    if device_name:
        devices = devices.filter(name__icontains=device_name)
    
    serializer = DeviceSerializer(devices, many=True)
    
    return Response(serializer.data)

@swagger_auto_schema(method='get', operation_description="GET одна запись устройства")
@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def get_device_by_id(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    serializer = DeviceSerializer(device)
    return Response(serializer.data)

@swagger_auto_schema(method='post', operation_description="POST добавление устройства", request_body=DeviceSerializer)
@api_view(["POST"])
@permission_classes([IsModerator])
def create_device(request):
    serializer = DeviceSerializer(data=request.data)
    
    if serializer.is_valid():
        device = serializer.save()
        return Response(DeviceSerializer(device).data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(method='put', operation_description="PUT изменение устройства", request_body=DeviceSerializer)
@api_view(["PUT"])
@permission_classes([IsModerator])
def update_device(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    
    if 'image' in request.FILES:
        image_result = add_pic(device, request.FILES['image'])
        if image_result.status_code != 200:
            return image_result
    
    serializer = DeviceSerializer(device, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(method='delete', operation_description="DELETE удаление устройства")
@api_view(["DELETE"])
@permission_classes([IsModerator])
def delete_device(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    
    delete_device_image(device)
    device.delete()
    
    return Response(status=status.HTTP_204_NO_CONTENT)

@swagger_auto_schema(method='post', operation_description="POST добавление изображения")
@api_view(["POST"])
@permission_classes([IsModerator])
def add_device_image(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    
    image = request.FILES.get('image')
    if not image:
        return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)
    
    result = add_pic(device, image)
    return result

@swagger_auto_schema(method='post', operation_description="POST добавление в заявку-черновик")
@api_view(["POST"])
@permission_classes([IsOwner])
def add_device_to_draft_request(request, device_id):
    user = identity_user(request)
    if not user:
        return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
    device = get_object_or_404(Device, id=device_id)
    
    draft_request = CalculationRequest.objects.filter(
        client=user,
        status=CalculationRequest.CalculationRequestStatus.DRAFT
    ).first()

    if not draft_request:
        draft_request = CalculationRequest.objects.create(
            client=user,
            status=CalculationRequest.CalculationRequestStatus.DRAFT,
            residents=1,
            temperature=20,
            result=None
        )

    device_in_request, created = DeviceInRequest.objects.get_or_create(
        calculation_request=draft_request,
        device=device,
        defaults={'quantity': 1}
    )
    
    if not created:
        device_in_request.quantity += 1
        device_in_request.save()

    serializer = CalculationRequestSerializer(draft_request)
    return Response(serializer.data, status=status.HTTP_200_OK)

# Методы для заявок
@swagger_auto_schema(method='get', operation_description="GET иконки корзины")
@api_view(["GET"])
@permission_classes([])
def get_cart_icon(request):
    user = identity_user(request)
    
    if not user or not user.is_authenticated:
        response_data = {
            "draft_request_id": None,
            "devices_count": 0
        }
        return Response(response_data)
    
    draft_request = CalculationRequest.objects.filter(
        client=user,
        status=CalculationRequest.CalculationRequestStatus.DRAFT
    ).first()

    response_data = {
        "draft_request_id": draft_request.id if draft_request else None,
        "devices_count": DeviceInRequest.objects.filter(calculation_request=draft_request).count() if draft_request else 0
    }
    
    return Response(response_data)

@swagger_auto_schema(
    method='get',
    operation_description="GET список заявок с фильтрацией",
    manual_parameters=[
        openapi.Parameter('status', openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter('date_start', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Дата начала (YYYY-MM-DD)'),
        openapi.Parameter('date_end', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Дата окончания (YYYY-MM-DD)')
    ]
)
@api_view(["GET"])
def search_requests(request):
    user = identity_user(request)
    
    if not user:
        return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
    status_filter = request.GET.get("status", "")
    date_start = request.GET.get("date_start")
    date_end = request.GET.get("date_end")
    
    if user.is_moderator:
        requests = CalculationRequest.objects.exclude(
            status=CalculationRequest.CalculationRequestStatus.DELETED
        )
    else:
        requests = CalculationRequest.objects.filter(
            client=user
        ).exclude(
            status=CalculationRequest.CalculationRequestStatus.DELETED
        )
    
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    if date_start:
        if 'T' in date_start:
            date_start = date_start.split('T')[0]
        start_date = parse_date(date_start)
        if start_date:
            requests = requests.filter(creation_datetime__date__gte=start_date)
    
    if date_end:
        if 'T' in date_end:
            date_end = date_end.split('T')[0]
        end_date = parse_date(date_end)
        if end_date:
            requests = requests.filter(creation_datetime__date__lte=end_date)
    
    serializer = CalculationRequestListSerializer(requests, many=True)
    return Response(serializer.data)

@swagger_auto_schema(method='get', operation_description="GET одна запись заявки")
@api_view(["GET"])
def get_request_by_id(request, request_id):
    user = identity_user(request)
    if not user:
        return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    
    if not user.is_moderator and calculation_request.client != user:
        return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
    
    if calculation_request.status == CalculationRequest.CalculationRequestStatus.DELETED:
        return Response({"error": "Request not found"}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = CalculationRequestDetailSerializer(calculation_request)
    return Response(serializer.data)

@swagger_auto_schema(method='put', operation_description="PUT изменения полей заявки", request_body=CalculationRequestSerializer)
@api_view(["PUT"])
@permission_classes([IsOwner])
def update_request(request, request_id):
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    
    if any(field in request.data for field in ['id', 'status', 'client', 'moderator', 
                                              'creation_datetime', 'formation_datetime', 
                                              'completion_datetime']):
        return Response({"error": "System fields cannot be modified"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    serializer = CalculationRequestSerializer(calculation_request, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(method='put', operation_description="PUT сформировать создателем")
@api_view(["PUT"])
@permission_classes([IsOwner])
def form_request(request, request_id):
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    
    if calculation_request.status != CalculationRequest.CalculationRequestStatus.DRAFT:
        return Response({"error": "Only draft requests can be formed"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    if not calculation_request.residents or not calculation_request.temperature:
        return Response({"error": "Required fields are missing"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    if not DeviceInRequest.objects.filter(calculation_request=calculation_request).exists():
        return Response({"error": "No devices in request"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    calculation_request.status = CalculationRequest.CalculationRequestStatus.FORMED
    calculation_request.formation_datetime = timezone.now()
    calculation_request.save()
    
    serializer = CalculationRequestSerializer(calculation_request)
    return Response(serializer.data)

@swagger_auto_schema(
    method='put', 
    operation_description="PUT завершить/отклонить модератором",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'action': openapi.Schema(type=openapi.TYPE_STRING, description='"complete" или "reject"')
        }
    )
)
@api_view(["PUT"])
@permission_classes([IsModerator])
def complete_request(request, request_id):
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    action = request.data.get("action")
    
    if calculation_request.status != CalculationRequest.CalculationRequestStatus.FORMED:
        return Response({"error": "Only formed requests can be completed/rejected"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    if action == "complete":
        call_async_service(calculation_request)
        calculation_request.moderator = identity_user(request)
        calculation_request.completion_datetime = timezone.now()
        calculation_request.save()
    elif action == "reject":
        calculation_request.status = CalculationRequest.CalculationRequestStatus.REJECTED
        calculation_request.moderator = identity_user(request)
        calculation_request.completion_datetime = timezone.now()
        calculation_request.save()
    else:
        return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = CalculationRequestSerializer(calculation_request)
    return Response(serializer.data)

@swagger_auto_schema(
    method='put',
    operation_description="PUT получение результата от асинхронного сервиса",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'token': openapi.Schema(type=openapi.TYPE_STRING),
            'request_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'result': openapi.Schema(type=openapi.TYPE_INTEGER)
        },
        required=['token', 'request_id', 'result']
    )
)
@api_view(["PUT"])
@authentication_classes([])
@permission_classes([])
def receive_calculation_result(request, request_id):
    """Endpoint для получения результатов расчета от асинхронного сервиса"""
    token = request.data.get("token")
    result_value = request.data.get("result")
    
    if token != SECRET_TOKEN:
        return Response({"error": "Invalid token"}, status=status.HTTP_403_FORBIDDEN)
    
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    
    calculation_request.result = result_value
    calculation_request.status = CalculationRequest.CalculationRequestStatus.COMPLETED
    calculation_request.save()
    
    serializer = CalculationRequestSerializer(calculation_request)
    return Response(serializer.data)

@swagger_auto_schema(
    method='put',
    operation_description="PUT изменение статуса заявки модератором",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'status': openapi.Schema(type=openapi.TYPE_STRING, description='Новый статус: COMPLETED или REJECTED')
        },
        required=['status']
    )
)
@api_view(["PUT"])
@authentication_classes([])
@permission_classes([])
def update_request_status(request, request_id):
    """Изменение статуса заявки модератором"""
    user = identity_user(request)
    if not user:
        return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_moderator:
        return Response({"error": "Moderator access required"}, status=status.HTTP_403_FORBIDDEN)
    
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    new_status = request.data.get("status")
    
    if new_status not in [CalculationRequest.CalculationRequestStatus.COMPLETED, 
                          CalculationRequest.CalculationRequestStatus.REJECTED]:
        return Response({"error": "Invalid status. Only COMPLETED or REJECTED allowed"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    if calculation_request.status == CalculationRequest.CalculationRequestStatus.DELETED:
        return Response({"error": "Cannot change status of deleted request"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    if new_status == CalculationRequest.CalculationRequestStatus.COMPLETED:
        # Если одобряем заявку со статусом FORMED, вызываем асинхронный сервис для расчета результата
        if calculation_request.status == CalculationRequest.CalculationRequestStatus.FORMED:
            # Вызываем асинхронный сервис для расчета результата
            call_async_service(calculation_request)
            # Статус остается FORMED до получения результата от асинхронного сервиса
            calculation_request.moderator = user
            calculation_request.completion_datetime = timezone.now()
            calculation_request.save()
        else:
            # Если заявка уже имеет результат или статус не FORMED, просто меняем статус
            calculation_request.status = new_status
            calculation_request.moderator = user
            calculation_request.completion_datetime = timezone.now()
            calculation_request.save()
    elif new_status == CalculationRequest.CalculationRequestStatus.REJECTED:
        calculation_request.status = new_status
        calculation_request.moderator = user
        calculation_request.completion_datetime = timezone.now()
        calculation_request.save()
    
    serializer = CalculationRequestSerializer(calculation_request)
    return Response(serializer.data)

@swagger_auto_schema(method='delete', operation_description="DELETE удаление заявки")
@api_view(["DELETE"])
@permission_classes([IsOwner])
def delete_request(request, request_id):
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    
    if calculation_request.status != CalculationRequest.CalculationRequestStatus.DRAFT:
        return Response({"error": "Only draft requests can be deleted"}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    calculation_request.status = CalculationRequest.CalculationRequestStatus.DELETED
    calculation_request.save()
    
    return Response(status=status.HTTP_204_NO_CONTENT)

# Методы для М-М связи
@swagger_auto_schema(method='delete', operation_description="DELETE удаление из заявки")
@api_view(["DELETE"])
@permission_classes([IsOwner])
def delete_device_from_request(request, request_id, device_id):
    device_in_request = get_object_or_404(
        DeviceInRequest, 
        calculation_request_id=request_id, 
        device_id=device_id
    )
    
    device_in_request.delete()
    
    calculation_request = get_object_or_404(CalculationRequest, id=request_id)
    devices = DeviceInRequest.objects.filter(calculation_request=calculation_request)
    serializer = DeviceInRequestSerializer(devices, many=True)
    
    return Response(serializer.data)

@swagger_auto_schema(method='put', operation_description="PUT изменение количества", request_body=DeviceInRequestSerializer)
@api_view(["PUT"])
@permission_classes([IsOwner])
def update_device_in_request(request, request_id, device_id):
    device_in_request = get_object_or_404(
        DeviceInRequest, 
        calculation_request_id=request_id, 
        device_id=device_id
    )
    
    serializer = DeviceInRequestSerializer(device_in_request, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Методы аутентификации
@swagger_auto_schema(method='post', operation_description="POST регистрация", request_body=UserRegisterSerializer)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def register_user(request):
    serializer = UserRegisterSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        session_id = str(uuid.uuid4())
        session_storage.set(session_id, user.id)
        
        response_data = MyUserSerializer(user).data
        response_data['session_id'] = session_id
        
        response = Response(response_data, status=status.HTTP_201_CREATED)
        response.set_cookie("session_id", session_id, httponly=False, max_age=86400 * 30, path="/", domain=None, samesite='Lax')  # 30 дней
        return response
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(method='get', operation_description="GET профиль пользователя")
@api_view(["GET"])
def get_user_profile(request, user_id):
    user = identity_user(request)
    if not user:
        return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
    if user.id != user_id and not user.is_moderator:
        return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
        
    user_obj = get_object_or_404(MyUser, id=user_id)
    serializer = MyUserSerializer(user_obj)
    return Response(serializer.data)

@swagger_auto_schema(method='put', operation_description="PUT обновление профиля", request_body=MyUserSerializer)
@csrf_exempt
@api_view(["PUT"])
def update_user_profile(request, user_id):
    user = identity_user(request)
    if not user:
        return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
    if user.id != user_id:
        return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
        
    user_obj = get_object_or_404(MyUser, id=user_id)
    serializer = MyUserSerializer(user_obj, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(method='post', operation_description="POST аутентификация", request_body=UserLoginSerializer)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user is not None:
        # Создаем сессию в Redis
        session_id = str(uuid.uuid4())
        session_storage.set(session_id, user.id)
        
        response_data = MyUserSerializer(user).data
        response_data['session_id'] = session_id
        
        response = Response(response_data)
        response.set_cookie("session_id", session_id, httponly=False, max_age=86400 * 30, path="/", domain=None, samesite='Lax')  # 30 дней
        return response
    
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

@swagger_auto_schema(method='post', operation_description="POST деавторизация")
@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def logout_user(request):
    session = get_session(request)
    if session:
        session_storage.delete(session)
    
    response = Response({"message": "Logged out successfully"})
    response.delete_cookie('session_id')
    return response