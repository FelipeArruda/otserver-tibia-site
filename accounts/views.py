from datetime import date, timedelta

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
from django.db import connections
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone, translation
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
    TibiaVacationForm,
    TibiaVersionForm,
)
from accounts.models import (
    AuditLog,
    OTServer,
    PlatformSetting,
    TibiaVacation,
    TibiaVersion,
    User,
)
from accounts.services import (
    check_otserver_connections,
    fetch_otserver_character_deaths,
    list_otserver_characters,
    log_audit_event,
    save_otserver_health_check,
    summarize_otserver_characters,
)


def _localized_text(*, en: str, pt: str) -> str:
    language = (translation.get_language() or "").lower()
    return pt if language.startswith("pt") else en


def _otserver_audit_details(
    *,
    server: OTServer,
    db_password_changed: bool,
    api_token_changed: bool,
) -> dict[str, object]:
    return {
        "name": server.name,
        "tibia_version": server.tibia_version_id,
        "environment": server.environment,
        "database_engine": server.database_engine,
        "db_host": server.db_host,
        "db_port": server.db_port,
        "db_name": server.db_name,
        "db_user": server.db_user,
        "db_charset": server.db_charset,
        "db_collation": server.db_collation,
        "db_use_ssl": server.db_use_ssl,
        "api_base_url": server.api_base_url,
        "timezone": server.timezone,
        "monitor_enabled": server.monitor_enabled,
        "monitor_interval_minutes": server.monitor_interval_minutes,
        "is_active": server.is_active,
        "api_token_configured": bool(server.api_token),
        "db_password_changed": db_password_changed,
        "api_token_changed": api_token_changed,
    }


class DashboardNavigationMixin:
    main_menu_items = [
        {
            "key": "overview",
            "label": _("Overview"),
            "href": reverse_lazy("accounts:home"),
            "icon": "home",
        },
        {
            "key": "audit",
            "label": _("Audit Logs"),
            "href": reverse_lazy("accounts:audit_logs"),
            "icon": "list",
            "required_perms": ["accounts.view_auditlog"],
        },
        {
            "key": "otservers_group",
            "label": "OTServers Management",
            "icon": "server_manage",
            "required_perms": ["accounts.view_otserver"],
            "children": [
                {
                    "key": "otservers",
                    "label": _("OTServers"),
                    "href": reverse_lazy("accounts:otservers"),
                    "icon": "database",
                },
                {
                    "key": "characters",
                    "label": _("Characters"),
                    "href": reverse_lazy("accounts:characters"),
                    "icon": "shield",
                },
                {
                    "key": "tibia_vacations",
                    "label": _("Vocations"),
                    "href": reverse_lazy("accounts:tibia_vacations"),
                    "icon": "list",
                    "required_perms": ["accounts.view_tibiavacation"],
                },
                {
                    "key": "tibia_versions",
                    "label": _("Tibia Versions"),
                    "href": reverse_lazy("accounts:tibia_versions"),
                    "icon": "list",
                    "required_perms": ["accounts.view_tibiaversion"],
                },
            ],
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
        context["main_menu_items"] = self._visible_menu_items(self.main_menu_items)
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

    def _visible_menu_items(
        self, items: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        visible_items: list[dict[str, object]] = []

        for item in items:
            if not self._can_view_item(self.request.user, item):
                continue

            visible_item = dict(item)
            if visible_item.get("key") == "otservers_group":
                language = translation.get_language() or ""
                visible_item["label"] = (
                    "Gest\u00e3o de OTServers"
                    if language.lower().startswith("pt")
                    else "OTServers Management"
                )
            if visible_item.get("key") == "tibia_vacations":
                language = translation.get_language() or ""
                visible_item["label"] = (
                    "Voca\u00e7\u00f5es"
                    if language.lower().startswith("pt")
                    else "Vocations"
                )
            if visible_item.get("key") == "tibia_versions":
                language = translation.get_language() or ""
                visible_item["label"] = (
                    "Vers\u00f5es do Tibia"
                    if language.lower().startswith("pt")
                    else "Tibia Versions"
                )
            raw_children = item.get("children", [])
            children = (
                self._visible_menu_items(raw_children)
                if isinstance(raw_children, list)
                else []
            )
            if raw_children and not children:
                continue
            if children:
                visible_item["children"] = children

            is_active_self = visible_item.get("key") == self.active_menu_key
            has_active_child = any(child.get("is_active") for child in children)
            visible_item["is_active_self"] = is_active_self
            visible_item["has_active_child"] = has_active_child
            visible_item["is_active"] = is_active_self or has_active_child
            visible_item["is_open"] = bool(children and visible_item["is_active"])
            visible_items.append(visible_item)

        return visible_items


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

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        total_users = User.objects.count()
        total_servers = OTServer.objects.count()
        active_servers = OTServer.objects.filter(is_active=True).count()
        character_summary = summarize_otserver_characters(
            servers=list(OTServer.objects.all())
        )
        audit_events_24h = AuditLog.objects.filter(created_at__gte=last_24h).count()
        latest_audit_event = AuditLog.objects.select_related("actor").first()
        recent_audit_logs = list(
            AuditLog.objects.select_related("actor")
            .filter(action__startswith="otserver.")
            .order_by("-created_at")[:5]
        )
        recent_ot_tests = list(
            AuditLog.objects.filter(
                action="otserver.connection_test", created_at__gte=last_24h
            ).order_by("-created_at")[:50]
        )
        failed_ot_tests_24h = sum(
            bool(entry.details.get("success") is False) for entry in recent_ot_tests
        )

        database_ok = True
        try:
            connections["default"].ensure_connection()
        except Exception:
            database_ok = False

        last_hour = now - timedelta(hours=1)
        recent_online_delta = AuditLog.objects.filter(
            action="otserver.connection_test",
            created_at__gte=last_hour,
            details__success=True,
        ).count()

        next_save_server = timezone.localtime(now).replace(
            hour=3, minute=0, second=0, microsecond=0
        )
        if next_save_server <= timezone.localtime(now):
            next_save_server += timedelta(days=1)

        pending_incidents = failed_ot_tests_24h + len(character_summary["errors"])

        context["show_secondary_content"] = True
        context["home_metrics"] = {
            "total_users": total_users,
            "active_servers": active_servers,
            "total_servers": total_servers,
            "total_characters": character_summary["total_characters"],
            "online_characters": character_summary["online_characters"],
            "offline_characters": character_summary["offline_characters"],
            "unknown_status_characters": character_summary["unknown_status_characters"],
            "characters_source_errors": len(character_summary["errors"]),
            "healthy_character_sources": character_summary["healthy_sources"],
            "active_character_sources": character_summary["active_sources"],
            "audit_events_24h": audit_events_24h,
            "pending_incidents": pending_incidents,
            "recent_online_delta": recent_online_delta,
            "next_save_server": next_save_server,
            "latest_event_at": latest_audit_event.created_at
            if latest_audit_event
            else None,
            "latest_event_action": latest_audit_event.action
            if latest_audit_event
            else "",
            "failed_ot_tests_24h": failed_ot_tests_24h,
            "database_ok": database_ok,
        }
        context["operational_events"] = [
            self._format_operational_event(log) for log in recent_audit_logs
        ]
        monitored_servers = OTServer.objects.filter(
            is_active=True,
            monitor_enabled=True,
        ).order_by("name")
        context["operator_status"] = [
            {
                "name": server.name,
                "status": (
                    "ok"
                    if server.last_health_check_ok is True
                    else (
                        "delay" if server.last_health_check_ok is False else "unknown"
                    )
                ),
                "status_label": (
                    _localized_text(en="Connected", pt="Conectado")
                    if server.last_health_check_ok is True
                    else (
                        _localized_text(en="Disconnected", pt="Desconectado")
                        if server.last_health_check_ok is False
                        else _localized_text(en="Pending", pt="Pendente")
                    )
                ),
                "checked_at": server.last_health_check_at,
            }
            for server in monitored_servers
        ]
        context["dashboard_healthy"] = (
            database_ok
            and failed_ot_tests_24h == 0
            and character_summary["errors"] == []
        )
        context["can_view_users"] = self.request.user.has_perm("accounts.view_user")
        context["can_view_otservers"] = self.request.user.has_perm(
            "accounts.view_otserver"
        )
        context["can_view_characters"] = self.request.user.has_perm(
            "accounts.view_otserver"
        )
        context["can_view_audit"] = self.request.user.has_perm("accounts.view_auditlog")
        return context

    @staticmethod
    def _format_operational_event(log: AuditLog) -> dict[str, object]:
        action_map = {
            "otserver.create": _localized_text(
                en="OTServer created",
                pt="OTServer criado",
            ),
            "otserver.update": _localized_text(
                en="OTServer updated",
                pt="OTServer atualizado",
            ),
            "otserver.delete": _localized_text(
                en="OTServer removed",
                pt="OTServer removido",
            ),
            "otserver.connection_test": _localized_text(
                en="Connection test",
                pt="Teste de conexão",
            ),
            "otserver.health_check": _localized_text(
                en="Automatic health check",
                pt="Verificação automática",
            ),
        }
        title = action_map.get(
            log.action,
            _localized_text(en="OTServer event", pt="Evento de OTServer"),
        )

        status = "info"
        status_label = ""
        if log.action == "otserver.connection_test":
            success = log.details.get("success")
            status = "success" if success is True else "error"
            status_label = (
                _localized_text(en="Succeeded", pt="Sucesso")
                if success is True
                else _localized_text(en="Failed", pt="Falhou")
            )
        if log.action == "otserver.health_check":
            success = log.details.get("success")
            status = "success" if success is True else "error"
            status_label = (
                _localized_text(en="Connected", pt="Conectado")
                if success is True
                else _localized_text(en="Disconnected", pt="Desconectado")
            )

        return {
            "title": title,
            "target": log.target,
            "status": status,
            "status_label": status_label,
            "created_at": log.created_at,
        }


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
        servers = OTServer.objects.select_related("tibia_version").order_by("name")
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
        context["can_test_otserver"] = self.request.user.has_perm(
            "accounts.change_otserver"
        )
        context["total_servers"] = OTServer.objects.count()
        context["filtered_servers"] = context["paginator"].count
        context["show_secondary_content"] = False
        return context


class CharacterListView(
    DashboardNavigationMixin,
    PaginationMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/characters.html"
    permission_required = "accounts.view_otserver"
    raise_exception = True
    active_menu_key = "characters"
    page_size = 20

    ORDERING_CHOICES = (
        ("name_asc", _("Name (A-Z)")),
        ("name_desc", _("Name (Z-A)")),
        ("level_desc", _("Highest level")),
        ("level_asc", _("Lowest level")),
        ("updated_desc", _("Most recently updated")),
        ("updated_asc", _("Least recently updated")),
    )

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["show_secondary_content"] = False
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")

        available_servers = list(OTServer.objects.order_by("name"))
        selected_otserver = self.request.GET.get("otserver", "").strip()
        search = self.request.GET.get("q", "").strip()
        selected_vocation = self.request.GET.get("vocation", "").strip()
        selected_status = self.request.GET.get("status", "").strip()
        selected_account_id = self.request.GET.get("account_id", "").strip()
        selected_account_email = self.request.GET.get("account_email", "").strip()
        selected_order = self.request.GET.get("order", "name_asc").strip()
        min_level = self._parse_level(self.request.GET.get("min_level", ""))
        max_level = self._parse_level(self.request.GET.get("max_level", ""))

        characters_result = list_otserver_characters(
            servers=available_servers,
            search=search,
            otserver_pk=selected_otserver,
            vocation=selected_vocation,
            min_level=min_level,
            max_level=max_level,
            status=selected_status,
            account_id=selected_account_id,
            account_email=selected_account_email,
            order=selected_order,
        )
        all_filtered_characters = characters_result["characters"]

        context.update(
            self.paginate_queryset(all_filtered_characters, context_name="characters")
        )
        context["filters"] = {
            "otserver": selected_otserver,
            "q": search,
            "vocation": selected_vocation,
            "status": selected_status,
            "account_id": selected_account_id,
            "account_email": selected_account_email,
            "order": selected_order,
            "min_level": self.request.GET.get("min_level", "").strip(),
            "max_level": self.request.GET.get("max_level", "").strip(),
        }
        context["order_choices"] = self.ORDERING_CHOICES
        context["otserver_choices"] = [
            server for server in available_servers if server.is_active
        ]
        context["vocation_choices"] = characters_result["available_vocations"]
        context["source_errors"] = characters_result["errors"]
        context["total_characters"] = len(all_filtered_characters)
        context["total_online"] = sum(
            character.get("is_online") is True for character in all_filtered_characters
        )
        context["total_offline"] = context["total_characters"] - context["total_online"]
        context["source_count"] = len(context["otserver_choices"])
        context["characters_ui"] = {
            "name_label": "Nome" if is_pt else "Character",
            "vocation_label": "Voca\u00e7\u00e3o" if is_pt else "Vocation",
            "account_id_label": "ID da conta" if is_pt else "Account ID",
            "account_name_label": "Nome da conta" if is_pt else "Account name",
            "account_email_label": "E-mail da conta" if is_pt else "Account email",
            "view_label": "Visualizar" if is_pt else "View",
        }
        return context

    @staticmethod
    def _parse_level(value: str) -> int | None:
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return None


class CharacterDetailView(
    DashboardNavigationMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/character_detail.html"
    permission_required = "accounts.view_otserver"
    raise_exception = True
    active_menu_key = "characters"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["show_secondary_content"] = False
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")

        server = get_object_or_404(OTServer, pk=kwargs["otserver_pk"], is_active=True)
        character_name = str(kwargs["character_name"]).strip()
        matches = list_otserver_characters(
            servers=[server],
            search=character_name,
            otserver_pk=str(server.pk),
            order="name_asc",
        )["characters"]
        normalized_name = character_name.casefold()
        selected_character = next(
            (
                character
                for character in matches
                if str(character.get("name", "")).strip().casefold() == normalized_name
            ),
            None,
        )
        if selected_character is None:
            messages.error(self.request, _("Character not found for this OTServer."))
            context["character"] = {}
            context["detail_description"] = _(
                "Complete view of character and account data from the selected OTServer."
            )
            context["associated_characters"] = []
            context["recent_deaths"] = []
            return context

        context["character"] = selected_character
        account_id = selected_character.get("account_id")
        associated_characters: list[dict[str, object]] = []
        if account_id is not None:
            associated_result = list_otserver_characters(
                servers=[server],
                otserver_pk=str(server.pk),
                account_id=str(account_id),
                order="name_asc",
            )
            associated_characters = [
                character
                for character in associated_result["characters"]
                if str(character.get("name", "")).strip().casefold() != normalized_name
            ]
        context["associated_characters"] = associated_characters
        try:
            context["recent_deaths"] = fetch_otserver_character_deaths(
                server=server,
                character_name=str(selected_character.get("name", "")),
                limit=3,
            )
        except Exception:
            context["recent_deaths"] = []

        context["detail_description"] = _(
            "OTServer: %(server)s | Account ID: %(account_id)s"
        ) % {
            "server": selected_character.get("otserver_name") or "-",
            "account_id": selected_character.get("account_id") or "-",
        }
        context["characters_ui"] = {
            "page_title": ("Detalhes do personagem" if is_pt else "Character details"),
            "page_description": (
                "Visão completa dos dados do personagem e da conta no OTServer selecionado."
                if is_pt
                else "Complete view of character and account data from the selected OTServer."
            ),
            "account_section": (
                "Informa\u00e7\u00f5es da conta" if is_pt else "Account information"
            ),
            "character_section": "Personagem" if is_pt else "Character",
            "linked_characters_section": (
                "Personagens vinculados \u00e0 conta"
                if is_pt
                else "Characters linked to this account"
            ),
            "vocation_label": "Voca\u00e7\u00e3o" if is_pt else "Vocation",
            "account_id_label": "ID da conta" if is_pt else "Account ID",
            "account_name_label": "Nome da conta" if is_pt else "Account name",
            "account_email_label": "E-mail da conta" if is_pt else "Account email",
            "account_type_label": "Tipo de conta" if is_pt else "Account type",
            "account_real_name_label": "Nome real" if is_pt else "Real name",
            "account_location_label": "Localiza\u00e7\u00e3o" if is_pt else "Location",
            "account_country_label": "Pa\u00eds" if is_pt else "Country",
            "account_premium_points_label": (
                "Pontos premium" if is_pt else "Premium points"
            ),
            "account_premdays_label": "Dias premium" if is_pt else "Premium days",
            "account_coins_label": "Coins",
            "account_created_label": (
                "Conta criada em" if is_pt else "Account created at"
            ),
            "account_last_login_label": (
                "\u00daltimo login da conta" if is_pt else "Account last login"
            ),
            "status_label": "Status",
            "status_online": "Online",
            "status_offline": "Offline",
            "status_unknown": "Desconhecido" if is_pt else "Unknown",
            "server_label": "OTServer",
            "level_label": "N\u00edvel" if is_pt else "Level",
            "name_label": "Nome" if is_pt else "Name",
            "updated_label": "Atualizado em" if is_pt else "Updated at",
            "action_label": "Ação" if is_pt else "Action",
            "view_label": "Visualizar" if is_pt else "View",
            "open_character_label": ("Abrir personagem" if is_pt else "Open character"),
            "back_label": (
                "Voltar para personagens" if is_pt else "Back to characters"
            ),
            "profile_kicker": "Perfil do personagem" if is_pt else "Character profile",
            "profile_description": (
                "Vis\u00e3o detalhada da conta e dos personagens vinculados para revis\u00e3o r\u00e1pida."
                if is_pt
                else "Detailed account snapshot and server-linked character information, designed for faster review."
            ),
            "account_snapshot_title": (
                "Resumo da conta" if is_pt else "Account snapshot"
            ),
            "quick_status_title": "Status r\u00e1pido" if is_pt else "Quick status",
            "character_info_hint": (
                "Informa\u00e7\u00f5es principais do personagem em jogo."
                if is_pt
                else "Main in-game information for this character."
            ),
            "account_info_hint": (
                "Dados administrativos e de propriedade da conta vinculada."
                if is_pt
                else "Administrative and ownership details of the linked account."
            ),
            "linked_characters_hint": (
                "Mesma conta, outros personagens neste OTServer."
                if is_pt
                else "Same account, other characters in this OTServer."
            ),
            "recent_deaths_title": ("Últimas mortes" if is_pt else "Recent deaths"),
            "recent_deaths_empty": (
                "Nenhuma morte registrada para este personagem."
                if is_pt
                else "No deaths recorded for this character."
            ),
            "recent_deaths_level": "Nível" if is_pt else "Level",
            "recent_deaths_killer": ("Morto por" if is_pt else "Killed by"),
            "character_not_found_title": (
                "Personagem não encontrado." if is_pt else "Character not found."
            ),
            "character_not_found_hint": (
                "Tente novamente pela lista de personagens."
                if is_pt
                else "Try again from the character list."
            ),
            "no_linked_characters": (
                "Nenhum outro personagem vinculado a esta conta."
                if is_pt
                else "No other characters linked to this account."
            ),
        }
        return context


class OTServerListConnectionTestView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ("accounts.view_otserver", "accounts.change_otserver")
    raise_exception = True

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        server = get_object_or_404(
            OTServer.objects.select_related("tibia_version"), pk=kwargs["pk"]
        )
        test_result = check_otserver_connections(
            database_engine=server.database_engine,
            db_host=server.db_host,
            db_port=server.db_port,
            db_name=server.db_name,
            db_user=server.db_user,
            db_password=server.get_db_password(),
            db_charset=server.db_charset,
            db_use_ssl=server.db_use_ssl,
            api_base_url=server.api_base_url,
            api_token=server.get_api_token(),
        )
        save_otserver_health_check(server=server, result=test_result)
        log_audit_event(
            request=request,
            action="otserver.connection_test",
            target=server.name,
            details={
                "source": "list",
                "success": test_result["success"],
                "database_ok": test_result["database"]["ok"],
                "api_ok": test_result["api"]["ok"],
            },
        )
        if test_result["success"]:
            messages.success(
                request,
                _("Connection test for %(name)s succeeded.") % {"name": server.name},
            )
        else:
            messages.error(
                request,
                _("Connection test for %(name)s failed.") % {"name": server.name},
            )

        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = reverse_lazy("accounts:otservers")
        return redirect(next_url)


class OTServerCreateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    template_name = "accounts/otserver_form.html"
    form_class = OTServerForm
    permission_required = ("accounts.view_otserver", "accounts.add_otserver")
    raise_exception = True
    success_url = reverse_lazy("accounts:otservers")
    active_menu_key = "otservers"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["show_secondary_content"] = False
        context["test_result"] = kwargs.get("test_result")
        return context

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        self.object = None
        if request.POST.get("action") != "test_connection":
            return super().post(request, *args, **kwargs)

        form = self.get_form()
        if not form.is_valid():
            messages.error(request, _("Fix the highlighted fields before testing."))
            return self.render_to_response(self.get_context_data(form=form), status=400)

        test_result = check_otserver_connections(
            database_engine=form.cleaned_data["database_engine"],
            db_host=form.cleaned_data["db_host"],
            db_port=form.cleaned_data["db_port"],
            db_name=form.cleaned_data["db_name"],
            db_user=form.cleaned_data["db_user"],
            db_password=form.cleaned_data["db_password"],
            db_charset=form.cleaned_data["db_charset"],
            db_use_ssl=form.cleaned_data["db_use_ssl"],
            api_base_url=form.cleaned_data["api_base_url"],
            api_token=form.cleaned_data["api_token"],
        )
        if form.instance.pk:
            save_otserver_health_check(server=form.instance, result=test_result)
        log_audit_event(
            request=request,
            action="otserver.connection_test",
            target=form.cleaned_data["name"] or form.cleaned_data["db_host"],
            details={
                "success": test_result["success"],
                "database_ok": test_result["database"]["ok"],
                "api_ok": test_result["api"]["ok"],
            },
        )
        if test_result["success"]:
            messages.success(request, _("Connection test succeeded."))
        else:
            messages.error(request, _("Connection test failed."))
        return self.render_to_response(
            self.get_context_data(form=form, test_result=test_result)
        )

    def form_valid(self, form: OTServerForm) -> HttpResponse:
        response = super().form_valid(form)
        details = _otserver_audit_details(
            server=form.instance,
            db_password_changed=True,
            api_token_changed=bool(form.cleaned_data.get("api_token")),
        )
        log_audit_event(
            request=self.request,
            action="otserver.create",
            target=form.instance.name,
            details=details,
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
        server = get_object_or_404(
            OTServer.objects.select_related("tibia_version"), pk=kwargs["pk"]
        )
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

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["show_secondary_content"] = False
        context["test_result"] = kwargs.get("test_result")
        return context

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        self.object = self.get_object()
        original_db_password = self.object.get_db_password()
        original_api_token = self.object.get_api_token()
        if request.POST.get("action") != "test_connection":
            return super().post(request, *args, **kwargs)

        form_data = request.POST.copy()
        if not form_data.get("db_password"):
            form_data["db_password"] = original_db_password
        if not form_data.get("api_token"):
            form_data["api_token"] = original_api_token

        form = self.form_class(form_data, instance=self.object)
        if not form.is_valid():
            messages.error(request, _("Fix the highlighted fields before testing."))
            return self.render_to_response(
                self.get_context_data(object=self.object, form=form),
                status=400,
            )

        db_password = form.cleaned_data["db_password"]
        api_token = form.cleaned_data["api_token"]
        test_result = check_otserver_connections(
            database_engine=form.cleaned_data["database_engine"],
            db_host=form.cleaned_data["db_host"],
            db_port=form.cleaned_data["db_port"],
            db_name=form.cleaned_data["db_name"],
            db_user=form.cleaned_data["db_user"],
            db_password=db_password,
            db_charset=form.cleaned_data["db_charset"],
            db_use_ssl=form.cleaned_data["db_use_ssl"],
            api_base_url=form.cleaned_data["api_base_url"],
            api_token=api_token,
        )
        save_otserver_health_check(server=self.object, result=test_result)
        log_audit_event(
            request=request,
            action="otserver.connection_test",
            target=self.object.name,
            details={
                "success": test_result["success"],
                "database_ok": test_result["database"]["ok"],
                "api_ok": test_result["api"]["ok"],
            },
        )
        if test_result["success"]:
            messages.success(request, _("Connection test succeeded."))
        else:
            messages.error(request, _("Connection test failed."))
        return self.render_to_response(
            self.get_context_data(
                object=self.object, form=form, test_result=test_result
            )
        )

    def form_valid(self, form: OTServerForm) -> HttpResponse:
        previous_server = OTServer.objects.get(pk=form.instance.pk)
        previous_db_password = previous_server.get_db_password()
        previous_api_token = previous_server.get_api_token()
        response = super().form_valid(form)
        details = _otserver_audit_details(
            server=form.instance,
            db_password_changed=form.instance.get_db_password() != previous_db_password,
            api_token_changed=form.instance.get_api_token() != previous_api_token,
        )
        log_audit_event(
            request=self.request,
            action="otserver.update",
            target=form.instance.name,
            details=details,
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


class TibiaVersionListView(
    DashboardNavigationMixin,
    PaginationMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/tibia_versions.html"
    permission_required = ("accounts.view_otserver", "accounts.view_tibiaversion")
    raise_exception = True
    active_menu_key = "tibia_versions"
    page_size = 15

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")

        queryset = TibiaVersion.objects.annotate(
            otservers_count=Count("otservers", distinct=True)
        ).order_by("sort_order", "code")

        search = self.request.GET.get("q", "").strip()
        supported = self.request.GET.get("supported", "").strip()
        if search:
            queryset = queryset.filter(code__icontains=search)
        if supported == "yes":
            queryset = queryset.filter(is_supported=True)
        elif supported == "no":
            queryset = queryset.filter(is_supported=False)

        context.update(self.paginate_queryset(queryset, context_name="versions"))
        context["filters"] = {"q": search, "supported": supported}
        context["can_add_version"] = self.request.user.has_perm(
            "accounts.add_tibiaversion"
        )
        context["can_change_version"] = self.request.user.has_perm(
            "accounts.change_tibiaversion"
        )
        context["can_delete_version"] = self.request.user.has_perm(
            "accounts.delete_tibiaversion"
        )
        context["version_ui"] = {
            "title": "Vers\u00f5es do Tibia" if is_pt else "Tibia Versions",
            "description": (
                "Gerencie as vers\u00f5es do Tibia dispon\u00edveis para seus OTServers."
                if is_pt
                else "Manage available Tibia versions for your OTServers."
            ),
            "add_button": "Adicionar versão" if is_pt else "Add version",
            "sort_order": "Ordem" if is_pt else "Sort order",
            "all_status": "Todos os status" if is_pt else "All status",
            "supported": "Suportada" if is_pt else "Supported",
            "unsupported": "Não suportada" if is_pt else "Unsupported",
            "otservers_count": "OTServers vinculados" if is_pt else "Linked OTServers",
            "actions": "Ações" if is_pt else "Actions",
            "none_found": (
                "Nenhuma versão encontrada." if is_pt else "No Tibia versions found."
            ),
            "remove_confirm": (
                "Remover esta versão do Tibia?"
                if is_pt
                else "Remove this Tibia version?"
            ),
        }
        context["show_secondary_content"] = False
        return context


class TibiaVersionCreateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    template_name = "accounts/tibia_version_form.html"
    form_class = TibiaVersionForm
    permission_required = ("accounts.view_otserver", "accounts.add_tibiaversion")
    raise_exception = True
    success_url = reverse_lazy("accounts:tibia_versions")
    active_menu_key = "tibia_versions"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")
        context["version_ui"] = {
            "title": "Nova versão do Tibia" if is_pt else "New Tibia version",
            "description": (
                "Cadastre versões para uso em OTServers e mapeamentos."
                if is_pt
                else "Register versions for OTServer usage and mappings."
            ),
            "back": "Voltar para versões" if is_pt else "Back to versions",
        }
        context["show_secondary_content"] = False
        return context

    def form_valid(self, form: TibiaVersionForm) -> HttpResponse:
        response = super().form_valid(form)
        log_audit_event(
            request=self.request,
            action="tibia_version.create",
            target=form.instance.code,
            details={
                "sort_order": form.instance.sort_order,
                "is_supported": form.instance.is_supported,
            },
        )
        messages.success(
            self.request,
            _localized_text(
                en="Tibia version created successfully.",
                pt="Versão do Tibia criada com sucesso.",
            ),
        )
        return response

    def form_invalid(self, form: TibiaVersionForm) -> HttpResponse:
        messages.error(
            self.request,
            _localized_text(
                en="Please correct the highlighted fields.",
                pt="Corrija os campos destacados.",
            ),
        )
        return super().form_invalid(form)


class TibiaVersionUpdateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    template_name = "accounts/tibia_version_form.html"
    form_class = TibiaVersionForm
    model = TibiaVersion
    pk_url_kwarg = "pk"
    permission_required = ("accounts.view_otserver", "accounts.change_tibiaversion")
    raise_exception = True
    success_url = reverse_lazy("accounts:tibia_versions")
    active_menu_key = "tibia_versions"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")
        context["version_ui"] = {
            "title": "Editar versão do Tibia" if is_pt else "Edit Tibia version",
            "description": (
                "Atualize ordem e status de suporte da versão."
                if is_pt
                else "Update sort order and supported status."
            ),
            "back": "Voltar para versões" if is_pt else "Back to versions",
        }
        context["show_secondary_content"] = False
        return context

    def get_form(
        self, form_class: type[TibiaVersionForm] | None = None
    ) -> TibiaVersionForm:
        form = super().get_form(form_class)
        form.fields["code"].disabled = True
        return form

    def form_valid(self, form: TibiaVersionForm) -> HttpResponse:
        response = super().form_valid(form)
        log_audit_event(
            request=self.request,
            action="tibia_version.update",
            target=form.instance.code,
            details={
                "sort_order": form.instance.sort_order,
                "is_supported": form.instance.is_supported,
            },
        )
        messages.success(
            self.request,
            _localized_text(
                en="Tibia version updated successfully.",
                pt="Versão do Tibia atualizada com sucesso.",
            ),
        )
        return response

    def form_invalid(self, form: TibiaVersionForm) -> HttpResponse:
        messages.error(
            self.request,
            _localized_text(
                en="Please correct the highlighted fields.",
                pt="Corrija os campos destacados.",
            ),
        )
        return super().form_invalid(form)


class TibiaVersionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ("accounts.view_otserver", "accounts.delete_tibiaversion")
    raise_exception = True

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        version = get_object_or_404(TibiaVersion, pk=kwargs["pk"])
        code = version.code
        try:
            version.delete()
        except ProtectedError:
            messages.error(
                request,
                _localized_text(
                    en=(
                        "Cannot remove this Tibia version because it is in use by "
                        "OTServers or related records."
                    ),
                    pt=(
                        "Não é possível remover esta versão do Tibia porque ela está "
                        "em uso por OTServers ou registros relacionados."
                    ),
                ),
            )
            return redirect("accounts:tibia_versions")

        log_audit_event(
            request=request,
            action="tibia_version.delete",
            target=code,
            details={},
        )
        messages.success(
            request,
            _localized_text(
                en="Tibia version removed successfully.",
                pt="Versão do Tibia removida com sucesso.",
            ),
        )
        return redirect("accounts:tibia_versions")


class TibiaVacationListView(
    DashboardNavigationMixin,
    PaginationMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "accounts/tibia_vacations.html"
    permission_required = ("accounts.view_otserver", "accounts.view_tibiavacation")
    raise_exception = True
    active_menu_key = "tibia_vacations"
    page_size = 15

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")
        queryset = (
            TibiaVacation.objects.select_related("otserver", "tibia_version")
            .filter(otserver__isnull=False)
            .order_by(
                "otserver__name",
                "vocation_id",
            )
        )
        search = self.request.GET.get("q", "").strip()
        otserver = self.request.GET.get("otserver", "").strip()

        if search:
            queryset = queryset.filter(name__icontains=search)
        if otserver:
            queryset = queryset.filter(otserver_id=otserver)

        context.update(self.paginate_queryset(queryset, context_name="vacations"))
        context["filters"] = {"q": search, "otserver": otserver}
        context["otserver_choices"] = OTServer.objects.select_related(
            "tibia_version"
        ).order_by("name")
        context["can_add_vacation"] = self.request.user.has_perm(
            "accounts.add_tibiavacation"
        )
        context["can_change_vacation"] = self.request.user.has_perm(
            "accounts.change_tibiavacation"
        )
        context["can_delete_vacation"] = self.request.user.has_perm(
            "accounts.delete_tibiavacation"
        )
        context["vocation_ui"] = {
            "title": "Vocações" if is_pt else "Vocations",
            "description": (
                "Gerencie traduções de vocações por versão do Tibia."
                if is_pt
                else "Manage vocation translations by Tibia version."
            ),
            "add_button": "Adicionar vocação" if is_pt else "Add vocation",
            "all_otservers": "Todos os OTServers" if is_pt else "All OTServers",
            "vocation_id": "ID da vocação" if is_pt else "Vocation ID",
            "name_pt": "Nome (Português)" if is_pt else "Name (Portuguese)",
            "description_label": "Descrição" if is_pt else "Description",
            "actions": "Ações" if is_pt else "Actions",
            "none_found": "Nenhuma vocação encontrada."
            if is_pt
            else "No vocations found.",
            "remove_confirm": "Remover esta vocação?"
            if is_pt
            else "Remove this vocation?",
        }
        context["show_secondary_content"] = False
        return context


class TibiaVacationCreateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    template_name = "accounts/tibia_vacation_form.html"
    form_class = TibiaVacationForm
    permission_required = ("accounts.view_otserver", "accounts.add_tibiavacation")
    raise_exception = True
    success_url = reverse_lazy("accounts:tibia_vacations")
    active_menu_key = "tibia_vacations"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")
        context["vocation_ui"] = {
            "title": "Nova vocação" if is_pt else "New vocation",
            "description": (
                "Mantenha registros de tradução de vocações por OTServer."
                if is_pt
                else "Maintain vocation translation records per OTServer."
            ),
            "back": "Voltar para vocações" if is_pt else "Back to vocations",
        }
        context["show_secondary_content"] = False
        return context

    def form_valid(self, form: TibiaVacationForm) -> HttpResponse:
        response = super().form_valid(form)
        log_audit_event(
            request=self.request,
            action="tibia_vacation.create",
            target=f"{form.instance.tibia_version_id}:{form.instance.vocation_id}",
            details={
                "name": form.instance.name,
                "name_pt_br": form.instance.name_pt_br,
            },
        )
        messages.success(
            self.request,
            _localized_text(
                en="Vocation created successfully.",
                pt="Vocação criada com sucesso.",
            ),
        )
        return response

    def form_invalid(self, form: TibiaVacationForm) -> HttpResponse:
        messages.error(
            self.request,
            _localized_text(
                en="Please correct the highlighted fields.",
                pt="Corrija os campos destacados.",
            ),
        )
        return super().form_invalid(form)


class TibiaVacationUpdateView(
    DashboardNavigationMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    template_name = "accounts/tibia_vacation_form.html"
    form_class = TibiaVacationForm
    model = TibiaVacation
    pk_url_kwarg = "pk"
    permission_required = ("accounts.view_otserver", "accounts.change_tibiavacation")
    raise_exception = True
    success_url = reverse_lazy("accounts:tibia_vacations")
    active_menu_key = "tibia_vacations"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        language = (translation.get_language() or "").lower()
        is_pt = language.startswith("pt")
        context["vocation_ui"] = {
            "title": "Editar vocação" if is_pt else "Edit vocation",
            "description": (
                "Mantenha registros de tradução de vocações por OTServer."
                if is_pt
                else "Maintain vocation translation records per OTServer."
            ),
            "back": "Voltar para vocações" if is_pt else "Back to vocations",
        }
        context["show_secondary_content"] = False
        return context

    def form_valid(self, form: TibiaVacationForm) -> HttpResponse:
        response = super().form_valid(form)
        log_audit_event(
            request=self.request,
            action="tibia_vacation.update",
            target=f"{form.instance.tibia_version_id}:{form.instance.vocation_id}",
            details={
                "name": form.instance.name,
                "name_pt_br": form.instance.name_pt_br,
            },
        )
        messages.success(
            self.request,
            _localized_text(
                en="Vocation updated successfully.",
                pt="Vocação atualizada com sucesso.",
            ),
        )
        return response

    def form_invalid(self, form: TibiaVacationForm) -> HttpResponse:
        messages.error(
            self.request,
            _localized_text(
                en="Please correct the highlighted fields.",
                pt="Corrija os campos destacados.",
            ),
        )
        return super().form_invalid(form)


class TibiaVacationDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ("accounts.view_otserver", "accounts.delete_tibiavacation")
    raise_exception = True

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        vacation = get_object_or_404(TibiaVacation, pk=kwargs["pk"])
        target = f"{vacation.tibia_version_id}:{vacation.vocation_id}"
        vacation.delete()
        log_audit_event(
            request=request,
            action="tibia_vacation.delete",
            target=target,
            details={},
        )
        messages.success(
            request,
            _localized_text(
                en="Vocation removed successfully.",
                pt="Vocação removida com sucesso.",
            ),
        )
        return redirect("accounts:tibia_vacations")


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
