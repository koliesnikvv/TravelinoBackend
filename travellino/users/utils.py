from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def validate_password_strength(password):
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(char.isdigit() for char in password):
        return "Password must contain at least one digit."
    if password.isdigit():
        return "Password cannot be entirely numeric."
    return None


def send_password_reset_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_link = f"http://localhost:3000/reset-password/{uid}/{token}/"

    send_mail(
        subject='Reset your password',
        message=f'Click the link to reset your password: {reset_link}',
        from_email='noreply@yoursite.com',
        recipient_list=[user.email],
        fail_silently=False,
    )