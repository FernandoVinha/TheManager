# accounts/templatetags/form_extras.py
from django import template
from django.forms.boundfield import BoundField

register = template.Library()

@register.filter
def add_class(field, css):
    """
    Uso: {{ form.campo|add_class:"form-control" }}
    Se 'field' não for BoundField (ex: veio string por engano), retorna como está.
    """
    if not isinstance(field, BoundField):
        return field  # evita AttributeError

    widget = field.field.widget
    attrs = widget.attrs.copy()

    # mescla classes sem duplicar
    current = (attrs.get("class") or "").split()
    to_add = (css or "").split()
    final = list(dict.fromkeys([*current, *to_add]))  # remove duplicatas, mantém ordem

    attrs["class"] = " ".join(c for c in final if c)
    return field.as_widget(attrs=attrs)
