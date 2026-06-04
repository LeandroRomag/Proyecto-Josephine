from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        UserModel = get_user_model()
        identifier = (email or kwargs.get('identifier') or '').strip()

        if not identifier or not password:
            return None

        candidates = UserModel.objects.filter(email__iexact=identifier)

        for user in candidates:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None