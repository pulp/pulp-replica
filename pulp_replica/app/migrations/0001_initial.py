# Generated by Django 3.2.16 on 2023-01-22 19:15

from django.db import migrations, models
import django_lifecycle.mixins
import pulpcore.app.models.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Server',
            fields=[
                ('pulp_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('pulp_created', models.DateTimeField(auto_now_add=True)),
                ('pulp_last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.TextField(db_index=True, unique=True)),
                ('base_url', models.TextField()),
                ('api_root', models.TextField(default='pulp')),
                ('ca_cert', models.TextField(null=True)),
                ('client_cert', models.TextField(null=True)),
                ('client_key', pulpcore.app.models.fields.EncryptedTextField(null=True)),
                ('tls_validation', models.BooleanField(default=True)),
                ('username', pulpcore.app.models.fields.EncryptedTextField(null=True)),
                ('password', pulpcore.app.models.fields.EncryptedTextField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
    ]