from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from accounts.models import PlatformSetting, User

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
            "default_language": forms.Select(attrs={"class": BASE_INPUT_CLASSES}),
            "default_timezone": forms.TextInput(
                attrs={
                    "class": BASE_INPUT_CLASSES,
                    "placeholder": _("America/Sao_Paulo"),
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
