from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed a default test admin user if it does not exist."

    def handle(self, *args: object, **options: object) -> None:
        user_model = get_user_model()
        email = "admin@admin.com"
        password = "admin"

        user, created = user_model.objects.get_or_create(
            pk=email,
            defaults={
                "email": email,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(f"Created test admin user: {email}"))
            return

        self.stdout.write(f"Test admin user already exists: {email}")
