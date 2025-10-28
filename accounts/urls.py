from django.urls import path
from .views import LoginView, LogoutView, RegisterView, home

urlpatterns = [
    path("", LoginView.as_view(), name="login"),          # página inicial = login
    path("login/", LoginView.as_view(), name="login_alt"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("home/", home, name="home"),
]
