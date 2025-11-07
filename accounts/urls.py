from django.urls import path
from .views import (
    SignInView, SignOutView, GiteaUserListView,
    UserCreateView, ResendInviteView,
    ForgotPasswordView, PasswordResetConfirmView,UserDeleteView,DashboardView,
)

urlpatterns = [
    path("login/", SignInView.as_view(), name="login"),
    path("logout/", SignOutView.as_view(), name="logout"),

    path("gitea/users/", GiteaUserListView.as_view(), name="gitea_users"),

    path("users/create/", UserCreateView.as_view(), name="user_create"),
    path("users/<int:user_id>/resend-invite/", ResendInviteView.as_view(), name="resend_invite"),

    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset/<str:token>/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    path("users/<int:user_id>/delete/", UserDeleteView.as_view(), name="user_delete"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

]
