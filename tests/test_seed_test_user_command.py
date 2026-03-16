import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_test_user_creates_default_admin_only_once() -> None:
    user_model = get_user_model()

    call_command("seed_test_user")
    call_command("seed_test_user")

    assert user_model.objects.count() == 1
    user = user_model.objects.get(pk="admin@admin.com")
    assert user.email == "admin@admin.com"
    assert user.check_password("admin")
    assert user.is_staff is True
    assert user.is_superuser is True
