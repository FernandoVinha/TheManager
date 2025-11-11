# tasck/templatetags/form_extras.py
from django import template

register = template.Library()

@register.filter(name="add_class")
def add_class(field, css):
    """
    Adiciona CSS class à widget do campo e retorna o próprio BoundField.
    Uso: {{ form.meu_campo|add_class:"form-select" }}
    """
    try:
        current = field.field.widget.attrs.get("class", "")
        joined = f"{current} {css}".strip() if current else css
        field.field.widget.attrs["class"] = joined
    except Exception:
        # se algo der errado, devolve o campo sem alterar
        pass
    return field

@register.filter(name="attr")
def set_attr(field, arg):
    """
    Seta qualquer atributo na widget. Ex: {{ field|attr:"placeholder:Digite aqui" }}
    """
    try:
        key, val = arg.split(":", 1)
        field.field.widget.attrs[key] = val
    except Exception:
        pass
    return field
