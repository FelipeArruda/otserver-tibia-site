from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    UserCreationForm,
)
from django.utils.translation import gettext_lazy as _

from accounts.models import User


class EmailAuthenticationForm(AuthenticationForm):
    input_classes = (
        "mt-2 w-full rounded-xl border border-slate-200 bg-white/80 px-4 py-3 text-slate-800 "
        "placeholder:text-slate-400 shadow-sm outline-none transition focus:border-cyan-400 "
        "focus:ring-4 focus:ring-cyan-100"
    )

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
    input_classes = (
        "mt-2 w-full rounded-xl border border-slate-200 bg-white/80 px-4 py-3 text-slate-800 "
        "placeholder:text-slate-400 shadow-sm outline-none transition focus:border-cyan-400 "
        "focus:ring-4 focus:ring-cyan-100"
    )

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
    input_classes = (
        "mt-2 w-full rounded-xl border border-slate-200 bg-white/80 px-4 py-3 text-slate-800 "
        "placeholder:text-slate-400 shadow-sm outline-none transition focus:border-cyan-400 "
        "focus:ring-4 focus:ring-cyan-100"
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": _("name@example.com"),
                "class": self.input_classes,
            }
        )
