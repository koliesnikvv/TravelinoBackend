from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView, LoginView, LogoutView, ProtectedAPIView,
    VerifyEmailView, ForgotPasswordView, ResetPasswordView,
    ProfileView, CustomTokenObtainPairView, ChangePasswordView,
    UserPreferencesView, PreferencesOptionsView
)

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('protected/', ProtectedAPIView.as_view(), name='protected'),
    path('verify-email/<uidb64>/<token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/<uid>/<token>/', ResetPasswordView.as_view(), name='reset-password'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('profile/preferences/', UserPreferencesView.as_view(), name='preferences'),
    path('profile/preferences/options/', PreferencesOptionsView.as_view(), name='preferences-options'),
]