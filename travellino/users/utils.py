from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def send_password_reset_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_link = f"http://localhost:5173/reset-password/{uid}/{token}/"

    send_mail(
        subject='Reset your password',
        message=f'Click the link to reset your password: {reset_link}',
        from_email='noreply@yoursite.com',
        recipient_list=[user.email],
        fail_silently=False,
    )
