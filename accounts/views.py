from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import UserCreateForm, PasswordSetupForm
from .models import User, UserInvite
from .services import gitea as gitea_api
from .utils import send_reset_link_or_return


# =========================================================
# Helpers
# =========================================================

def _safe_redirect(request: HttpRequest, default_name: str) -> HttpResponse:
    """
    Redirects to ?next= if safe (same host), otherwise to named URL.
    """
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect(reverse(default_name))


def _forbidden() -> HttpResponse:
    return HttpResponseForbidden("Forbidden")


# =========================================================
# Auth (Sign in / Sign out)
# =========================================================

class SignInView(LoginView):
    """
    Simple username/password login. No self-signup.
    """
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        # After login, land on the Gitea users list by default
        return reverse_lazy("gitea_users")


class SignOutView(LoginRequiredMixin, View):
    """
    Logout strictly via POST to avoid CSRF-prone GET.
    If GET is used, render a tiny confirmation with a POST form.
    """
    template_name_get = "accounts/logout_confirm.html"

    def post(self, request: HttpRequest) -> HttpResponse:
        from django.contrib.auth import logout
        logout(request)
        messages.success(request, "You have been signed out.")
        return redirect(reverse("login"))

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name_get, {})


# =========================================================
# Gitea Users (read-only list pulled from Gitea API)
# =========================================================

class GiteaUserListView(LoginRequiredMixin, View):
    """
    Read-only list of users from Gitea (via your gitea_api service).
    """
    template_name = "accounts/gitea_users.html"

    def get(self, request: HttpRequest) -> HttpResponse:
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
# User Creation (Admin/Manager) → token email (or copy link)
# =========================================================

class UserCreateView(LoginRequiredMixin, View):
    """
    Admin or Manager can create users.
    Managers CANNOT create Admin users.
    The new user is inactive with an unusable password.
    We then create a one-time invite token and either:
      - Send email (if SMTP configured), or
      - Show a copyable link (fallback).
    """
    template_name = "accounts/user_create.html"
    template_success_fallback = "accounts/user_create_success.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if not (request.user.can_manage_users):
            return _forbidden()

        form = UserCreateForm()
        form.request = request  # allow form to enforce manager cannot create admin
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        if not (request.user.can_manage_users):
            return _forbidden()

        form = UserCreateForm(request.POST)
        form.request = request
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        # Build user in inactive state with unusable password
        user: User = form.save(commit=False)
        user.is_active = False
        user.username = user.username or user.email.split("@")[0]
        user.set_unusable_password()
        user.save()

        # Create one-time invite token
        invite = UserInvite.create_for_user(user)

        # Try to send e-mail; if not configured, return link for copy
        link = send_reset_link_or_return(user, invite.token, request)
        if link:
            return render(
                request,
                self.template_success_fallback,
                {"user_created": user, "reset_link": link},
            )

        messages.success(request, "User created and reset link sent by email.")
        return _safe_redirect(request, default_name="gitea_users")


# =========================================================
# Forgot Password (public for any user)
# =========================================================

class ForgotPasswordView(View):
    """
    Collects the user's email and sends the same token link used for activation.
    If email isn't configured, shows a copyable link (for dev/demo).
    """
    template_name = "accounts/forgot_password.html"
    template_done_copy = "accounts/forgot_password_done.html"
    template_done_sent = "accounts/forgot_password_sent.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        email = (request.POST.get("email") or "").strip().lower()
        if not email:
            return render(request, self.template_name, {"error": "Email is required."})

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # You may prefer a generic message to avoid enumeration
            return render(request, self.template_name, {"error": "No account found for this email."})

        invite = getattr(user, "invite", None)
        # Replace any previous token for simplicity
        if invite:
            invite.delete()
        invite = UserInvite.create_for_user(user)

        link = send_reset_link_or_return(user, invite.token, request)
        if link:
            return render(request, self.template_done_copy, {"reset_link": link})

        return render(request, self.template_done_sent)


# =========================================================
# Password Reset / Activation (via token)
# =========================================================

class PasswordResetConfirmView(View):
    """
    Single form for both: new-user activation and password reset.
    Uses the one-time token (UserInvite).
    """
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
        user.set_password(form.cleaned_data["password1"])
        user.is_active = True  # covers the new-user activation case
        user.save()

        # Consume token (one-time)
        invite.delete()

        # Auto-login after setting password
        login(request, user)
        messages.success(request, "Password updated. Welcome!")
        return _safe_redirect(request, default_name="gitea_users")


# =========================================================
# Optional: Resend invite (Admin/Manager)
# =========================================================

class ResendInviteView(LoginRequiredMixin, View):
    """
    Regenerates a fresh token and re-sends the email (or shows link).
    Managers cannot resend for Admin accounts (no escalation).
    """
    template_name_copy = "accounts/user_create_success.html"

    def post(self, request: HttpRequest, user_id: int) -> HttpResponse:
        if not (request.user.can_manage_users):
            return _forbidden()

        target = get_object_or_404(User, pk=user_id)

        # Managers cannot operate on Admin accounts
        if request.user.is_manager() and target.is_admin():
            messages.error(request, "Managers cannot resend admin invitations.")
            return _safe_redirect(request, default_name="gitea_users")

        # Replace existing invite
        existing = getattr(target, "invite", None)
        if existing:
            existing.delete()
        invite = UserInvite.create_for_user(target)

        link = send_reset_link_or_return(target, invite.token, request)
        if link:
            # show copy UI if email isn't configured
            messages.info(request, "Email is not configured. Copy this link and send it manually.")
            return render(
                request,
                self.template_name_copy,
                {"user_created": target, "reset_link": link},
            )

        messages.success(request, "Invitation re-sent.")
        return _safe_redirect(request, default_name="gitea_users")


class UserDeleteView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, user_id: int) -> HttpResponse:
        if not request.user.can_delete_users:
            return HttpResponseForbidden("Forbidden")

        user = get_object_or_404(User, pk=user_id)

        # don't allow deleting admins unless request.user is admin
        if user.is_admin() and not request.user.is_admin():
            messages.error(request, "Only admins can delete admin users.")
            return redirect("gitea_users")

        user.delete()
        messages.success(request, "User deleted.")
        return redirect("gitea_users")
class DashboardView(LoginRequiredMixin, View):
    template_name = "accounts/dashboard.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)