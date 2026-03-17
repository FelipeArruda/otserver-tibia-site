from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.views import (
    LoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, TemplateView, UpdateView

from accounts.forms import (
    AdminUserCreateForm,
    AdminUserUpdateForm,
    EmailAuthenticationForm,
    ForgotPasswordForm,
    OTServerForm,
    PlatformSettingForm,
    RoleManagementForm,
    SignUpForm,
)
from accounts.models import AuditLog, OTServer, PlatformSetting, User
from accounts.services import log_audit_event


class DashboardNavigationMixin:
    main_menu_items = [
        {
            "key": "overview",
            "label": _("Overview"),
            "href": reverse_lazy("accounts:home"),
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
            "key": "audit",
            "label": _("Audit Logs"),
            "href": reverse_lazy("accounts:audit_logs"),
            "icon": "list",
            "required_perms": ["accounts.view_auditlog"],
        },
        {
            "key": "otservers",
            "label": _("OTServers"),
            "href": reverse_lazy("accounts:otservers"),
            "icon": "database",
            "required_perms": ["accounts.view_otserver"],
        },
    ]
    settings_menu_items = [
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
        context["main_menu_items"] = [
            item
            for item in self.main_menu_items
            if self._can_view_item(self.request.user, item)
        ]
        context["settings_menu_items"] = [
            item
            for item in self.settings_menu_items
            if self._can_view_item(self.request.user, item)
        ]
        context["show_settings_group"] = bool(context["settings_menu_items"])
        context["settings_active"] = self.active_menu_key in {
            item["key"] for item in context["settings_menu_items"]
        }
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


class PaginationMixin:
    page_size = 10

    def paginate_queryset(
        self, queryset: object, *, context_name: str
    ) -> dict[str, object]:
        paginator = Paginator(queryset, self.page_size)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        params = self.request.GET.copy()
        params.pop("page", None)
        return {
            context_name: page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "pagination_query": params.urlencode(),
        }


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


class LanguagePreferenceView(LoginRequiredMixin, View):
    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        del args, kwargs
        language = request.POST.get("language", "").strip().lower()
        valid_languages = {code for code, _ in settings.LANGUAGES}
        next_url = request.POST.get("next") or reverse_lazy("accounts:home")

        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = reverse_lazy("accounts:home")

        response = redirect(next_url)
        if language in valid_languages:
            request.user.preferred_language = language
            request.user.save(update_fields=["preferred_language"])
            translation.activate(language)
            request.session["django_language"] = language
            request.LANGUAGE_CODE = language
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                language,
                max_age=settings.LANGUAGE_COOKIE_AGE,
            )
        return response


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
    DashboardNavigationMixin,
    PaginationMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
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

        pagination = self.paginate_queryset(users, context_name="users")
        context.update(pagination)
        context["total_users"] = pagination["paginator"].count
        context["groups"] = Group.objects.order_by("name")
        context["filters"] = {
            "q": search,
            "status": status,
            "staff": staff,
            "group": group,
        }
        return context


class RolePermissionContextMixin:
    APP_LABEL_TRANSLATIONS = {
        "accounts": _("Accounts"),
        "admin": _("Administration"),
        "auth": _("Authentication"),
        "contenttypes": _("Content types"),
        "sessions": _("Sessions"),
    }

    @staticmethod
    def _permission_label(permission: Permission) -> str:
        action, _separator, _model_codename = permission.codename.partition("_")
        model_class = permission.content_type.model_class()
        if model_class is None:
            return permission.name

        model_label = str(model_class._meta.verbose_name)
        if action == "add":
            return _("Can add %(model)s") % {"model": model_label}
        if action == "change":
            return _("Can change %(model)s") % {"model": model_label}
        if action == "delete":
            return _("Can delete %(model)s") % {"model": model_label}
        if action == "view":
            return _("Can view %(model)s") % {"model": model_label}
        return permission.name

    @classmethod
    def get_permission_groups(cls) -> list[dict[str, object]]:
        permissions = Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "name"
        )
        groups: dict[str, list[dict[str, object]]] = {}
        for permission in permissions:
            raw_app_label = permission.content_type.app_label
            app_label = str(
                cls.APP_LABEL_TRANSLATIONS.get(
                    raw_app_label, raw_app_label.replace("_", " ").title()
                )
            )
            groups.setdefault(app_label, []).append(
                {
                    "pk": permission.pk,
                    "label": cls._permission_label(permission),
                }
            )
        return [{"label": label, "items": items} for label, items in groups.items()]

    def can_manage_members(self) -> bool:
        return self.request.user.has_perm("accounts.change_user")


class RoleManagementView(
    DashboardNavigationMixin,
    PaginationMixin,
    RolePermissionContextMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/roles.html"
    permission_required = "auth.view_group"
    raise_exception = True
    active_menu_key = "groups"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        base_roles = Group.objects.prefetch_related("permissions", "user_set").annotate(
            members_count=Count("user", distinct=True),
            permissions_count=Count("permissions", distinct=True),
        )
        roles = base_roles
        search = self.request.GET.get("q", "").strip()
        members = self.request.GET.get("members", "").strip()
        order = self.request.GET.get("order", "name").strip()
        allowed_members_filters = {"with", "without"}
        selected_members = members if members in allowed_members_filters else ""

        if search:
            roles = roles.filter(name__icontains=search)
        if selected_members == "with":
            roles = roles.filter(members_count__gt=0)
        elif selected_members == "without":
            roles = roles.filter(members_count=0)

        ordering_map = {
            "name": "name",
            "name_desc": "-name",
            "permissions_desc": "-permissions_count",
            "members_desc": "-members_count",
        }
        selected_order = order if order in ordering_map else "name"
        roles = roles.order_by(ordering_map[selected_order], "name")

        pagination = self.paginate_queryset(roles, context_name="roles")
        context.update(pagination)
        context["total_roles"] = base_roles.count()
        context["filtered_roles_count"] = pagination["paginator"].count
        context["role_filters"] = {
            "q": search,
            "members": selected_members,
            "order": selected_order,
        }
        context["active_filter_count"] = sum(
            bool(value)
            for value in (
                search,
                selected_members,
                selected_order if selected_order != "name" else "",
            )
        )
        context["can_create_roles"] = self.request.user.has_perm("auth.add_group")
        context["can_manage_roles"] = self.request.user.has_perm("auth.change_group")
        context["can_delete_roles"] = self.request.user.has_perm("auth.delete_group")
        return context


class RoleCreateView(
    DashboardNavigationMixin,
    RolePermissionContextMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/role_form.html"
    permission_required = ("auth.view_group", "auth.add_group")
    raise_exception = True
    active_menu_key = "groups"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or RoleManagementForm(
            prefix="role",
            can_manage_members=self.can_manage_members(),
        )
        context["permission_groups"] = self.get_permission_groups()
        context["is_create"] = True
        return context

    def get(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        del args, kwargs
        return self.render_to_response(self.get_context_data())

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        del args, kwargs
        form = RoleManagementForm(
            request.POST,
            prefix="role",
            can_manage_members=self.can_manage_members(),
        )
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form), status=400)

        role = form.save()
        log_audit_event(
            request=request,
            action="role.create",
            target=role.name,
            details={
                "permissions_count": role.permissions.count(),
                "members_count": role.user_set.count(),
            },
        )
        messages.success(request, _("Role created successfully."))
        return redirect("accounts:roles")


class RoleDetailView(
    DashboardNavigationMixin,
    RolePermissionContextMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/role_detail.html"
    permission_required = "auth.view_group"
    raise_exception = True
    active_menu_key = "groups"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        role = get_object_or_404(
            Group.objects.prefetch_related("permissions", "user_set"), pk=kwargs["pk"]
        )
        context["role"] = role
        context["role_permissions_display"] = [
            self._permission_label(permission) for permission in role.permissions.all()
        ]
        context["can_manage_roles"] = self.request.user.has_perm("auth.change_group")
        context["can_delete_roles"] = self.request.user.has_perm("auth.delete_group")
        return context


class RoleUpdateView(
    DashboardNavigationMixin,
    RolePermissionContextMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/role_form.html"
    permission_required = ("auth.view_group", "auth.change_group")
    raise_exception = True
    active_menu_key = "groups"

    def _get_role(self, pk: int) -> Group:
        return get_object_or_404(Group, pk=pk)

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        role = kwargs.get("role")
        if not isinstance(role, Group):
            role = self._get_role(kwargs["pk"])
        context["role"] = role
        context["form"] = kwargs.get("form") or RoleManagementForm(
            instance=role,
            prefix="role",
            can_manage_members=self.can_manage_members(),
        )
        context["permission_groups"] = self.get_permission_groups()
        context["is_create"] = False
        return context

    def get(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        del request, args
        return self.render_to_response(self.get_context_data(**kwargs))

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        del args
        role = self._get_role(kwargs["pk"])
        form = RoleManagementForm(
            request.POST,
            instance=role,
            prefix="role",
            can_manage_members=self.can_manage_members(),
        )
        if not form.is_valid():
            return self.render_to_response(
                self.get_context_data(role=role, form=form),
                status=400,
            )

        updated_role = form.save()
        log_audit_event(
            request=request,
            action="role.update",
            target=updated_role.name,
            details={
                "permissions_count": updated_role.permissions.count(),
                "members_count": updated_role.user_set.count(),
            },
        )
        messages.success(request, _("Role updated successfully."))
        return redirect("accounts:role_detail", pk=updated_role.pk)


class RoleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ("auth.view_group", "auth.delete_group")
    raise_exception = True

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        role = get_object_or_404(Group, pk=kwargs["pk"])
        role_name = role.name
        role.delete()
        log_audit_event(
            request=request,
            action="role.delete",
            target=role_name,
            details={},
        )
        messages.success(request, _("Role removed successfully."))
        return redirect("accounts:roles")


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
        log_audit_event(
            request=self.request,
            action="user.create",
            target=form.instance.email,
            details={
                "is_staff": form.instance.is_staff,
                "is_superuser": form.instance.is_superuser,
            },
        )
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
        log_audit_event(
            request=self.request,
            action="user.update",
            target=form.instance.email,
            details={
                "is_active": form.instance.is_active,
                "is_staff": form.instance.is_staff,
                "is_superuser": form.instance.is_superuser,
            },
        )
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
        log_audit_event(
            request=request,
            action="user.toggle_active",
            target=user.email,
            details={"is_active": user.is_active},
        )
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
        log_audit_event(
            request=self.request,
            action="platform.settings.update",
            target="platform",
            details={
                "default_language": form.instance.default_language,
                "default_timezone": form.instance.default_timezone,
                "primary_color": form.instance.primary_color,
                "platform_name": form.instance.platform_name,
            },
        )
        messages.success(self.request, _("Platform settings updated successfully."))
        return response


class OTServerListView(
    DashboardNavigationMixin,
    PaginationMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/otservers.html"
    permission_required = "accounts.view_otserver"
    raise_exception = True
    active_menu_key = "otservers"
    page_size = 10

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        servers = OTServer.objects.order_by("name")
        search = self.request.GET.get("q", "").strip()
        environment = self.request.GET.get("environment", "").strip()
        database_engine = self.request.GET.get("database_engine", "").strip()
        status = self.request.GET.get("status", "").strip()

        if search:
            servers = servers.filter(name__icontains=search)
        if environment:
            servers = servers.filter(environment=environment)
        if database_engine:
            servers = servers.filter(database_engine=database_engine)
        if status == "active":
            servers = servers.filter(is_active=True)
        elif status == "inactive":
            servers = servers.filter(is_active=False)

        context.update(self.paginate_queryset(servers, context_name="servers"))
        context["filters"] = {
            "q": search,
            "environment": environment,
            "database_engine": database_engine,
            "status": status,
        }
        context["environment_choices"] = OTServer.Environment.choices
        context["database_engine_choices"] = OTServer.DatabaseEngine.choices
        context["can_create_otserver"] = self.request.user.has_perm(
            "accounts.add_otserver"
        )
        context["can_edit_otserver"] = self.request.user.has_perm(
            "accounts.change_otserver"
        )
        context["can_delete_otserver"] = self.request.user.has_perm(
            "accounts.delete_otserver"
        )
        context["total_servers"] = OTServer.objects.count()
        context["filtered_servers"] = context["paginator"].count
        context["show_secondary_content"] = False
        return context


class OTServerCreateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    template_name = "accounts/otserver_form.html"
    form_class = OTServerForm
    permission_required = ("accounts.view_otserver", "accounts.add_otserver")
    raise_exception = True
    success_url = reverse_lazy("accounts:otservers")
    active_menu_key = "otservers"

    def form_valid(self, form: OTServerForm) -> HttpResponse:
        response = super().form_valid(form)
        log_audit_event(
            request=self.request,
            action="otserver.create",
            target=form.instance.name,
            details={
                "environment": form.instance.environment,
                "database_engine": form.instance.database_engine,
                "db_host": form.instance.db_host,
                "is_active": form.instance.is_active,
            },
        )
        messages.success(self.request, _("OTServer created successfully."))
        return response


class OTServerDetailView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, TemplateView
):
    template_name = "accounts/otserver_detail.html"
    permission_required = "accounts.view_otserver"
    raise_exception = True
    active_menu_key = "otservers"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        server = get_object_or_404(OTServer, pk=kwargs["pk"])
        context["server"] = server
        context["masked_db_password"] = "********"
        context["masked_api_token"] = "********" if server.api_token else ""
        context["can_edit_otserver"] = self.request.user.has_perm(
            "accounts.change_otserver"
        )
        context["can_delete_otserver"] = self.request.user.has_perm(
            "accounts.delete_otserver"
        )
        context["show_secondary_content"] = False
        return context


class OTServerUpdateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    template_name = "accounts/otserver_form.html"
    form_class = OTServerForm
    model = OTServer
    pk_url_kwarg = "pk"
    permission_required = ("accounts.view_otserver", "accounts.change_otserver")
    raise_exception = True
    success_url = reverse_lazy("accounts:otservers")
    active_menu_key = "otservers"

    def form_valid(self, form: OTServerForm) -> HttpResponse:
        response = super().form_valid(form)
        log_audit_event(
            request=self.request,
            action="otserver.update",
            target=form.instance.name,
            details={
                "environment": form.instance.environment,
                "database_engine": form.instance.database_engine,
                "db_host": form.instance.db_host,
                "is_active": form.instance.is_active,
            },
        )
        messages.success(self.request, _("OTServer updated successfully."))
        return response


class OTServerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ("accounts.view_otserver", "accounts.delete_otserver")
    raise_exception = True

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        server = get_object_or_404(OTServer, pk=kwargs["pk"])
        server_name = server.name
        server.delete()
        log_audit_event(
            request=request,
            action="otserver.delete",
            target=server_name,
            details={},
        )
        messages.success(request, _("OTServer removed successfully."))
        return redirect("accounts:otservers")


class AuditLogListView(
    DashboardNavigationMixin,
    PaginationMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/audit_logs.html"
    permission_required = "accounts.view_auditlog"
    raise_exception = True
    active_menu_key = "audit"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["show_secondary_content"] = False
        search = self.request.GET.get("q", "").strip()
        action = self.request.GET.get("action", "").strip()
        start_date_raw = self.request.GET.get("start_date", "").strip()
        end_date_raw = self.request.GET.get("end_date", "").strip()

        start_date = self._parse_iso_date(start_date_raw)
        end_date = self._parse_iso_date(end_date_raw)

        logs = AuditLog.objects.select_related("actor")
        if search:
            logs = logs.filter(target__icontains=search)
        if action:
            logs = logs.filter(action=action)
        if start_date:
            logs = logs.filter(created_at__date__gte=start_date)
        if end_date:
            logs = logs.filter(created_at__date__lte=end_date)
        if start_date and end_date and start_date > end_date:
            messages.error(self.request, _("Start date cannot be after end date."))
            logs = AuditLog.objects.none()

        context.update(self.paginate_queryset(logs, context_name="logs"))
        context["actions"] = (
            AuditLog.objects.order_by("action")
            .values_list("action", flat=True)
            .distinct()
        )
        context["filters"] = {
            "q": search,
            "action": action,
            "start_date": start_date_raw,
            "end_date": end_date_raw,
        }
        return context

    @staticmethod
    def _parse_iso_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
