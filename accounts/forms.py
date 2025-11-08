# accounts/forms.py
from django import forms
from .models import User

class UserCreateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "role",
            "gitea_full_name",
            "gitea_visibility",
        ]

    def __init__(self, *args, **kwargs):
        # opcional: aplica classes padrão (assim você pode até dispensar o filtro no template)
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if widget.__class__.__name__.lower().endswith("select"):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    def clean_role(self):
        role = self.cleaned_data["role"]
        request = getattr(self, "request", None)
        if request and request.user.is_manager() and role == User.ROLE_ADMIN:
            raise forms.ValidationError("Managers cannot create admin users.")
        return role


class PasswordSetupForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            raise forms.ValidationError("Passwords do not match.")
        return data


class SelfProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "gitea_full_name",
            "gitea_website",
            "gitea_location",
            "gitea_description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            widget = field.widget
            if widget.__class__.__name__.lower().endswith("select"):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class AdminUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name", "last_name",
            "email",
            "role",
            "is_active",
            "gitea_full_name", "gitea_website", "gitea_location", "gitea_description",
            "gitea_visibility", "gitea_max_repo_creation",
            "gitea_allow_create_organization", "gitea_allow_git_hook",
            "gitea_allow_import_local", "gitea_restricted", "gitea_prohibit_login",
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # styling padrão
        for _, field in self.fields.items():
            widget = field.widget
            if widget.__class__.__name__.lower().endswith("select"):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if self.request and self.request.user.is_manager() and role == User.ROLE_ADMIN:
            raise forms.ValidationError("Managers cannot assign Admin role.")
        return role

    def clean(self):
        data = super().clean()
        target = self.instance
        if self.request and self.request.user.is_manager() and target.is_superuser:
            raise forms.ValidationError("Managers cannot modify superuser accounts.")
        return data
