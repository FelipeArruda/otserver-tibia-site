from django.conf import settings
from django.contrib import messages
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
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, TemplateView, UpdateView

from accounts.forms import (
    AdminUserCreateForm,
    AdminUserUpdateForm,
    EmailAuthenticationForm,
    ForgotPasswordForm,
    PlatformSettingForm,
    SignUpForm,
)
from accounts.models import PlatformSetting, User


class DashboardNavigationMixin:
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
        {
            "key": "settings",
            "label": _("Platform Settings"),
            "href": reverse_lazy("accounts:platform_settings"),
            "icon": "settings",
            "required_perms": ["accounts.change_platformsetting"],
        },
    ]
    active_menu_key = "overview"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["menu_items"] = [
            item
            for item in self.menu_items
            if self._can_view_item(self.request.user, item)
        ]
        context["active_menu_key"] = self.active_menu_key
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


class AccountHomeView(DashboardNavigationMixin, LoginRequiredMixin, TemplateView):
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


class UserManagementView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, TemplateView
):
    template_name = "accounts/users.html"
    permission_required = "accounts.view_user"
    raise_exception = True
    active_menu_key = "users"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        users = User.objects.prefetch_related("groups").order_by("email")

        search = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        staff = self.request.GET.get("staff", "").strip()
        group = self.request.GET.get("group", "").strip()

        if search:
            users = users.filter(email__icontains=search)
        if status == "active":
            users = users.filter(is_active=True)
        elif status == "inactive":
            users = users.filter(is_active=False)
        if staff == "yes":
            users = users.filter(is_staff=True)
        elif staff == "no":
            users = users.filter(is_staff=False)
        if group:
            users = users.filter(groups__name=group).distinct()

        context["users"] = users
        context["groups"] = Group.objects.order_by("name")
        context["filters"] = {
            "q": search,
            "status": status,
            "staff": staff,
            "group": group,
        }
        return context


class RoleManagementView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, TemplateView
):
    template_name = "accounts/roles.html"
    permission_required = "auth.view_group"
    raise_exception = True
    active_menu_key = "groups"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["roles"] = Group.objects.prefetch_related("permissions").order_by(
            "name"
        )
        return context


class UserCreateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    template_name = "accounts/user_form.html"
    form_class = AdminUserCreateForm
    permission_required = "accounts.add_user"
    raise_exception = True
    success_url = reverse_lazy("accounts:users")
    active_menu_key = "users"

    def form_valid(self, form: AdminUserCreateForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, _("User created successfully."))
        return response


class UserUpdateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    template_name = "accounts/user_form.html"
    form_class = AdminUserUpdateForm
    model = User
    pk_url_kwarg = "pk"
    permission_required = "accounts.change_user"
    raise_exception = True
    success_url = reverse_lazy("accounts:users")
    active_menu_key = "users"

    def form_valid(self, form: AdminUserUpdateForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, _("User updated successfully."))
        return response


class UserToggleActiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "accounts.change_user"
    raise_exception = True

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        user = get_object_or_404(User, pk=kwargs["pk"])

        if user.pk == request.user.pk and user.is_active:
            messages.error(request, _("You cannot deactivate your own account."))
            return redirect("accounts:users")

        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        messages.success(request, _("User status updated."))
        return redirect("accounts:users")


class PlatformSettingsView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    template_name = "accounts/platform_settings.html"
    form_class = PlatformSettingForm
    permission_required = "accounts.change_platformsetting"
    raise_exception = True
    success_url = reverse_lazy("accounts:platform_settings")
    active_menu_key = "settings"

    def get_object(self, queryset: object = None) -> PlatformSetting:
        del queryset
        return PlatformSetting.get_solo()

    def form_valid(self, form: PlatformSettingForm) -> HttpResponse:
        response = super().form_valid(form)
        preferred_language = form.instance.default_language
        translation.activate(preferred_language)
        self.request.session["django_language"] = preferred_language
        self.request.LANGUAGE_CODE = preferred_language
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            preferred_language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
        )
        messages.success(self.request, _("Platform settings updated successfully."))
        return response
