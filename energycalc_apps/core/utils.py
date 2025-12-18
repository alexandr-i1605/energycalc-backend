from .redis import session_storage
from .models import MyUser
from django.conf import settings

def identity_user(request):
    session = get_session(request)
    
    if session is None or not session_storage.exists(session):
        return None
    
    user_id = session_storage.get(session)
    try:
        if isinstance(user_id, bytes):
            user_id = user_id.decode('utf-8')
        user = MyUser.objects.get(id=int(user_id))
        return user
    except (MyUser.DoesNotExist, ValueError, TypeError):
        return None

def get_session(request):
    if 'HTTP_X_SESSION_ID' in request.META:
        return request.META['HTTP_X_SESSION_ID']
    
    if 'session_id' in request.COOKIES:
        return request.COOKIES['session_id']
    
    return None

def get_minio_url(image_path):
    """
    Генерирует полный URL для изображения в MinIO
    
    Args:
        image_path: путь к изображению (например, '3.png' или 'images/3.png')
    
    Returns:
        Полный URL с правильным протоколом и IP
    """
    if image_path.startswith('images/'):
        image_path = image_path.replace('images/', '', 1)
    
    protocol = 'https' if settings.USE_HTTPS else 'http'
    return f"{protocol}://{settings.LOCAL_IP}:{settings.MINIO_PORT}/images/{image_path}"