#system_settings/forms.py
from django import forms


# ============================================================
#  FORMULÁRIO DE E-MAIL (usa .env.email)
# ============================================================

class EmailSettingsForm(forms.Form):
    email_backend = forms.CharField(
        label="Email backend",
        initial="django.core.mail.backends.smtp.EmailBackend",
        required=True,
    )

    email_host = forms.CharField(
        label="Servidor SMTP (EMAIL_HOST)",
        initial="smtp.gmail.com",
        required=True,
    )

    email_port = forms.IntegerField(
        label="Porta (EMAIL_PORT)",
        initial=587,
        required=True,
    )

    email_use_tls = forms.BooleanField(
        label="Usar TLS (EMAIL_USE_TLS)",
        initial=True,
        required=False,
    )

    email_use_ssl = forms.BooleanField(
        label="Usar SSL (EMAIL_USE_SSL)",
        initial=False,
        required=False,
    )

    email_host_user = forms.CharField(
        label="Usuário SMTP (EMAIL_HOST_USER)",
        required=False,
    )

    email_host_password = forms.CharField(
        label="Senha SMTP (EMAIL_HOST_PASSWORD)",
        widget=forms.PasswordInput(render_value=True),
        required=False,
    )

    default_from_email = forms.CharField(
        label="DEFAULT_FROM_EMAIL",
        initial="TheManager <no-reply@example.com>",
        required=True,
    )

    server_email = forms.CharField(
        label="SERVER_EMAIL",
        required=False,
    )


# ============================================================
#  FORMULÁRIO DE GITEA (local + externo)
# ============================================================

class GiteaSettingsForm(forms.Form):

    # ---------------------------
    # MODO (Gitea externo ou local)
    # ---------------------------
    use_external_gitea = forms.BooleanField(
        label="Usar Gitea externo (não gerenciar Docker local)",
        required=False,
        help_text="Se ativado, o sistema usa um Gitea externo e ignora o Docker local.",
    )

    # ---------------------------
    # INTEGRAÇÃO BÁSICA (Django)
    # ---------------------------
    gitea_base_url = forms.CharField(
        label="GITEA_BASE_URL",
        required=False,
        help_text="URL pública do Gitea. Ex: http://meu-servidor:3000",
    )

    gitea_admin_token = forms.CharField(
        label="GITEA_ADMIN_TOKEN",
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Token admin usado pelo Django para criar usuários/repos.",
    )

    # ---------------------------------------------------------
    # CAMPOS ABAIXO são SOMENTE para quando NÃO for externo
    # (stack local usando doker/getea)
    # ---------------------------------------------------------

    # ---------------------------
    # Banco de Dados local do Gitea
    # ---------------------------
    gitea_db_name = forms.CharField(
        label="GITEA_DB_NAME",
        required=False,  # validado na clean()
        initial="gitea",
    )

    gitea_db_user = forms.CharField(
        label="GITEA_DB_USER",
        required=False,  # validado na clean()
        initial="gitea",
    )

    mysql_root_password = forms.CharField(
        label="MYSQL_ROOT_PASSWORD",
        widget=forms.PasswordInput(render_value=True),
        required=False,  # validado na clean()
        help_text="Senha root do MySQL usado pelo Gitea local.",
    )

    mysql_password = forms.CharField(
        label="MYSQL_PASSWORD",
        widget=forms.PasswordInput(render_value=True),
        required=False,  # validado na clean()
        help_text="Senha do usuário MySQL usado pelo Gitea local.",
    )

    # ---------------------------
    # Segredos internos do Gitea local
    # ---------------------------
    gitea_secret_key = forms.CharField(
        label="GITEA_SECRET_KEY",
        widget=forms.PasswordInput(render_value=True),
        required=False,  # validado na clean()
        help_text="Chave secreta usada pelo Gitea interno.",
    )

    gitea_internal_token = forms.CharField(
        label="GITEA_INTERNAL_TOKEN",
        widget=forms.PasswordInput(render_value=True),
        required=False,  # validado na clean()
        help_text="Token interno para comunicação entre serviços do Gitea.",
    )

    gitea_jwt_secret = forms.CharField(
        label="GITEA_JWT_SECRET",
        widget=forms.PasswordInput(render_value=True),
        required=False,  # validado na clean()
        help_text="Segredo JWT interno do Gitea.",
    )

    # ---------------------------
    # Admin inicial do Gitea local
    # ---------------------------
    gitea_admin_user = forms.CharField(
        label="GITEA_ADMIN_USER",
        required=False,  # validado na clean()
        help_text="Usuário admin inicial do Gitea local.",
    )

    gitea_admin_pass = forms.CharField(
        label="GITEA_ADMIN_PASS",
        widget=forms.PasswordInput(render_value=True),
        required=False,  # validado na clean()
        help_text="Senha do admin inicial.",
    )

    gitea_admin_email = forms.EmailField(
        label="GITEA_ADMIN_EMAIL",
        required=False,  # validado na clean()
        help_text="E-mail do admin inicial.",
    )

    # ---------------------------
    # Validação condicional
    # ---------------------------
    def clean(self):
        cleaned_data = super().clean()
        use_external = cleaned_data.get("use_external_gitea", False)

        # Se NÃO for externo, validar campos obrigatórios do Gitea local
        if not use_external:
            required_fields = [
                "gitea_db_name",
                "gitea_db_user",
                "mysql_root_password",
                "mysql_password",
                "gitea_secret_key",
                "gitea_internal_token",
                "gitea_jwt_secret",
                "gitea_admin_user",
                "gitea_admin_pass",
                "gitea_admin_email",
            ]

            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, "Este campo é obrigatório quando o Gitea não é externo.")

        return cleaned_data
