# projects/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("thumb", "name", "manager", "methodology", "created_at")
    list_filter = ("methodology", "created_at")
    search_fields = ("name", "description", "manager__email")
    readonly_fields = ("created_at", "updated_at", "slug", "manager")

    def thumb(self, obj):
        url = obj.image.url if obj.image else "https://placehold.co/80x45?text=IMG"
        return format_html('<img src="{}" style="height:45px;border-radius:6px;" />', url)
    thumb.short_description = "Imagem"
