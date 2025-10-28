#accounts/views.py
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView
from .forms import EmailAuthenticationForm, SimpleUserCreationForm

# Login é a página inicial ("/")
class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True  # se já estiver logado, manda para /home (ajuste abaixo)

    def get_success_url(self):
        return reverse_lazy("home")  # crie uma view /home depois; por ora pode apontar para /admin/ se preferir


class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy("login")


class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = SimpleUserCreationForm
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Conta criada! Aguarde um gerente atribuir sua permissão. Faça login para continuar.")
        return super().form_valid(form)


# Exemplo de home simples (temporária) só para testar pós-login
@login_required
def home(request):
    return render(request, "accounts/home_placeholder.html", {})
