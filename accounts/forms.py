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

    def clean_role(self):
        role = self.cleaned_data["role"]
        request = self.request

        # manager cannot create admin
        if request.user.is_manager() and role == User.ROLE_ADMIN:
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
