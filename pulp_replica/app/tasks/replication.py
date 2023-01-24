from pulp_replica.app.models import Server
from pulpcore.cli.common.generic import PulpCLIContext
from pulpcore.cli.file.context import (
    PulpFileDistributionContext,
    PulpFilePublicationContext,
    PulpFileRemoteContext,
    PulpFileRepositoryContext,
)

from pulp_file.app.models import FileDistribution, FileRemote, FileRepository
from pulp_file.app.tasks import synchronize as file_synchronize

from pulpcore.plugin.models import Task, TaskGroup
from pulpcore.plugin.tasking import dispatch  # , general_create, general_update
from pulpcore.plugin.util import get_url
from pulpcore.constants import TASK_FINAL_STATES, TASK_STATES

from pulpcore.app import tasks


class Replicator:
    def __init__(self, pulp_ctx, task_group):
        """
        Override this method with instances of plugin specific instances of Remote, Repository, and Distribution contexts.
        :param pulp_ctx: PulpReplicaContext
        """
        self.pulp_ctx = pulp_ctx
        self.task_group = task_group
        self.distribution_ctx = None
        self.remote_ctx = None
        self.repository_ctx = None
        self.publication_ctx = None
        self.remote_model = None
        self.repository_model = None
        self.distribution_model = None
        self.distribution_serializer = None
        self.app_label = None
        self.sync_task = None

    def get_upstream_distributions(self):
        return self.distribution_ctx(self.pulp_ctx).list(1000, 0, {})

    def get_url(self, upstream_distribution):
        return upstream_distribution["base_url"]

    def get_or_create_remote(self, upstream_distribution):
        url = self.get_url(upstream_distribution)
        if not url:
            return None
        # Check if there is a remote pointing to this distribution
        try:
            remote = FileRemote.objects.get(name=upstream_distribution["name"])
            if remote.url != url:
                remote.url = url
                remote.save()
        except FileRemote.DoesNotExist:
            # Create the remote
            remote = FileRemote(name=upstream_distribution["name"], url=url)
            remote.save()

        return remote

    def get_repository_extra_fields(self, remote):
        return {}

    def get_or_create_repository(self, remote):
        try:
            repository = self.repository_model.objects.get(name=remote.name)
            # Update the existing repository with latest values
            repository.remote = remote
            for field_name, value in self.get_repository_extra_fields(remote).items():
                setattr(repository, field_name, value)
            repository.save()
        except self.remote_model.DoesNotExist:
            repository = self.repository_model(
                name=remote.name, remote=remote, **self.get_repository_extra_fields(remote)
            )
            repository.save()
        return repository

    def get_or_create_distribution(self, repository, upstream_distribution):
        try:
            distro = self.distribution_model.objects.get(name=upstream_distribution["name"])
            # Check that the distribution has the right repository associated
            if (
                distro.repository.pk != repository.pk
                or distro.base_path == upstream_distribution["base_path"]
            ):
                # Update the distribution
                dispatch(
                    tasks.base.general_update,
                    task_group=self.task_group,
                    exclusive_resources=["/api/v3/distributions/"],
                    args=(distro.pk, self.app_label, self.serializer_name),
                    kwargs={
                        "data": {
                            "name": upstream_distribution["name"],
                            "base_path": upstream_distribution["base_path"],
                            "repository": get_url(repository),
                        }
                    },
                )
        except self.distribution_model.DoesNotExist:
            # Dispatch a task to create the distribution
            dispatch(
                tasks.base.general_create,
                task_group=self.task_group,
                exclusive_resources=["/api/v3/distributions/"],
                args=(self.app_label, self.serializer_name),
                kwargs={
                    "data": {
                        "name": upstream_distribution["name"],
                        "base_path": upstream_distribution["base_path"],
                        "repository": get_url(repository),
                    }
                },
            )

    def sync(self, repository):
        dispatch(
            self.sync_task,
            task_group=self.task_group,
            shared_resources=[repository.remote],
            exclusive_resources=[repository],
            kwargs={
                "remote_pk": str(repository.remote.pk),
                "repository_pk": str(repository.pk),
                "mirror": True,
            },
        )


class FileReplicator(Replicator):
    def __init__(self, pulp_ctx, task_group):
        self.pulp_ctx = pulp_ctx
        self.remote_ctx = PulpFileRemoteContext
        self.repository_ctx = PulpFileRepositoryContext
        self.distribution_ctx = PulpFileDistributionContext
        self.publication_ctx = PulpFilePublicationContext
        self.app_label = "file"
        self.remote_model = FileRemote
        self.repository_model = FileRepository
        self.distribution_model = FileDistribution
        self.serializer_name = "FileDistributionSerializer"
        self.task_group = task_group
        self.sync_task = file_synchronize

    def get_url(self, upstream_distribution):
        # Check if a distribution is repository or publication based
        if upstream_distribution["repository"]:
            manifest = self.repository_ctx(
                self.pulp_ctx, upstream_distribution["repository"]
            ).entity["manifest"]
        elif upstream_distribution["publication"]:
            manifest = self.publication_ctx(self.pulp_ctx, distro["publication"]).entity["manifest"]
        else:
            # This distribution doesn't serve any content
            return None

        return f"{upstream_distribution['base_url']}{manifest}"

    def get_repository_extra_fields(self, remote):
        return dict(manifest=remote.url.split("/")[-1], autopublish=True)


def replicate_distributions(server_pk):
    server = Server.objects.get(pk=server_pk)
    api_kwargs = dict(
        base_url=server.base_url,
        username=server.username,
        password=server.password,
        user_agent="pulpcore-3.22",
    )
    ctx = PulpCLIContext(
        api_root=server.api_root,
        api_kwargs=api_kwargs,
        format="json",
        background_tasks=False,
        timeout=0,
    )
    task_group = TaskGroup.current()
    supported_replicators = [FileReplicator(ctx, task_group)]

    for replicator in supported_replicators:
        distros = replicator.get_upstream_distributions()

        for distro in distros:
            # Create remote
            remote = replicator.get_or_create_remote(upstream_distribution=distro)

            # Check if there is already a repository
            repository = replicator.get_or_create_repository(remote=remote)

            # Dispatch a sync task
            replicator.sync(repository)

            # Get or create a distribution
            replicator.get_or_create_distribution(repository, distro)
