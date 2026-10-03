from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def reject_duplicate_serials(apps, schema_editor):
    Asset = apps.get_model('assets', 'Asset')
    alias = schema_editor.connection.alias
    duplicates = (Asset.objects.using(alias).values('unique_identifier')
                  .annotate(total=models.Count('pk')).filter(total__gt=1).count())
    if duplicates:
        raise RuntimeError(
            f'Cannot enforce globally unique asset serial numbers: {duplicates} duplicate serial group(s) exist. '
            'Resolve each duplicate in a reviewed data migration or use a clean database; no asset rows were changed.'
        )


def preserve_current_assignments(apps, schema_editor):
    Asset = apps.get_model('assets', 'Asset')
    AssignmentHistory = apps.get_model('assets', 'AssignmentHistory')
    alias = schema_editor.connection.alias
    AssignmentHistory.objects.using(alias).bulk_create([
        AssignmentHistory(asset_id=asset.pk, employee_id=asset.assigned_to_id,
                         action='assigned', occurred_at=None, actor_id=None)
        for asset in Asset.objects.using(alias).filter(assigned_to__isnull=False).iterator()
    ])


class Migration(migrations.Migration):
    dependencies = [
        ('assets', '0004_asset_is_active_assettype_is_active'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(reject_duplicate_serials, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='asset', name='unique_identifier',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.CreateModel(
            name='AssignmentHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('assigned', 'Assigned'), ('returned', 'Returned'), ('reassigned', 'Reassigned')], max_length=16)),
                ('occurred_at', models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asset_assignment_actions', to=settings.AUTH_USER_MODEL)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignment_history', to='assets.asset')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignment_history', to='assets.employee')),
            ],
            options={'ordering': ['-occurred_at', '-pk']},
        ),
        migrations.RunPython(preserve_current_assignments, migrations.RunPython.noop),
    ]
