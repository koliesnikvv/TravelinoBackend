from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

VALID_USER = {
    'first_name': 'Test',
    'last_name': 'User',
    'email': 'test@example.com',
    'phone': '+380991234567',
    'password': 'StrongPass1',
    'password_check': 'StrongPass1',
}


def make_verified_user(email='test@example.com', password='StrongPass1', phone='+380991234567'):
    """Helper: create an active, email-verified user."""
    user = User.objects.create_user(
        email=email,
        password=password,
        phone=phone,
        first_name='Test',
        last_name='User',
    )
    user.is_active = True
    user.is_email_verified = True
    user.save()
    return user


def auth_client(user):
    """Helper: return an APIClient authenticated with JWT for the given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ─────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegisterViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('users:register')

    def test_register_success(self):
        response = self.client.post(self.url, VALID_USER)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=VALID_USER['email']).exists())

    def test_register_sends_verification_email(self):
        self.client.post(self.url, VALID_USER)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(VALID_USER['email'], mail.outbox[0].to)
        self.assertIn('verify', mail.outbox[0].subject.lower())

    def test_register_user_inactive_until_verified(self):
        self.client.post(self.url, VALID_USER)
        user = User.objects.get(email=VALID_USER['email'])
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)

    def test_register_duplicate_email(self):
        self.client.post(self.url, VALID_USER)
        response = self.client.post(self.url, VALID_USER)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_register_duplicate_phone(self):
        self.client.post(self.url, VALID_USER)
        data = {**VALID_USER, 'email': 'other@example.com'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_register_passwords_dont_match(self):
        data = {**VALID_USER, 'password_check': 'WrongPass1'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password_too_short(self):
        data = {**VALID_USER, 'password': 'abc', 'password_check': 'abc'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password_no_digit(self):
        data = {**VALID_USER, 'password': 'NoDigitPass', 'password_check': 'NoDigitPass'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_invalid_phone_format(self):
        data = {**VALID_USER, 'phone': '0991234567'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_required_fields(self):
        response = self.client.post(self.url, {'email': 'x@x.com'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# Email verification
# ─────────────────────────────────────────────

class VerifyEmailViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='verify@example.com',
            password='StrongPass1',
            phone='+380991234568',
            first_name='Test',
            last_name='User',
        )

    def _make_url(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return reverse('users:verify-email', kwargs={'uidb64': uid, 'token': token})

    def test_verify_email_success(self):
        url = self._make_url(self.user)
        response = self.client.get(url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        self.assertTrue(self.user.is_active)
        self.assertRedirects(response, 'http://localhost:3000/email-confirmed',
                             fetch_redirect_response=False)

    def test_verify_email_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse('users:verify-email', kwargs={'uidb64': uid, 'token': 'invalid-token'})
        response = self.client.get(url)
        self.assertRedirects(response, 'http://localhost:3000/email-error',
                             fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_verify_email_invalid_uid(self):
        token = default_token_generator.make_token(self.user)
        url = reverse('users:verify-email', kwargs={'uidb64': 'invalid', 'token': token})
        response = self.client.get(url)
        self.assertRedirects(response, 'http://localhost:3000/email-error',
                             fetch_redirect_response=False)


# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────

class LoginViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('users:login')
        self.user = make_verified_user()

    def test_login_success(self):
        response = self.client.post(self.url, {
            'email': 'test@example.com',
            'password': 'StrongPass1',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_wrong_password(self):
        response = self.client.post(self.url, {
            'email': 'test@example.com',
            'password': 'WrongPass1',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_email(self):
        response = self.client.post(self.url, {
            'email': 'nobody@example.com',
            'password': 'StrongPass1',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_unverified_email(self):
        unverified = User.objects.create_user(
            email='unverified@example.com',
            password='StrongPass1',
            phone='+380991234569',
            first_name='Test',
            last_name='User',
        )
        response = self.client.post(self.url, {
            'email': 'unverified@example.com',
            'password': 'StrongPass1',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields(self):
        response = self.client.post(self.url, {'email': 'test@example.com'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────

class LogoutViewTests(TestCase):

    def setUp(self):
        self.url = reverse('users:logout')
        self.user = make_verified_user()

    def test_logout_success(self):
        refresh = RefreshToken.for_user(self.user)
        client = auth_client(self.user)
        response = client.post(self.url, {'refresh': str(refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_unauthenticated(self):
        client = APIClient()
        response = client.post(self.url, {'refresh': 'token'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_invalid_token(self):
        client = auth_client(self.user)
        response = client.post(self.url, {'refresh': 'invalid-token'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────
# Forgot / Reset password
# ─────────────────────────────────────────────

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ForgotPasswordViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('users:forgot-password')
        self.user = make_verified_user()

    def test_forgot_password_existing_email(self):
        response = self.client.post(self.url, {'email': 'test@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_nonexistent_email(self):
        # Should still return 200 to not leak user existence
        response = self.client.post(self.url, {'email': 'nobody@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)


class ResetPasswordViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = make_verified_user()

    def _make_url(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return reverse('users:reset-password', kwargs={'uid': uid, 'token': token})

    def test_reset_password_success(self):
        url = self._make_url(self.user)
        response = self.client.post(url, {'new_password': 'NewPass123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123'))

    def test_reset_password_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse('users:reset-password', kwargs={'uid': uid, 'token': 'bad-token'})
        response = self.client.post(url, {'new_password': 'NewPass123'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_invalid_uid(self):
        token = default_token_generator.make_token(self.user)
        url = reverse('users:reset-password', kwargs={'uid': 'invalid', 'token': token})
        response = self.client.post(url, {'new_password': 'NewPass123'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_weak_password(self):
        url = self._make_url(self.user)
        response = self.client.post(url, {'new_password': 'weak'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_missing_password(self):
        url = self._make_url(self.user)
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────

class ProfileViewTests(TestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('users:profile')

    def test_get_profile(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)

    def test_update_profile(self):
        response = self.client.put(self.url, {'first_name': 'Updated'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')

    def test_update_profile_email_readonly(self):
        response = self.client.put(self.url, {'email': 'newemail@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)

    def test_delete_account_success(self):
        response = self.client.delete(self.url, {'password': 'StrongPass1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(email=self.user.email).exists())

    def test_delete_account_wrong_password(self):
        response = self.client.delete(self.url, {'password': 'WrongPass1'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_account_missing_password(self):
        response = self.client.delete(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_unauthenticated(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────
# Change password
# ─────────────────────────────────────────────

class ChangePasswordViewTests(TestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('users:change-password')

    def test_change_password_success(self):
        response = self.client.post(self.url, {
            'current_password': 'StrongPass1',
            'new_password': 'NewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456'))

    def test_change_password_wrong_current(self):
        response = self.client.post(self.url, {
            'current_password': 'WrongPass1',
            'new_password': 'NewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_password_same_as_current(self):
        response = self.client.post(self.url, {
            'current_password': 'StrongPass1',
            'new_password': 'StrongPass1',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_weak_new(self):
        response = self.client.post(self.url, {
            'current_password': 'StrongPass1',
            'new_password': 'weak',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_missing_fields(self):
        response = self.client.post(self.url, {'current_password': 'StrongPass1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_unauthenticated(self):
        response = APIClient().post(self.url, {
            'current_password': 'StrongPass1',
            'new_password': 'NewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────
# Preferences
# ─────────────────────────────────────────────

class UserPreferencesViewTests(TestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('users:preferences')

    def test_get_preferences(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('preferences', response.data)

    def test_update_preferences_valid(self):
        response = self.client.put(self.url, {'preferences': ['museums', 'hiking']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['preferences'], ['museums', 'hiking'])

    def test_update_preferences_invalid(self):
        response = self.client.put(self.url, {'preferences': ['invalid_pref']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_preferences_duplicates(self):
        response = self.client.put(self.url, {'preferences': ['museums', 'museums']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preferences_unauthenticated(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PreferencesOptionsViewTests(TestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('users:preferences-options')

    def test_get_options(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('preferences', response.data)
        self.assertIsInstance(response.data['preferences'], list)

    def test_get_options_unauthenticated(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)