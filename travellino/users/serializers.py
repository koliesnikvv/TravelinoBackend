from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from users.models import UserProfile
from users.utils import validate_password_strength

CustomUser = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_check = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=True)

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'password', 'password_check']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        validate_email(value)
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value

    def validate_phone(self, value):
        if CustomUser.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone already registered.")
        return value

    def validate(self, data):
        password1 = data.get('password')
        password2 = data.get('password_check')

        if password1 != password2:
            raise serializers.ValidationError({"password_check": "Passwords don't match."})

        error = validate_password_strength(password1)
        if error:
            raise serializers.ValidationError({"password": error})

        return data

    def create(self, validated_data):
        validated_data.pop('password_check')
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(password=password, **validated_data)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email') or attrs.get('username')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError({'non_field_errors': ['Email and password required']})

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError({'non_field_errors': ['Invalid email or password']})

        if not user.check_password(password):
            raise serializers.ValidationError({'non_field_errors': ['Invalid email or password']})

        if not user.is_active:
            raise serializers.ValidationError({'non_field_errors': ['User account is disabled.']})

        data = super().validate(attrs)

        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone': self.user.phone,
        }
        return data


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name', 'phone', 'is_email_verified']
        read_only_fields = ['is_email_verified', 'email']


ALLOWED_PREFERENCES = ['beach', 'mountains', 'city']


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['photo', 'preferences']

    def validate_preferences(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Preferences must not contain duplicates.")
        invalid = [v for v in value if v not in ALLOWED_PREFERENCES]
        if invalid:
            raise serializers.ValidationError(f"Invalid preferences: {invalid}")
        return value


class UserWithProfileSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'profile']