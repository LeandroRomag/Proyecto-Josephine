from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings

from .models import User
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    PasswordResetSerializer,
    PasswordResetConfirmSerializer,
)


class UserViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {
                    'user': UserSerializer(user).data,
                    'token': token.key,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {
                    'user': UserSerializer(user).data,
                    'token': token.key,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        request.user.auth_token.delete()
        return Response({'detail': 'Sesión cerrada.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'detail': 'Contraseña cambiada correctamente.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def password_reset(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

                subject = 'Recuperar contraseña - Josephine Shop'
                message = f"""
Hola {user.first_name or user.email},

Haz clic en el siguiente enlace para recuperar tu contraseña:
{reset_url}

Si no solicitaste esto, ignora este email.
                """
                send_mail(subject, message, settings.EMAIL_FROM, [email], fail_silently=False)
                return Response({'detail': 'Email enviado.'}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({'detail': 'Email no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def password_reset_confirm(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['token']
            uid = request.data.get('uid')

            try:
                uid_decoded = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=uid_decoded)

                if default_token_generator.check_token(user, token):
                    user.set_password(serializer.validated_data['new_password'])
                    user.save()
                    return Response({'detail': 'Contraseña restablecida.'}, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'Token inválido.'}, status=status.HTTP_400_BAD_REQUEST)
            except (TypeError, ValueError, User.DoesNotExist):
                return Response({'error': 'Datos inválidos.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
