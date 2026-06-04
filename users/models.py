from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.email or self.get_full_name() or f'User {self.pk}'
