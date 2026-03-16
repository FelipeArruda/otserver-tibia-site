from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username: str) -> "User":
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})

    def _create_user(
        self, email: str, password: str | None, **extra_fields: object
    ) -> "User":
        if not email:
            raise ValueError("The Email must be set")

        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), primary_key=True)
    preferred_language = models.CharField(
        max_length=10,
        choices=[
            ("en", "English"),
            ("pt-br", "Portuguese (Brazil)"),
        ],
        blank=True,
        default="",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    objects = UserManager()

    def __str__(self) -> str:
        return self.email


class PlatformSetting(models.Model):
    singleton_id = 1

    platform_name = models.CharField(max_length=120, default="OTServ Control Panel")
    default_language = models.CharField(
        max_length=10,
        choices=[
            ("en", "English"),
            ("pt-br", "Portuguese (Brazil)"),
        ],
        default="en",
    )
    default_timezone = models.CharField(max_length=64, default="UTC")
    primary_color = models.CharField(
        max_length=7,
        default="#06b6d4",
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="Use a valid hex color, e.g. #06b6d4.",
            )
        ],
    )
    logo_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Platform setting")
        verbose_name_plural = _("Platform settings")

    def save(self, *args: object, **kwargs: object) -> None:
        self.pk = self.singleton_id
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> "PlatformSetting":
        obj, _ = cls.objects.get_or_create(
            pk=cls.singleton_id,
            defaults={
                "platform_name": "OTServ Control Panel",
                "default_language": "en",
                "default_timezone": "UTC",
                "primary_color": "#06b6d4",
            },
        )
        return obj


class AuditLog(models.Model):
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("Actor"),
    )
    action = models.CharField(max_length=120, verbose_name=_("Action"))
    target = models.CharField(max_length=120, verbose_name=_("Target"))
    details = models.JSONField(default=dict, blank=True, verbose_name=_("Details"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Audit log")
        verbose_name_plural = _("Audit logs")
