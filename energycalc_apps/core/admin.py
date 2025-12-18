from django.contrib import admin
from .models import MyUser, Device, CalculationRequest, DeviceInRequest

admin.site.register(Device)
admin.site.register(CalculationRequest)
admin.site.register(DeviceInRequest)
admin.site.register(MyUser)
