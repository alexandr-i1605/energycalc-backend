from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class Device(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    
    name = models.CharField(max_length=255, verbose_name='Название устройства')
    category = models.CharField(max_length=100, verbose_name='Категория')
    image_url = models.URLField(max_length=500, verbose_name='URL изображения')
    
    power = models.IntegerField(verbose_name='Мощность (Вт)')
    consumption = models.FloatField(verbose_name='Потребление в месяц (кВт)')
    peak_power = models.IntegerField(verbose_name='Пиковая мощность (Вт)')
    voltage = models.CharField(max_length=50, verbose_name='Напряжение')
    work_per_day = models.CharField(max_length=50, verbose_name='Работа в день')
    energy_class = models.CharField(max_length=10, verbose_name='Энергетический класс')

    class Meta:
        db_table = 'device'

    def __str__(self):
        return self.name

class CalculationRequest(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    class CalculationRequestStatus(models.TextChoices):
        DRAFT = "DRAFT"
        DELETED = "DELETED"
        FORMED = "FORMED"
        COMPLETED = "COMPLETED"
        REJECTED = "REJECTED"

    status = models.CharField(
        max_length=10,
        choices=CalculationRequestStatus.choices,
        default=CalculationRequestStatus.DRAFT,
    )

    residents=models.IntegerField(default=1)
    temperature=models.IntegerField(default=20)
    result=models.IntegerField(null=True, blank=True, default=None)
    #result = base_consuption + (abs(20-temperature)*0.01*base_consuption)+
    #+(residents-1)*0.3*base_consuption

    creation_datetime = models.DateTimeField(auto_now_add=True)
    formation_datetime = models.DateTimeField(blank=True, null=True)
    completion_datetime = models.DateTimeField(blank=True, null=True)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING,
                                related_name='created_request')
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING,
                                 related_name='moderated_request', blank=True, null=True)
    
    
    class Meta:
        db_table = 'CalculationRequest'

    def __str__(self):
        return f"Расчет № {self.id}"
    
class DeviceInRequest(models.Model):
    calculation_request = models.ForeignKey(CalculationRequest, on_delete=models.DO_NOTHING)
    device = models.ForeignKey(Device, on_delete=models.DO_NOTHING)
    quantity = models.IntegerField(default=1)

    class Meta:
            db_table = 'DeviceInRequest'
            unique_together = ('calculation_request', 'device')

    def __str__(self):
        return f"{self.calculation_request.id}-{self.device.id}"

class MyUser(AbstractUser):
    is_moderator = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'myuser'
    
    def __str__(self):
        return f"{self.username} ({'Модератор' if self.is_moderator else 'Пользователь'})"