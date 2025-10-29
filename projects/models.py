# projects/models.py
from __future__ import annotations
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

User = settings.AUTH_USER_MODEL

def project_image_upload_to(instance: "Project", filename: str) -> str:
    # Ex.: projects/42/logo/2025-10-28_filename.png
    today = timezone.now().date().isoformat()
    return f"projects/{instance.pk or 'new'}/logo/{today}_{filename}"

class Project(models.Model):
    class Methodology(models.TextChoices):
        SCRUM = "scrum", "Scrum"
        KANBAN = "kanban", "Kanban"
        XP = "xp", "Extreme Programming (XP)"

    name = models.CharField("Nome do projeto", max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, editable=False)

    # gerente (preenchido automaticamente com o usuário que cria)
    manager = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="managed_projects",
        verbose_name="Gerente do projeto",
        editable=False,  # <- não aparece em formulários/admin add
    )

    methodology = models.CharField(
        "Metodologia",
        max_length=20,
        choices=Methodology.choices,
        default=Methodology.SCRUM,
    )
    description = models.TextField("Descrição", blank=True)

    # imagem opcional
    image = models.ImageField(
        "Imagem do projeto",
        upload_to=project_image_upload_to,
        blank=True,
        null=True,
        help_text="Opcional. PNG/JPG/WebP para identificar rapidamente.",
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "projeto"
            self.slug = base
        return super().save(*args, **kwargs)

    @property
    def image_url(self) -> str:
        # placeholder se não houver imagem
        if self.image:
            return self.image.url
        # 320x180 para capa do card
        return "https://placehold.co/640x360?text=Projeto"
