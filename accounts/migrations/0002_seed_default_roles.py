from django.db import migrations


def seed_default_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    groups_definition = {
        "Owner": ["view_user", "add_user", "change_user", "delete_user", "view_group"],
        "Game Master": ["view_user", "change_user"],
        "Support": ["view_user"],
        "Viewer": [],
    }

    for group_name, permission_codenames in groups_definition.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        if permission_codenames:
            permissions = Permission.objects.filter(codename__in=permission_codenames)
            group.permissions.add(*permissions)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(seed_default_roles, noop_reverse),
    ]
