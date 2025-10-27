from __future__ import annotations
from typing import Iterable
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.utils.functional import cached_property


# ======== Predicados básicos ========

def has_any_role(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return bool(getattr(user, "is_system_manager", False)
                or getattr(user, "is_employee", False)
                or getattr(user, "is_client", False))


def has_roles(user, require_manager: bool = False, require_employee: bool = False, require_client: bool = False) -> bool:
    """Retorna True se o usuário satisfaz pelo menos UMA das flags solicitadas."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    checks = []
    if require_manager:
        checks.append(bool(getattr(user, "is_system_manager", False)))
    if require_employee:
        checks.append(bool(getattr(user, "is_employee", False)))
    if require_client:
        checks.append(bool(getattr(user, "is_client", False)))
    # Se nenhuma role solicitada foi passada, caímos na regra geral "tem alguma role?"
    return any(checks) if checks else has_any_role(user)


# ======== Decorators (function-based views) ========

def require_any_role(view_func):
    """Bloqueia users sem nenhuma flag (e não-superusers)."""
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not has_any_role(request.user):
            raise PermissionDenied("Sem acesso ao sistema.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def require_manager(view_func):
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not has_roles(request.user, require_manager=True):
            raise PermissionDenied("Apenas Gerente do Sistema.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def require_employee(view_func):
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not has_roles(request.user, require_employee=True):
            raise PermissionDenied("Apenas Funcionário.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def require_client(view_func):
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not has_roles(request.user, require_client=True):
            raise PermissionDenied("Apenas Cliente.")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ======== Mixins (class-based views) ========

class RequireAnyRoleMixin:
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not has_any_role(request.user):
            raise PermissionDenied("Sem acesso ao sistema.")
        return super().dispatch(request, *args, **kwargs)


class RequireManagerMixin:
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not has_roles(request.user, require_manager=True):
            raise PermissionDenied("Apenas Gerente do Sistema.")
        return super().dispatch(request, *args, **kwargs)


class RequireEmployeeMixin:
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not has_roles(request.user, require_employee=True):
            raise PermissionDenied("Apenas Funcionário.")
        return super().dispatch(request, *args, **kwargs)


class RequireClientMixin:
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not has_roles(request.user, require_client=True):
            raise PermissionDenied("Apenas Cliente.")
        return super().dispatch(request, *args, **kwargs)
