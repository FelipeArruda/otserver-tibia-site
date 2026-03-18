from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.secrets import decrypt_secret, encrypt_secret


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


class TibiaVersion(models.Model):
    DEFAULT_CODE = "15.30"

    code = models.CharField(max_length=10, primary_key=True, verbose_name=_("Version"))
    sort_order = models.PositiveIntegerField(default=0)
    is_supported = models.BooleanField(default=True, verbose_name=_("Supported"))

    class Meta:
        ordering = ["sort_order", "code"]
        verbose_name = _("Tibia version")
        verbose_name_plural = _("Tibia versions")

    def __str__(self) -> str:
        return self.code


class OTServer(models.Model):
    class Environment(models.TextChoices):
        PRODUCTION = "production", _("Production")
        STAGING = "staging", _("Staging")
        DEVELOPMENT = "development", _("Development")

    class DatabaseEngine(models.TextChoices):
        MYSQL = "mysql", "MySQL"
        MARIADB = "mariadb", "MariaDB"

    name = models.CharField(max_length=120, unique=True, verbose_name=_("Name"))
    tibia_version = models.ForeignKey(
        TibiaVersion,
        on_delete=models.PROTECT,
        related_name="otservers",
        default=TibiaVersion.DEFAULT_CODE,
        verbose_name=_("Tibia version"),
    )
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.PRODUCTION,
        verbose_name=_("Environment"),
    )
    database_engine = models.CharField(
        max_length=20,
        choices=DatabaseEngine.choices,
        default=DatabaseEngine.MYSQL,
        verbose_name=_("Database engine"),
    )
    db_host = models.CharField(max_length=255, verbose_name=_("Database host"))
    db_port = models.PositiveIntegerField(default=3306, verbose_name=_("Database port"))
    db_name = models.CharField(max_length=128, verbose_name=_("Database name"))
    db_user = models.CharField(max_length=128, verbose_name=_("Database user"))
    db_password = models.TextField(verbose_name=_("Database password"))
    db_charset = models.CharField(
        max_length=64,
        default="utf8mb4",
        verbose_name=_("Database charset"),
    )
    db_collation = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_("Database collation"),
    )
    db_use_ssl = models.BooleanField(default=False, verbose_name=_("Use SSL"))
    api_base_url = models.URLField(blank=True, verbose_name=_("API base URL"))
    api_token = models.TextField(blank=True, verbose_name=_("API token"))
    timezone = models.CharField(
        max_length=64, default="UTC", verbose_name=_("Timezone")
    )
    monitor_enabled = models.BooleanField(
        default=True, verbose_name=_("Monitoring enabled")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("OTServer")
        verbose_name_plural = _("OTServers")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.db_password:
            self.db_password = encrypt_secret(self.db_password)
        if self.api_token:
            self.api_token = encrypt_secret(self.api_token)
        super().save(*args, **kwargs)

    def get_db_password(self) -> str:
        return decrypt_secret(self.db_password)

    def get_api_token(self) -> str:
        return decrypt_secret(self.api_token)

    def __str__(self) -> str:
        return self.name


class TibiaVacation(models.Model):
    tibia_version = models.ForeignKey(
        TibiaVersion,
        on_delete=models.PROTECT,
        related_name="tibia_vacations",
        verbose_name=_("Tibia version"),
    )
    vocation_id = models.PositiveSmallIntegerField(verbose_name=_("Vocation ID"))
    name = models.CharField(max_length=120, verbose_name=_("Name"))
    description = models.CharField(
        max_length=255, blank=True, verbose_name=_("Description")
    )
    name_pt_br = models.CharField(
        max_length=120, blank=True, verbose_name=_("Name (Portuguese)")
    )
    description_pt_br = models.CharField(
        max_length=255, blank=True, verbose_name=_("Description (Portuguese)")
    )
    base_id = models.PositiveSmallIntegerField(default=0, verbose_name=_("Base ID"))
    from_voc = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("From vocation")
    )
    client_id = models.PositiveSmallIntegerField(default=0, verbose_name=_("Client ID"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))

    class Meta:
        db_table = "tibia_vacations"
        ordering = ["tibia_version_id", "vocation_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tibia_version", "vocation_id"],
                name="uniq_tibia_vacation_per_version",
            )
        ]
        verbose_name = _("Tibia vacation")
        verbose_name_plural = _("Tibia vacations")

    def __str__(self) -> str:
        return f"{self.tibia_version_id} #{self.vocation_id} - {self.name}"
