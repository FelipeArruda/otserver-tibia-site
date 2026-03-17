from django.db import migrations, models


def backfill_otserver_version_fk(apps, schema_editor):
    del schema_editor
    OTServer = apps.get_model("accounts", "OTServer")
    TibiaVersion = apps.get_model("accounts", "TibiaVersion")

    default_code = "15.30"
    for server in OTServer.objects.all():
        version_code = getattr(server, "tibia_version", "") or default_code
        if not TibiaVersion.objects.filter(code=version_code).exists():
            version_code = default_code
        server.tibia_version_ref_id = version_code
        server.save(update_fields=["tibia_version_ref"])


def noop_reverse(apps, schema_editor):
    del apps, schema_editor


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_tibiaversion"),
    ]

    operations = [
        migrations.AddField(
            model_name="otserver",
            name="tibia_version_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="otservers_temp",
                to="accounts.tibiaversion",
                verbose_name="Tibia version",
            ),
        ),
        migrations.RunPython(backfill_otserver_version_fk, noop_reverse),
    ]
