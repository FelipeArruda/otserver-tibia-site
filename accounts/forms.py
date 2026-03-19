from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group, Permission
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from accounts.models import OTServer, PlatformSetting, TibiaVacation, TibiaVersion, User

BASE_INPUT_CLASSES = (
    "mt-2 w-full rounded-xl border border-slate-200 bg-white/80 px-4 py-3 text-slate-800 "
    "placeholder:text-slate-400 shadow-sm outline-none transition focus:border-cyan-400 "
    "focus:ring-4 focus:ring-cyan-100"
)


class EmailAuthenticationForm(AuthenticationForm):
    input_classes = BASE_INPUT_CLASSES

    username = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(
            attrs={
                "autofocus": True,
                "autocomplete": "email",
                "placeholder": _("name@example.com"),
                "class": input_classes,
            }
        ),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["password"].widget.attrs.update(
            {
                "autocomplete": "current-password",
                "placeholder": _("Enter your password"),
                "class": self.input_classes,
            }
        )


class SignUpForm(UserCreationForm):
    input_classes = BASE_INPUT_CLASSES

    class Meta:
        model = User
        fields = ("email",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": _("name@example.com"),
                "class": self.input_classes,
            }
        )
        self.fields["password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": _("Enter your password"),
                "class": self.input_classes,
            }
        )
        self.fields["password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": _("Confirm password"),
                "class": self.input_classes,
            }
        )


class ForgotPasswordForm(PasswordResetForm):
    input_classes = BASE_INPUT_CLASSES

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": _("name@example.com"),
                "class": self.input_classes,
            }
        )


class AdminUserCreateForm(forms.ModelForm):
    input_classes = BASE_INPUT_CLASSES

    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": input_classes,
                "autocomplete": "new-password",
                "placeholder": _("Enter your password"),
            }
        ),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(
            attrs={
                "class": input_classes,
                "autocomplete": "new-password",
                "placeholder": _("Confirm password"),
            }
        ),
    )

    class Meta:
        model = User
        fields = ("email", "is_active", "is_staff", "is_superuser", "groups")
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": BASE_INPUT_CLASSES,
                    "autocomplete": "email",
                    "placeholder": _("name@example.com"),
                }
            ),
            "groups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = Group.objects.order_by("name")

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("The two password fields didn't match."))
        return cleaned_data

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class AdminUserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email", "is_active", "is_staff", "is_superuser", "groups")
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": AdminUserCreateForm.input_classes,
                    "placeholder": _("name@example.com"),
                    "autocomplete": "email",
                }
            ),
            "groups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = Group.objects.order_by("name")


class PlatformSettingForm(forms.ModelForm):
    FALLBACK_TIMEZONES = (
        "UTC",
        "America/Sao_Paulo",
        "America/New_York",
        "Europe/London",
    )
    default_language = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
    )
    default_timezone = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
    )

    class Meta:
        model = PlatformSetting
        fields = (
            "platform_name",
            "default_language",
            "default_timezone",
            "primary_color",
            "logo_url",
        )
        widgets = {
            "platform_name": forms.TextInput(
                attrs={
                    "class": BASE_INPUT_CLASSES,
                    "placeholder": _("OTServ Control Panel"),
                }
            ),
            "primary_color": forms.TextInput(
                attrs={
                    "class": BASE_INPUT_CLASSES,
                    "placeholder": "#06b6d4",
                }
            ),
            "logo_url": forms.URLInput(
                attrs={
                    "class": BASE_INPUT_CLASSES,
                    "placeholder": _("https://example.com/logo.png"),
                }
            ),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["platform_name"].label = _("Platform name")
        self.fields["default_language"].label = _("Default language")
        self.fields["default_language"].choices = [
            ("en", _("English")),
            ("pt-br", _("Portuguese (Brazil)")),
        ]
        self.fields["default_timezone"].label = _("Default timezone")
        current_timezone = self.instance.default_timezone
        if not current_timezone:
            current_timezone = "UTC"
        timezone_choices = self._build_timezone_choices()
        if current_timezone and current_timezone not in {
            value for value, _label in timezone_choices
        }:
            timezone_choices.insert(0, (current_timezone, current_timezone))
        self.fields["default_timezone"].choices = timezone_choices
        if not self.initial.get("default_timezone"):
            self.initial["default_timezone"] = current_timezone
        self.fields["primary_color"].label = _("Primary color")
        self.fields["logo_url"].label = _("Logo URL")

    def clean_default_timezone(self) -> str:
        timezone_name = self.cleaned_data["default_timezone"]
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise forms.ValidationError(_("Select a valid timezone.")) from exc
        return timezone_name

    @classmethod
    def _build_timezone_choices(cls) -> list[tuple[str, str]]:
        try:
            timezone_names = sorted(available_timezones())
        except Exception:
            timezone_names = []
        if not timezone_names:
            timezone_names = list(cls.FALLBACK_TIMEZONES)
        return [(timezone_name, timezone_name) for timezone_name in timezone_names]


class RoleManagementForm(forms.ModelForm):
    input_classes = BASE_INPUT_CLASSES

    permissions = forms.ModelMultipleChoiceField(
        label=_("Permissions"),
        required=False,
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
    )
    members = forms.ModelMultipleChoiceField(
        label=_("Members"),
        required=False,
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = Group
        fields = ("name", "permissions")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": BASE_INPUT_CLASSES,
                    "placeholder": _("Role name"),
                }
            )
        }

    def __init__(
        self, *args: object, can_manage_members: bool = False, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = Permission.objects.select_related(
            "content_type"
        ).order_by("content_type__app_label", "name")
        self.fields["members"].queryset = User.objects.order_by("email")
        self.fields["name"].label = _("Role name")

        if self.instance.pk:
            self.fields["permissions"].initial = self.instance.permissions.all()
            self.fields["members"].initial = self.instance.user_set.all()

        if not can_manage_members:
            del self.fields["members"]

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        existing = Group.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(_("A role with this name already exists."))
        return name

    def save(self, commit: bool = True) -> Group:
        role = super().save(commit=commit)
        role.permissions.set(self.cleaned_data.get("permissions", []))
        members = self.cleaned_data.get("members")
        if members is not None:
            role.user_set.set(members)
        return role


class OTServerForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
    )
    db_password = forms.CharField(
        label=_("Database password"),
        required=True,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Keep current password"),
            },
        ),
    )
    api_token = forms.CharField(
        label=_("API token"),
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Keep current token"),
            },
        ),
    )
    players_table = forms.CharField(
        label=_("Players table"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. players)"),
            }
        ),
    )
    deaths_table = forms.CharField(
        label=_("Deaths table"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. player_deaths)"),
            }
        ),
    )
    player_id_column = forms.CharField(
        label=_("Player ID column"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. id)"),
            }
        ),
    )
    player_group_id_column = forms.CharField(
        label=_("Player group ID column"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. group_id)"),
            }
        ),
    )
    death_player_id_column = forms.CharField(
        label=_("Death player ID column"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. player_id)"),
            }
        ),
    )
    death_time_column = forms.CharField(
        label=_("Death time column"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. time)"),
            }
        ),
    )
    death_level_column = forms.CharField(
        label=_("Death level column"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. level)"),
            }
        ),
    )
    death_killer_column = forms.CharField(
        label=_("Death killer column"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": BASE_INPUT_CLASSES,
                "placeholder": _("Auto-detect (e.g. killed_by)"),
            }
        ),
    )

    class Meta:
        model = OTServer
        fields = (
            "name",
            "tibia_version",
            "environment",
            "database_engine",
            "db_host",
            "db_port",
            "db_name",
            "db_user",
            "db_password",
            "db_charset",
            "db_collation",
            "db_use_ssl",
            "api_base_url",
            "api_token",
            "timezone",
            "monitor_enabled",
            "monitor_interval_minutes",
            "is_active",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "tibia_version": forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
            "environment": forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
            "database_engine": forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
            "db_host": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "db_port": forms.NumberInput(attrs={"class": BASE_INPUT_CLASSES, "min": 1}),
            "db_name": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "db_user": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "db_charset": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "db_collation": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "db_use_ssl": forms.CheckboxInput(attrs={"class": "peer sr-only"}),
            "api_base_url": forms.URLInput(attrs={"class": BASE_INPUT_CLASSES}),
            "monitor_enabled": forms.CheckboxInput(attrs={"class": "peer sr-only"}),
            "monitor_interval_minutes": forms.NumberInput(
                attrs={"class": BASE_INPUT_CLASSES, "min": 1, "max": 1440}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "peer sr-only"}),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        schema_mapping = {}
        if self.instance.pk and isinstance(self.instance.schema_mapping, dict):
            schema_mapping = self.instance.schema_mapping

        self.fields["timezone"].choices = PlatformSettingForm._build_timezone_choices()

        self.fields["environment"].label = _("Environment")
        self.fields["tibia_version"].label = _("Tibia version")
        self.fields["tibia_version"].required = False
        self.fields["tibia_version"].queryset = TibiaVersion.objects.filter(
            is_supported=True
        ).order_by("sort_order", "code")
        self.fields["tibia_version"].empty_label = None
        self.fields["tibia_version"].initial = TibiaVersion.DEFAULT_CODE
        self.fields["database_engine"].label = _("Database engine")
        self.fields["db_host"].label = _("Database host")
        self.fields["db_port"].label = _("Database port")
        self.fields["db_name"].label = _("Database name")
        self.fields["db_user"].label = _("Database user")
        self.fields["db_charset"].label = _("Database charset")
        self.fields["db_collation"].label = _("Database collation")
        self.fields["db_use_ssl"].label = _("Use SSL")
        self.fields["api_base_url"].label = _("API base URL")
        self.fields["monitor_enabled"].label = _("Monitoring enabled")
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")
        self.fields["monitor_interval_minutes"].label = (
            "Intervalo de monitoramento (minutos)"
            if is_pt
            else "Monitoring interval (minutes)"
        )
        self.fields["monitor_interval_minutes"].required = False
        self.fields["monitor_interval_minutes"].initial = (
            self.instance.monitor_interval_minutes or 5 if self.instance.pk else 5
        )
        self.fields["is_active"].label = _("Active")
        self.fields["players_table"].widget.attrs["list"] = "schema-table-options"
        self.fields["deaths_table"].widget.attrs["list"] = "schema-table-options"
        self.fields["player_id_column"].widget.attrs["list"] = "schema-column-options"
        self.fields["player_group_id_column"].widget.attrs["list"] = (
            "schema-column-options"
        )
        self.fields["death_player_id_column"].widget.attrs["list"] = (
            "schema-column-options"
        )
        self.fields["death_time_column"].widget.attrs["list"] = "schema-column-options"
        self.fields["death_level_column"].widget.attrs["list"] = "schema-column-options"
        self.fields["death_killer_column"].widget.attrs["list"] = (
            "schema-column-options"
        )
        self.fields["players_table"].initial = schema_mapping.get("players_table", "")
        self.fields["deaths_table"].initial = schema_mapping.get("deaths_table", "")
        self.fields["player_id_column"].initial = schema_mapping.get(
            "player_id_column", ""
        )
        self.fields["player_group_id_column"].initial = schema_mapping.get(
            "player_group_id_column", ""
        )
        self.fields["death_player_id_column"].initial = schema_mapping.get(
            "death_player_id_column", ""
        )
        self.fields["death_time_column"].initial = schema_mapping.get(
            "death_time_column", ""
        )
        self.fields["death_level_column"].initial = schema_mapping.get(
            "death_level_column", ""
        )
        self.fields["death_killer_column"].initial = schema_mapping.get(
            "death_killer_column", ""
        )
        self.fields["players_table"].label = (
            "Tabela de players" if is_pt else "Players table"
        )
        self.fields["deaths_table"].label = (
            "Tabela de mortes" if is_pt else "Deaths table"
        )
        self.fields["player_id_column"].label = (
            "Coluna de ID do player" if is_pt else "Player ID column"
        )
        self.fields["player_group_id_column"].label = (
            "Coluna do group ID do player" if is_pt else "Player group ID column"
        )
        self.fields["death_player_id_column"].label = (
            "Coluna de player ID nas mortes" if is_pt else "Death player ID column"
        )
        self.fields["death_time_column"].label = (
            "Coluna de data/hora da morte" if is_pt else "Death time column"
        )
        self.fields["death_level_column"].label = (
            "Coluna de level da morte" if is_pt else "Death level column"
        )
        self.fields["death_killer_column"].label = (
            "Coluna de assassino da morte" if is_pt else "Death killer column"
        )
        self.fields["players_table"].widget.attrs["placeholder"] = (
            "Detecção automática (ex.: players)"
            if is_pt
            else "Auto-detect (e.g. players)"
        )
        self.fields["deaths_table"].widget.attrs["placeholder"] = (
            "Detecção automática (ex.: player_deaths)"
            if is_pt
            else "Auto-detect (e.g. player_deaths)"
        )
        self.fields["player_id_column"].widget.attrs["placeholder"] = (
            "Detecção automática (ex.: id)" if is_pt else "Auto-detect (e.g. id)"
        )
        self.fields["death_player_id_column"].widget.attrs["placeholder"] = (
            "Detecção automática (ex.: player_id)"
            if is_pt
            else "Auto-detect (e.g. player_id)"
        )
        self.fields["death_time_column"].widget.attrs["placeholder"] = (
            "Detecção automática (ex.: time)" if is_pt else "Auto-detect (e.g. time)"
        )
        self.fields["death_level_column"].widget.attrs["placeholder"] = (
            "Detecção automática (ex.: level)" if is_pt else "Auto-detect (e.g. level)"
        )
        self.fields["death_killer_column"].widget.attrs["placeholder"] = (
            "Detecção automática (ex.: killed_by)"
            if is_pt
            else "Auto-detect (e.g. killed_by)"
        )

        if self.instance.pk:
            self.fields["db_password"].required = False
            self.fields["db_password"].help_text = _(
                "Leave blank to keep the current password."
            )
            self.fields["api_token"].help_text = _(
                "Leave blank to keep the current token."
            )

        # Keep secret inputs filled only after explicit "test_connection" submit.
        # This allows test -> save flows without forcing users to type secrets again.
        if self.is_bound and self.data.get("action") == "test_connection":
            self.fields["db_password"].widget.render_value = True
            self.fields["api_token"].widget.render_value = True

    def clean_timezone(self) -> str:
        timezone_name = self.cleaned_data["timezone"]
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise forms.ValidationError(_("Select a valid timezone.")) from exc
        return timezone_name

    def clean_tibia_version(self) -> TibiaVersion:
        version = self.cleaned_data.get("tibia_version")
        if isinstance(version, TibiaVersion):
            return version
        return TibiaVersion.objects.get(pk=TibiaVersion.DEFAULT_CODE)

    def clean_monitor_interval_minutes(self) -> int:
        interval = self.cleaned_data.get("monitor_interval_minutes")
        if not interval:
            return 5
        return int(interval)

    def save(self, commit: bool = True) -> OTServer:
        current_server: OTServer | None = None
        if self.instance.pk:
            current_server = OTServer.objects.filter(pk=self.instance.pk).first()

        otserver = super().save(commit=False)
        if current_server is not None:
            if not self.cleaned_data.get("db_password"):
                otserver.db_password = current_server.db_password
            if not self.cleaned_data.get("api_token"):
                otserver.api_token = current_server.api_token
        otserver.schema_mapping = {
            key: str(self.cleaned_data.get(key, "")).strip()
            for key in (
                "players_table",
                "deaths_table",
                "player_id_column",
                "player_group_id_column",
                "death_player_id_column",
                "death_time_column",
                "death_level_column",
                "death_killer_column",
            )
            if str(self.cleaned_data.get(key, "")).strip()
        }
        if commit:
            otserver.save()
        return otserver


class TibiaVersionForm(forms.ModelForm):
    class Meta:
        model = TibiaVersion
        fields = ("code", "sort_order", "is_supported")
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": BASE_INPUT_CLASSES,
                    "placeholder": "15.30",
                }
            ),
            "sort_order": forms.NumberInput(
                attrs={"class": BASE_INPUT_CLASSES, "min": 0}
            ),
            "is_supported": forms.CheckboxInput(attrs={"class": "peer sr-only"}),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["code"].label = _("Version")
        self.fields["sort_order"].label = _("Sort order")
        self.fields["is_supported"].label = _("Supported")

    def clean_code(self) -> str:
        code = str(self.cleaned_data["code"]).strip()
        existing = TibiaVersion.objects.filter(code__iexact=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(
                _("A Tibia version with this code already exists.")
            )
        return code


class TibiaVacationForm(forms.ModelForm):
    class Meta:
        model = TibiaVacation
        fields = (
            "otserver",
            "vocation_id",
            "name",
            "description",
            "name_pt_br",
            "description_pt_br",
            "base_id",
            "from_voc",
            "client_id",
        )
        widgets = {
            "otserver": forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
            "vocation_id": forms.NumberInput(
                attrs={"class": BASE_INPUT_CLASSES, "min": 0}
            ),
            "name": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "description": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "name_pt_br": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "description_pt_br": forms.TextInput(attrs={"class": BASE_INPUT_CLASSES}),
            "base_id": forms.NumberInput(attrs={"class": BASE_INPUT_CLASSES, "min": 0}),
            "from_voc": forms.NumberInput(
                attrs={"class": BASE_INPUT_CLASSES, "min": 0}
            ),
            "client_id": forms.NumberInput(
                attrs={"class": BASE_INPUT_CLASSES, "min": 0}
            ),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["otserver"].queryset = OTServer.objects.select_related(
            "tibia_version"
        ).order_by("name")
        self.fields["otserver"].empty_label = None
        language = (translation.get_language() or "").lower()
        if language.startswith("pt"):
            self.fields["otserver"].label = "OTServer"
            self.fields["vocation_id"].label = "ID da vocação"
            self.fields["name"].label = "Nome"
            self.fields["description"].label = "Descrição"
            self.fields["name_pt_br"].label = "Nome (Português)"
            self.fields["description_pt_br"].label = "Descrição (Português)"
            self.fields["base_id"].label = "ID base"
            self.fields["from_voc"].label = "Vocação de origem"
            self.fields["client_id"].label = "ID do cliente"

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        otserver = cleaned_data.get("otserver")
        vocation_id = cleaned_data.get("vocation_id")
        if not otserver or vocation_id is None:
            return cleaned_data

        duplicate = TibiaVacation.objects.filter(
            otserver=otserver,
            vocation_id=vocation_id,
        )
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            language = (translation.get_language() or "").lower()
            message = (
                "Já existe uma vocação com este ID para o OTServer selecionado."
                if language.startswith("pt")
                else "A vocation with this ID already exists for the selected OTServer."
            )
            self.add_error("vocation_id", message)
        return cleaned_data
