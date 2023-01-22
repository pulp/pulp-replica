"""
Check `Plugin Writer's Guide`_ for more details.

.. _Plugin Writer's Guide:
    https://docs.pulpproject.org/pulpcore/plugins/plugin-writer/index.html
"""

from logging import getLogger

from django.db import models
from pulpcore.plugin.models import BaseModel, EncryptedTextField


class Server(BaseModel):
    name = models.TextField(db_index=True, unique=True)

    base_url = models.TextField()
    api_root = models.TextField(default="pulp")

    ca_cert = models.TextField(null=True)
    client_cert = models.TextField(null=True)
    client_key = EncryptedTextField(null=True)
    tls_validation = models.BooleanField(default=True)

    username = EncryptedTextField(null=True)
    password = EncryptedTextField(null=True)
