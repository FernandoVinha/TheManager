# projects/forms.py
from django import forms
from .models import Project

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "methodology", "description", "image"]  # sem "manager"
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do projeto"}),
            "methodology": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def clean_image(self):
        img = self.cleaned_data.get("image")
        # (opcional) validar tamanho/formatos
        return img


class ProjectEditForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["description", "image"]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def clean_image(self):
        img = self.cleaned_data.get("image")
        # (opcional) validar tamanho/formatos
        return img