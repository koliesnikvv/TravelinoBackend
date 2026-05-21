from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import CustomTokenObtainPairView
from .views import RegisterView, LoginView, LogoutView, ProtectedAPIView, VerifyEmailView, ForgotPasswordView, \
    ResetPasswordView, ProfileView

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('protected/', ProtectedAPIView.as_view(), name='protected'),
    path('verify-email/<uidb64>/<token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('email-confirmed/', VerifyEmailView.as_view(), name='email-confirme'),
    path('email-error/', VerifyEmailView.as_view(), name='email-error'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/<uid>/<token>/', ResetPasswordView.as_view(), name='reset-password'),
    path('profile/', ProfileView.as_view(), name='profile'),

]
