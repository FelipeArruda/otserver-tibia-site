from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
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
from accounts.models import User


class AccountHomeView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/home.html"

    menu_items = [
        {
            "key": "overview",
            "label": _("Overview"),
            "href": "#",
            "icon": "home",
        },
        {
            "key": "realm_status",
            "label": _("Realm Status"),
            "href": "#",
            "icon": "globe",
        },
        {
            "key": "characters",
            "label": _("Characters"),
            "href": "#",
            "icon": "shield",
        },
        {
            "key": "users",
            "label": _("User Management"),
            "href": reverse_lazy("accounts:users"),
            "icon": "users",
            "required_perms": ["accounts.view_user"],
        },
        {
            "key": "groups",
            "label": _("Roles & Groups"),
            "href": reverse_lazy("accounts:roles"),
            "icon": "lock",
            "required_perms": ["auth.view_group"],
        },
        {
            "key": "audit",
            "label": _("Audit Logs"),
            "href": "#",
            "icon": "list",
            "staff_only": True,
        },
    ]

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["menu_items"] = [
            item
            for item in self.menu_items
            if self._can_view_item(self.request.user, item)
        ]
        return context

    @staticmethod
    def _can_view_item(user: object, item: dict[str, object]) -> bool:
        has_perm = getattr(user, "has_perm", None)
        if not callable(has_perm):
            return False

        if item.get("staff_only") and not getattr(user, "is_staff", False):
            return False

        required_perms = item.get("required_perms", [])
        if not required_perms:
            return True

        return all(has_perm(perm) for perm in required_perms)


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

    def get(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        logout(request)
        return redirect(self.next_page)

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
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


class UserManagementView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "accounts/users.html"
    permission_required = "accounts.view_user"
    raise_exception = True

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["users"] = User.objects.order_by("email")
        return context


class RoleManagementView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "accounts/roles.html"
    permission_required = "auth.view_group"
    raise_exception = True

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["roles"] = Group.objects.prefetch_related("permissions").order_by(
            "name"
        )
        return context
