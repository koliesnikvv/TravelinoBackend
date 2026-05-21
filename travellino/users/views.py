import logging

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from users.serializers import RegisterSerializer, CustomUser, ProfileSerializer
from .utils import send_password_reset_email

logger = logging.getLogger('users')

User = get_user_model()



class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.send_verification_email(request)
            return Response(
                {
                    'user': RegisterSerializer(user).data,
                    'message': 'User registered successfully'
                },
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
            return redirect("http://localhost:5173/email-error")

        if default_token_generator.check_token(user, token):
            user.is_email_verified = True
            user.is_active = True
            user.save()
            return redirect("http://localhost:5173/email-confirmed")
        else:
            return redirect("http://localhost:5173/email-error")


class LoginView(APIView):
    permission_classes = []
    authentication_classes = []


def post(self, request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Enter both email and password'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        return Response({'error': 'User with this email does not exist'}, status=status.HTTP_404_NOT_FOUND)

    user = authenticate(request, email=email, password=password)

    if user is None:
        return Response({'error': 'Invalid password or email'}, status=status.HTTP_401_UNAUTHORIZED)

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
    permission_classes = (permissions.AllowAny,)

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
            return Response({'message': 'Check your email for reset link.'})
        except User.DoesNotExist:
            return Response({'error': 'User with this email does not exist.'}, status=404)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, uid, token):

        new_password = request.data.get('new_password')

        if not new_password:
            return Response({'error': 'New password is required.'}, status=status.HTTP_400_BAD_REQUEST)

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



class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data.pop('password', None)
        user = serializer.instance
        if new_password:
            user.set_password(new_password)
            user.save()
        serializer.save()
        return Response(ProfileSerializer(user).data)

    def delete(self, request):
        user = request.user
        user.delete()
        return Response({"message": "Account deleted"}, status=status.HTTP_200_)
