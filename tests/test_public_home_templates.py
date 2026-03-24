import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from accounts.models import HomePageTemplate, PlatformSetting


@pytest.mark.django_db
def test_root_uses_builtin_latest_news_template_by_default() -> None:
    client = Client()

    response = client.get("/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Latest News" in content


@pytest.mark.django_db
def test_platform_settings_upload_template_and_root_uses_uploaded_template(
    tmp_path,
) -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="template-manager@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="change_platformsetting")
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    upload = SimpleUploadedFile(
        "news_custom.html",
        b"<html><body><h1>NEWS TEMPLATE CUSTOM</h1></body></html>",
        content_type="text/html",
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            reverse("accounts:platform_settings"),
            {
                "platform_name": "OTServ Control Panel",
                "default_language": "en",
                "default_timezone": "UTC",
                "primary_color": "#06b6d4",
                "logo_url": "",
                "home_page_template": PlatformSetting.HOME_TEMPLATE_TIBIA_LATEST_NEWS,
                "home_page_template_upload": upload,
            },
        )

        assert response.status_code == 302

        settings_obj = PlatformSetting.get_solo()
        assert (
            settings_obj.home_page_template
            != PlatformSetting.HOME_TEMPLATE_TIBIA_LATEST_NEWS
        )
        assert HomePageTemplate.objects.filter(
            key=settings_obj.home_page_template
        ).exists()

        public_response = client.get("/")
        assert public_response.status_code == 200
        assert "NEWS TEMPLATE CUSTOM" in public_response.content.decode("utf-8")


@pytest.mark.django_db
def test_platform_settings_can_select_uploaded_template(tmp_path) -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="template-selector@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="change_platformsetting")
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        uploaded_template = HomePageTemplate.objects.create(
            name="Plain News",
            key="plain-news",
            template_file=SimpleUploadedFile(
                "plain_news.html",
                b"<html><body><p>plain template</p></body></html>",
                content_type="text/html",
            ),
        )

        client = Client()
        assert client.login(username=manager.email, password="StrongPass123!")

        response = client.post(
            reverse("accounts:platform_settings"),
            {
                "platform_name": "OTServ Control Panel",
                "default_language": "en",
                "default_timezone": "UTC",
                "primary_color": "#06b6d4",
                "logo_url": "",
                "home_page_template": uploaded_template.key,
            },
        )

        assert response.status_code == 302
        assert PlatformSetting.get_solo().home_page_template == uploaded_template.key


@pytest.mark.django_db
def test_platform_settings_post_missing_required_keys_uses_existing_values() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="template-missing-keys@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="change_platformsetting")
    )

    settings_obj = PlatformSetting.get_solo()
    settings_obj.platform_name = "Existing Platform"
    settings_obj.default_language = "en"
    settings_obj.default_timezone = "UTC"
    settings_obj.primary_color = "#06b6d4"
    settings_obj.save()

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    response = client.post(
        reverse("accounts:platform_settings"),
        {
            "home_page_template": PlatformSetting.HOME_TEMPLATE_TIBIA_LATEST_NEWS,
        },
    )

    assert response.status_code == 302
    updated_settings = PlatformSetting.get_solo()
    assert updated_settings.platform_name == "Existing Platform"
    assert updated_settings.default_language == "en"
    assert updated_settings.default_timezone == "UTC"
    assert updated_settings.primary_color == "#06b6d4"


@pytest.mark.django_db
def test_platform_settings_post_empty_required_values_uses_existing_values() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="template-empty-values@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="change_platformsetting")
    )

    settings_obj = PlatformSetting.get_solo()
    settings_obj.platform_name = "Existing Platform"
    settings_obj.default_language = "en"
    settings_obj.default_timezone = "UTC"
    settings_obj.primary_color = "#06b6d4"
    settings_obj.save()

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    response = client.post(
        reverse("accounts:platform_settings"),
        {
            "platform_name": "",
            "default_language": "",
            "default_timezone": "",
            "primary_color": "",
            "logo_url": "",
            "home_page_template": PlatformSetting.HOME_TEMPLATE_TIBIA_LATEST_NEWS,
        },
    )

    assert response.status_code == 302
    updated_settings = PlatformSetting.get_solo()
    assert updated_settings.platform_name == "Existing Platform"
    assert updated_settings.default_language == "en"
    assert updated_settings.default_timezone == "UTC"
    assert updated_settings.primary_color == "#06b6d4"
