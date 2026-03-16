from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, TemplateView

from accounts.forms import EmailAuthenticationForm, ForgotPasswordForm, SignUpForm


class AccountHomeView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/home.html"


class SignUpView(CreateView):
    template_name = "registration/signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("accounts:login")


class EmailLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class AccountLogoutView(View):
    next_page = reverse_lazy("accounts:login")

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        logout(request)
        return redirect(self.next_page)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        logout(request)
        return redirect(self.next_page)


class ForgotPasswordView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    form_class = ForgotPasswordForm
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")
    extra_email_context = {
        "project_name": _("OTServ Control Panel"),
    }


class ForgotPasswordDoneView(PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class ForgotPasswordConfirmView(PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class ForgotPasswordCompleteView(PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"
