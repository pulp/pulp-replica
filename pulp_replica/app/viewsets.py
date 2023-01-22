"""
Check `Plugin Writer's Guide`_ for more details.

.. _Plugin Writer's Guide:
    https://docs.pulpproject.org/pulpcore/plugins/plugin-writer/index.html
"""
from . import models, serializers, tasks

from drf_spectacular.utils import extend_schema
from rest_framework import mixins
from rest_framework.decorators import action

from pulpcore.plugin.models import TaskGroup
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.viewsets import NamedModelViewSet, OperationPostponedResponse
from pulpcore.tasking.tasks import dispatch


class ServerViewSet(
    NamedModelViewSet,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
):
    queryset = models.Server.objects.all()
    endpoint_name = "servers"
    serializer_class = serializers.ServerSerializer
    ordering = "-pulp_created"

    @extend_schema(
        description="Trigger an asynchronous repository replication task group.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"])
    def replicate(self, request, pk):
        """
        Triggers an asynchronous repository replication operation.
        """
        server = models.Server.objects.get(pk=pk)
        task_group = TaskGroup.objects.create(description=f"Replication of {server.name}")

        task = dispatch(
            tasks.replicate_distributions,
            exclusive_resources=["/pulp/api/v3/pulpservers/"],
            kwargs={"server_pk": pk},
            task_group=task_group,
        )

        return OperationPostponedResponse(task, request)
