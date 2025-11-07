from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings

def send_reset_link_or_return(user, token, request):
    """
    If SMTP email is configured, send email.
    Otherwise return the link so the UI can display a 'copy' box.
    """
    url = request.build_absolute_uri(reverse("password_reset_confirm", args=[token]))

    subject = "Set your password — TheManager"
    message = (
        f"Hello {user.get_full_name() or user.username or user.email},\n\n"
        "Use the link below to set (or reset) your password:\n\n"
        f"{url}\n\n"
        "If you did not request this, please ignore this message."
    )

    if settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
        send_mail(subject, message, None, [user.email], fail_silently=False)
        return None  # email sent
    else:
        return url  # no email backend → show link to copy
