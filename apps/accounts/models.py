from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Users log in with their email; ``display_name`` is what other bidders see."""

    username = None
    email = models.EmailField("email address", unique=True)
    display_name = models.CharField(max_length=40, unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    objects = UserManager()

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.display_name or self.email

    @property
    def masked_name(self) -> str:
        """Partially hidden name shown in public bid histories, e.g. ``j***e``."""
        name = self.display_name
        if len(name) <= 2:
            return name[0] + "*"
        return f"{name[0]}***{name[-1]}"
