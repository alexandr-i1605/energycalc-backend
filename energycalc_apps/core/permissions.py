from rest_framework import permissions
from .utils import identity_user

class IsModerator(permissions.BasePermission):
    def has_permission(self, request, view):
        user = identity_user(request)
        return bool(user and user.is_moderator)

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = identity_user(request)
        
        if request.method in permissions.SAFE_METHODS:
            return True
        return user and obj.client == user

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = identity_user(request)
        return user and obj.client == user

class IsGuest(permissions.BasePermission):
    def has_permission(self, request, view):
        user = identity_user(request)
        return user is None