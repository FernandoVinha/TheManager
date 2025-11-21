
# ============================================================================
# accounts/urls.py
# ============================================================================
from django.urls import path

from .views import (
    SignInView, SignOutView,
    UsersEntryView, ProfileView, GiteaUserListView,
    UserCreateView, ResendInviteView, UserDeleteView,
    ForgotPasswordView, PasswordResetConfirmView,
    UserEditView,
    DashboardView,
)

urlpatterns = [
    # Auth
    path("", SignInView.as_view(), name="login"),
    path("logout/", SignOutView.as_view(), name="logout"),

    # Landing pós-login
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    # Entrada inteligente "Users"
    path("users/", UsersEntryView.as_view(), name="users"),

    # Perfil (self-edit)
    path("profile/", ProfileView.as_view(), name="profile"),

    # Lista do Gitea (somente admin/manager)
    path("gitea/users/", GiteaUserListView.as_view(), name="gitea_users"),

    # CRUD auxiliar
    path("users/create/", UserCreateView.as_view(), name="user_create"),
    path("users/<int:user_id>/edit/", UserEditView.as_view(), name="user_edit"),
    path("users/<int:user_id>/delete/", UserDeleteView.as_view(), name="user_delete"),
    path("users/<int:user_id>/resend/", ResendInviteView.as_view(), name="user_resend_invite"),

    # Password reset/convite
    path("forgot/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset/<str:token>/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
