from django.conf import settings
from minio import Minio
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework.response import Response

def get_minio_client():
    return Minio(
        endpoint=settings.AWS_S3_ENDPOINT_URL,
        access_key=settings.AWS_ACCESS_KEY_ID,
        secret_key=settings.AWS_SECRET_ACCESS_KEY,
        secure=settings.MINIO_USE_SSL
    )

def process_file_upload(file_object: InMemoryUploadedFile, client, image_name):
    try:
        if not client.bucket_exists('images'):
            client.make_bucket('images')
        
        client.put_object('images', image_name, file_object, file_object.size)
        return f"http://{settings.AWS_S3_ENDPOINT_URL}/images/{image_name}"
    except Exception as e:
        return {"error": str(e)}

def add_pic(device, pic):
    client = get_minio_client()
    
    file_extension = pic.name.split('.')[-1].lower() if '.' in pic.name else 'png'
    image_name = f"{device.id}.{file_extension}"
    
    if not pic:
        return Response({"error": "No file provided for image."}, status=400)
    
    # Пытаемся удалить старую картинку если есть
    try:
        client.remove_object('images', image_name)
    except:
        pass
    
    result = process_file_upload(pic, client, image_name)
    
    if isinstance(result, dict) and 'error' in result:
        return Response({"error": result['error']}, status=500)
    
    device.image_url = result
    device.save()
    
    return Response({"message": "Image uploaded successfully", "image_url": result})

def delete_device_image(device):
    try:
        client = get_minio_client()
        
        if device.image_url:
            image_name = device.image_url.split('/')[-1]
        else:
            image_name = f"{device.id}.png"
        
        client.remove_object('images', image_name)
        return True
    except Exception as e:
        print(f"Error deleting image for device {device.id}: {str(e)}")
        return False