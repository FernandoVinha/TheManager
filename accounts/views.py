# accounts/views.py
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic.edit import UpdateView

from .forms import (
    UserCreateForm,
    PasswordSetupForm,
    SelfProfileForm,
    AdminUserForm,
)
from .models import User, UserInvite
from .services import gitea as gitea_api
from .utils import send_reset_link_or_return

log = logging.getLogger(__name__)
UserModel = get_user_model()

# --- Rate limiting config (simples, baseada em cache) ---
# max requests per window per email/ip
PW_RESET_MAX = int(getattr(settings, "PW_RESET_MAX", 5))
PW_RESET_WINDOW = int(getattr(settings, "PW_RESET_WINDOW_SECONDS", 60 * 60))  # default 1 hora


# =========================================================
# Helpers
# =========================================================

def _safe_redirect(request: HttpRequest, default_name: str) -> HttpResponse:
    """Redirects to ?next= if safe (same host), otherwise to named URL."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect(reverse(default_name))


def _forbidden() -> HttpResponse:
    return HttpResponseForbidden("Forbidden")


def _throttle_key_for_email(email: str) -> str:
    return f"pw_reset_email:{email}"


def _throttle_key_for_ip(ip: str) -> str:
    return f"pw_reset_ip:{ip}"


def _increment_counter(key: str, window: int) -> int:
    """
    Incrementa contador no cache e retorna novo valor.
    Usa set + incr para compatibilidade com locmem (caso não suporte incr).
    """
    try:
        # tenta incr (mais eficiente em caches distribuídos)
        val = cache.incr(key)
        return int(val)
    except Exception:
        # fallback: pega valor atual e seta+incr
        val = cache.get(key)
        if val is None:
            cache.set(key, 1, timeout=window)
            return 1
        else:
            try:
                new = int(val) + 1
            except Exception:
                new = 1
            cache.set(key, new, timeout=window)
            return new


def _check_and_increment_throttle(email: str, ip: str) -> tuple[bool, Optional[str]]:
    """
    Retorna (allowed, reason). Se allowed == False -> operação deve ser bloqueada
    por excesso de requisições.
    """
    email_key = _throttle_key_for_email(email)
    ip_key = _throttle_key_for_ip(ip)

    email_count = cache.get(email_key) or 0
    ip_count = cache.get(ip_key) or 0

    if int(email_count) >= PW_RESET_MAX:
        return False, "Too many reset requests for this email. Try later."
    if int(ip_count) >= (PW_RESET_MAX * 4):  # limite mais alto por IP
        return False, "Too many requests from your IP. Try later."

    # increment counters
    new_email_count = _increment_counter(email_key, PW_RESET_WINDOW)
    new_ip_count = _increment_counter(ip_key, PW_RESET_WINDOW)

    log.debug("pw reset counters: email=%s ip=%s -> %s/%s", email, ip, new_email_count, new_ip_count)
    return True, None


# =========================================================
# Auth (Sign in / Sign out)
# =========================================================

class SignInView(LoginView):
    """Simple username/password login. No self-signup."""
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        # Após login, cair na entrada inteligente de usuários por padrão
        return reverse_lazy("users")


class SignOutView(LoginRequiredMixin, View):
    """Logout compatível com GET/POST (de acordo com seu navbar)."""
    def post(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        messages.success(request, "You have been signed out.")
        return redirect(reverse("login"))

    def get(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        messages.success(request, "You have been signed out.")
        return redirect(reverse("login"))


# =========================================================
# Users entry: envia para lista (admin/manager) ou perfil (demais)
# =========================================================

class UsersEntryView(LoginRequiredMixin, View):
    """
    /users/ → se admin/manager: lista de usuários
            → caso contrário: página de edição do próprio perfil
    """
    def get(self, request: HttpRequest, *args, **kwargs):
        if request.user.can_manage_users:
            return redirect(reverse("gitea_users"))
        return redirect(reverse("profile"))


# =========================================================
# Profile (self-edit) — usa SelfProfileForm
# =========================================================

class ProfileView(LoginRequiredMixin, UpdateView):
    model = get_user_model()
    template_name = "accounts/profile.html"
    form_class = SelfProfileForm

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        messages.success(self.request, "Profile updated.")
        return reverse_lazy("profile")


# =========================================================
# Gitea Users (read-only list pulled from Gitea API) — admin/manager only
# =========================================================

class GiteaUserListView(LoginRequiredMixin, View):
    """Read-only list of users from Gitea (via gitea_api)."""
    template_name = "accounts/gitea_users.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        # Apenas admin/manager podem abrir a lista
        if not (request.user.can_manage_users):
            return redirect("profile")

        def to_int(val: Optional[str], default: int) -> int:
            try:
                return int(val) if val is not None else default
            except Exception:
                return default

        page = to_int(request.GET.get("page"), 1)
        limit = to_int(request.GET.get("limit"), 50)
        query = request.GET.get("query", "") or None

        if page < 1:
            page = 1
        if limit not in (25, 50, 100):
            limit = 50

        try:
            data = gitea_api.list_users(page=page, limit=limit, query=query)
            users = data.get("results", [])
            total = int(data.get("total", 0) or 0)
            error: Optional[str] = None
        except Exception as e:
            users = []
            total = 0
            error = str(e)
            log.exception("Falha ao listar usuários no Gitea: %s", e)

        # ===== Enriquecer com local_pk (id do User no Django), para ações CRUD locais =====
        for u in users:
            login_name = (u.get("login") or "").strip()
            email = (u.get("email") or "").strip().lower()

            local = None
            if login_name:
                local = User.objects.filter(username__iexact=login_name).only("id").first()
            if not local and email:
                local = User.objects.filter(email__iexact=email).only("id").first()

            u["local_pk"] = local.id if local else None
        # ===== FIM DO BLOCO =====

        has_prev = page > 1
        has_next = (page * limit) < total if total else len(users) == limit

        ctx = {
            "users": users,
            "total": total,
            "page": page,
            "limit": limit,
            "query": query or "",
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": page - 1,
            "next_page": page + 1,
            "limit_options": [25, 50, 100],
            "error": error,
        }
        return render(request, self.template_name, ctx)


# =========================================================
# User Creation (Admin/Manager) → token email (ou link copiável)
# =========================================================

class UserCreateView(LoginRequiredMixin, View):
    template_name = "accounts/user_create.html"
    template_success_fallback = "accounts/user_create_success.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if not (request.user.can_manage_users):
            return _forbidden()

        form = UserCreateForm()
        form.request = request  # validação de role (manager não cria admin)
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        if not (request.user.can_manage_users):
            return _forbidden()

        form = UserCreateForm(request.POST)
        form.request = request
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        # Cria usuário inativo com senha inutilizável
        user: User = form.save(commit=False)
        user.is_active = False

        # Garante username base a partir do email se não fornecido
        base = (user.username or (user.email.split("@")[0])).strip()
        base = "".join(ch for ch in base if ch.isalnum() or ch in ("_", "-")).lower() or "user"
        candidate = base
        i = 1
        while User.objects.filter(username=candidate).exists():
            i += 1
            candidate = f"{base}{i}"
        user.username = candidate

        # marca senha inutilizável localmente - a ativação será via invite link
        user.set_unusable_password()
        user.save()

        # Cria invite
        invite = UserInvite.create_for_user(user)

        # Envia o e-mail (ou retorna link copiável se SMTP não disponivel)
        try:
            link = send_reset_link_or_return(user, invite.token, request)
        except Exception as e:
            # Se o envio falhar de forma inesperada, log e disponibiliza link ao admin
            log.exception("Erro ao enviar e-mail de ativação para user=%s: %s", user.pk, e)
            link = None

        if link:
            # caso sem SMTP: mostramos página de sucesso com o link copiável
            messages.warning(request, "Email não está configurado — copie o link abaixo e envie manualmente.")
            return render(
                request,
                self.template_success_fallback,
                {"user_created": user, "reset_link": link},
            )

        # Se o backend SMTP enviou, informamos o admin e redirecionamos
        messages.success(request, "User created and an email to set password was sent.")
        return _safe_redirect(request, default_name="gitea_users")


# =========================================================
# Forgot Password (público) — anti-enumeração + rate limiting
# =========================================================

class ForgotPasswordView(View):
    template_name = "accounts/forgot_password.html"
    template_done_copy = "accounts/forgot_password_done.html"
    template_done_sent = "accounts/forgot_password_sent.html"

    def get_client_ip(self, request: HttpRequest) -> str:
        # Método simples para obter IP (X-Forwarded-For se presente)
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        email = (request.POST.get("email") or "").strip().lower()
        if not email:
            return render(request, self.template_name, {"error": "Email is required."})

        # Throttle básico para evitar abuso
        client_ip = self.get_client_ip(request)
        allowed, reason = _check_and_increment_throttle(email=email, ip=client_ip)
        if not allowed:
            log.warning("Throttle PW reset blocked: email=%s ip=%s reason=%s", email, client_ip, reason)
            # Mostramos mensagem genérica para evitar enumeração de razão
            messages.error(request, "Too many requests. Try again later.")
            return render(request, self.template_done_sent)

        user = User.objects.filter(email=email).first()
        if user:
            try:
                # Remove invite anterior e cria novo
                existing_invite = getattr(user, "invite", None)
                if existing_invite:
                    existing_invite.delete()
                invite = UserInvite.create_for_user(user)

                link = send_reset_link_or_return(user, invite.token, request)
                if link:
                    # Sem SMTP => mostra link copiável (e não informa se user existe ou não)
                    return render(request, self.template_done_copy, {"reset_link": link})
            except Exception as e:
                log.exception("Erro ao processar forgot_password para email=%s: %s", email, e)
                # mesmo em erro interno, não retornamos informação sobre existência do usuário

        # Sempre retornar "sent" para evitar enumeração — comportamento esperado
        return render(request, self.template_done_sent)


# =========================================================
# Password Reset / Activation (via token)
# =========================================================

class PasswordResetConfirmView(View):
    template_name = "accounts/password_reset_confirm.html"

    def get(self, request: HttpRequest, token: str) -> HttpResponse:
        invite = get_object_or_404(UserInvite, token=token)
        if invite.is_expired():
            invite.delete()
            messages.error(request, "This link has expired. Please request a new one.")
            return redirect(reverse("forgot_password"))
        return render(request, self.template_name, {"form": PasswordSetupForm()})

    def post(self, request: HttpRequest, token: str) -> HttpResponse:
        invite = get_object_or_404(UserInvite, token=token)
        if invite.is_expired():
            invite.delete()
            messages.error(request, "This link has expired. Please request a new one.")
            return redirect(reverse("forgot_password"))

        form = PasswordSetupForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = invite.user
        # Atribui a senha e ativa a conta
        user.set_password(form.cleaned_data["password1"])
        user.is_active = True
        user.save()

        # Consome token
        try:
            invite.delete()
        except Exception:
            log.exception("Erro ao deletar invite após reset (user=%s)", user.pk)

        # Login automático
        login(request, user)
        messages.success(request, "Password updated. Welcome!")
        return _safe_redirect(request, default_name="users")


# =========================================================
# Resend invite (Admin/Manager)
# =========================================================

class ResendInviteView(LoginRequiredMixin, View):
    template_name_copy = "accounts/user_create_success.html"

    def post(self, request: HttpRequest, user_id: int) -> HttpResponse:
        if not (request.user.can_manage_users):
            return _forbidden()

        target = get_object_or_404(User, pk=user_id)

        # Managers não operam em Admin
        if request.user.is_manager() and target.is_admin():
            messages.error(request, "Managers cannot resend admin invitations.")
            return _safe_redirect(request, default_name="gitea_users")

        existing = getattr(target, "invite", None)
        if existing:
            existing.delete()
        invite = UserInvite.create_for_user(target)

        try:
            link = send_reset_link_or_return(target, invite.token, request)
        except Exception as e:
            log.exception("Erro ao reenviar invite (user=%s): %s", target.pk, e)
            link = None

        if link:
            messages.info(request, "Email is not configured. Copy this link and send it manually.")
            return render(
                request,
                self.template_name_copy,
                {"user_created": target, "reset_link": link},
            )

        messages.success(request, "Invitation re-sent.")
        return _safe_redirect(request, default_name="gitea_users")


# =========================================================
# Delete user (Django + Gitea handled by signal)
# =========================================================

class UserDeleteView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, user_id: int) -> HttpResponse:
        if not request.user.can_delete_users:
            return HttpResponseForbidden("Forbidden")

        user = get_object_or_404(User, pk=user_id)

        # somente admin pode remover admin
        if user.is_admin() and not request.user.is_admin():
            messages.error(request, "Only admins can delete admin users.")
            return redirect("gitea_users")

        user.delete()
        messages.success(request, "User deleted.")
        return redirect("gitea_users")


# =========================================================
# Admin/Manager editam qualquer usuário — usa AdminUserForm
# =========================================================

class UserEditView(LoginRequiredMixin, View):
    template_name = "accounts/user_edit.html"

    def get(self, request: HttpRequest, user_id: int) -> HttpResponse:
        if not request.user.can_manage_users:
            return HttpResponseForbidden("Forbidden")

        target = get_object_or_404(User, pk=user_id)
        form = AdminUserForm(instance=target, request=request)
        return render(request, self.template_name, {"form": form, "target": target})

    def post(self, request: HttpRequest, user_id: int) -> HttpResponse:
        if not request.user.can_manage_users:
            return HttpResponseForbidden("Forbidden")

        target = get_object_or_404(User, pk=user_id)
        form = AdminUserForm(request.POST, instance=target, request=request)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "target": target})

        form.save()
        messages.success(request, "User updated.")
        return redirect("gitea_users")


# =========================================================
# Simple dashboard placeholder
# =========================================================

class DashboardView(LoginRequiredMixin, View):
    template_name = "accounts/dashboard.html"

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return render(request, self.template_name)
