import base64
import logging
import os

import httpx
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from users.models import UserProfile
from users.serializers import RegisterSerializer, CustomUser, ProfileSerializer, CustomTokenObtainPairSerializer, UserProfileSerializer
from .utils import send_password_reset_email, validate_password_strength
from users.serializers import ALLOWED_PREFERENCES

logger = logging.getLogger('users')

User = get_user_model()

IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save()

                user.send_verification_email(request)
            except Exception as e:
                logger.error(f"Registration failed: {e}")
                return Response(
                    {'error': 'Registration failed. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            return Response(
                {'message': 'Registration successful. Please check your email to verify your account.'},
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return redirect("http://localhost:3000/email-error")

        if default_token_generator.check_token(user, token):
            user.is_email_verified = True
            user.is_active = True
            user.save()
            return redirect("http://localhost:3000/email-confirmed")
        else:
            return redirect("http://localhost:3000/email-error")


class LoginView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'error': 'Enter both email and password'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email, password=password)

        if user is None:
            return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_email_verified:
            return Response({'error': 'Email not verified'}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
            }
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info("Logout attempt received")
        try:
            refresh = request.data['refresh']
            token = RefreshToken(refresh)
            token.blacklist()
            logger.info(f"User logged out successfully: {refresh}")
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class ProtectedAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        logger.info(f"Protected view accessed by: {request.user.first_name} {request.user.last_name}")
        return Response({
            'message': 'This is a protected view',
            'user': request.user.first_name}, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            send_password_reset_email(user)
        except User.DoesNotExist:
            pass
        return Response({'message': 'If this email is registered, you will receive a reset link.'})


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, uid, token):
        new_password = request.data.get('new_password')

        if not new_password:
            return Response({'error': 'New password is required.'}, status=status.HTTP_400_BAD_REQUEST)

        error = validate_password_strength(new_password)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'message': 'Password reset successful.'}, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProfileSerializer(request.user).data)

    def delete(self, request):
        password = request.data.get('password')
        if not password:
            return Response(
                {'error': 'Password is required to delete account.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not request.user.check_password(password):
            return Response(
                {'error': 'Invalid password.'},
                status=status.HTTP_403_FORBIDDEN
            )
        request.user.delete()
        return Response({"message": "Account deleted"}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response(
                {'error': 'Both current and new password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not request.user.check_password(current_password):
            return Response(
                {'error': 'Current password is incorrect.'},
                status=status.HTTP_403_FORBIDDEN
            )

        error = validate_password_strength(new_password)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        if current_password == new_password:
            return Response(
                {'error': 'New password must be different from current password.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.user.set_password(new_password)
        request.user.save()
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class UserPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request):
        profile = UserProfile.objects.get(user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PreferencesOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'preferences': ALLOWED_PREFERENCES})


class UploadPhotoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('photo')
        if not file:
            return Response({'error': 'No photo provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check file type
        content_type = file.content_type
        if content_type not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif'):
            return Response({'error': 'Unsupported file type. Use JPEG, PNG, WEBP or GIF.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check file size — max 5MB
        if file.size > 5 * 1024 * 1024:
            return Response({'error': 'File too large. Max 5MB.'}, status=status.HTTP_400_BAD_REQUEST)

        # Encode to base64 for imgbb
        image_data = base64.b64encode(file.read()).decode('utf-8')

        try:
            resp = httpx.post(
                'https://api.imgbb.com/1/upload',
                data={
                    'key': IMGBB_API_KEY,
                    'image': image_data,
                    'name': f'user_{request.user.id}_photo',
                },
                timeout=15,
            )
            resp.raise_for_status()
            url = resp.json()['data']['url']
        except Exception as e:
            logger.error(f'imgbb upload error for user {request.user.id}: {e}')
            return Response({'error': 'Failed to upload image. Try again.'}, status=status.HTTP_502_BAD_GATEWAY)

        # Save URL to profile
        profile = UserProfile.objects.get(user=request.user)
        profile.photo = url
        profile.save()

        return Response({'photo': url}, status=status.HTTP_200_OK)