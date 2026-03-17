from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_otserver_tibia_version_fk_backfill"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="otserver",
            name="tibia_version",
        ),
        migrations.RenameField(
            model_name="otserver",
            old_name="tibia_version_ref",
            new_name="tibia_version",
        ),
        migrations.AlterField(
            model_name="otserver",
            name="tibia_version",
            field=models.ForeignKey(
                default="15.30",
                on_delete=models.deletion.PROTECT,
                related_name="otservers",
                to="accounts.tibiaversion",
                verbose_name="Tibia version",
            ),
        ),
    ]
