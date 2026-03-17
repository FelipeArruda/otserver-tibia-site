from django.db import migrations, models


def seed_tibia_versions(apps, schema_editor):
    del schema_editor
    TibiaVersion = apps.get_model("accounts", "TibiaVersion")
    versions = []
    for major in range(7, 16):
        start_minor = 40 if major == 7 else 0
        end_minor = 30 if major == 15 else 90
        for minor in range(start_minor, end_minor + 1, 10):
            code = f"{major}.{minor:02d}"
            versions.append(
                TibiaVersion(
                    code=code, sort_order=major * 100 + minor, is_supported=True
                )
            )
    TibiaVersion.objects.bulk_create(versions, ignore_conflicts=True)


def noop_reverse(apps, schema_editor):
    del apps, schema_editor


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_alter_otserver_tibia_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="TibiaVersion",
            fields=[
                (
                    "code",
                    models.CharField(
                        max_length=10,
                        primary_key=True,
                        serialize=False,
                        verbose_name="Version",
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "is_supported",
                    models.BooleanField(default=True, verbose_name="Supported"),
                ),
            ],
            options={
                "verbose_name": "Tibia version",
                "verbose_name_plural": "Tibia versions",
                "ordering": ["sort_order", "code"],
            },
        ),
        migrations.RunPython(seed_tibia_versions, noop_reverse),
    ]
