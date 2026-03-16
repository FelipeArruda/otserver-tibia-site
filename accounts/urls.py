from django.urls import path

from accounts.views import (
    AccountHomeView,
    AccountLogoutView,
    EmailLoginView,
    ForgotPasswordCompleteView,
    ForgotPasswordConfirmView,
    ForgotPasswordDoneView,
    ForgotPasswordView,
    RoleManagementView,
    SignUpView,
    UserManagementView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", EmailLoginView.as_view(), name="login"),
    path("logout/", AccountLogoutView.as_view(), name="logout"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="password_reset"),
    path(
        "forgot-password/done/",
        ForgotPasswordDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        ForgotPasswordConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        ForgotPasswordCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("home/", AccountHomeView.as_view(), name="home"),
    path("users/", UserManagementView.as_view(), name="users"),
    path("roles/", RoleManagementView.as_view(), name="roles"),
]
