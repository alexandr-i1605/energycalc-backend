from rest_framework import permissions
from django.urls import path, include
from energycalc_apps.core import views
from rest_framework import routers
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.contrib import admin

router = routers.DefaultRouter()

schema_view = get_schema_view(
   openapi.Info(
      title="EnergyCalc API",
      default_version='v1',
      description="API для расчета энергопотребления",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@energycalc.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # методы для услуг Devices
    path('api/devices/', views.search_devices, name='search_devices'),# GET
    path('api/devices/<int:device_id>/', views.get_device_by_id, name='get_device_by_id'),# GET
    path('api/devices/create/', views.create_device, name='create_device'),# POST
    path('api/devices/<int:device_id>/update/', views.update_device, name='update_device'),# PUT
    path('api/devices/<int:device_id>/delete/', views.delete_device, name='delete_device'),# DELETE
    path('api/devices/<int:device_id>/add_image/', views.add_device_image, name='add_device_image'),# POST
    path('api/devices/<int:device_id>/add_to_request/', views.add_device_to_draft_request, name='add_device_to_draft_request'),# POST
    
    # методы для заявок CalculationRequest
    path('api/consumption-calc/cart_icon/', views.get_cart_icon, name='get_cart_icon'),# GET
    path('api/consumption-calc/', views.search_requests, name='search_requests'),# GET
    path('api/consumption-calc/<int:request_id>/', views.get_request_by_id, name='get_request_by_id'),# GET
    path('api/consumption-calc/<int:request_id>/update/', views.update_request, name='update_request'),# PUT
    path('api/consumption-calc/<int:request_id>/form/', views.form_request, name='form_request'),# PUT
    path('api/consumption-calc/<int:request_id>/complete/', views.complete_request, name='complete_request'),# PUT
    path('api/consumption-calc/<int:request_id>/status/', views.update_request_status, name='update_request_status'),# PUT
    path('api/consumption-calc/result/<int:request_id>/', views.receive_calculation_result, name='receive_calculation_result'),# PUT
    path('api/consumption-calc/<int:request_id>/delete/', views.delete_request, name='delete_request'),# DELETE
    
    # методы для М-М DeviceInRequest
    path('api/consumption-calc/<int:request_id>/devices/<int:device_id>/delete/', 
         views.delete_device_from_request, name='delete_device_from_request'),# DELETE
    path('api/consumption-calc/<int:request_id>/devices/<int:device_id>/update/', 
         views.update_device_in_request, name='update_device_in_request'),# PUT
    
    # методы для услуг пользователя
    path('api/users/register/', views.register_user, name='register_user'),# POST
    path('api/users/<int:user_id>/profile/', views.get_user_profile, name='get_user_profile'),# GET
    path('api/users/<int:user_id>/update/', views.update_user_profile, name='update_user_profile'),# PUT
    path('api/users/login/', views.login_user, name='login_user'),# POST
    path('api/users/logout/', views.logout_user, name='logout_user'),# POST

    #swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]