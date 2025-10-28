#accounts/context_processors.py
def roles_context(request):
    user = getattr(request, "user", None)
    is_auth = bool(user and user.is_authenticated)

    return {
        "is_authenticated": is_auth,
        "is_superuser": bool(is_auth and user.is_superuser),
        "is_system_manager": bool(is_auth and getattr(user, "is_system_manager", False)),
        "is_employee": bool(is_auth and getattr(user, "is_employee", False)),
        "is_client": bool(is_auth and getattr(user, "is_client", False)),
        "has_any_role": bool(is_auth and (
            getattr(user, "is_superuser", False)
            or getattr(user, "is_system_manager", False)
            or getattr(user, "is_employee", False)
            or getattr(user, "is_client", False)
        )),
    }
