from pulp_replica.app.models import Server
from pulpcore.cli.common.generic import PulpCLIContext
from pulpcore.cli.file.context import (
    PulpFileDistributionContext,
    PulpFilePublicationContext,
    PulpFileRemoteContext,
    PulpFileRepositoryContext,
)

from pulpcore.cli.rpm.context import (
    PulpRpmDistributionContext,
    PulpRpmPublicationContext,
    PulpRpmRemoteContext,
    PulpRpmRepositoryContext,
)


from pulp_file.app.models import FileDistribution, FileRemote, FileRepository
from pulp_file.app.tasks import synchronize as file_synchronize

from pulp_rpm.app.models import RpmDistribution, RpmRemote, RpmRepository
from pulp_rpm.app.tasks import synchronize as rpm_synchronize

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

    def url(self, upstream_distribution):
        return upstream_distribution["base_url"]

    def create_or_update_remote(self, upstream_distribution):

        if not upstream_distribution["repository"] and not upstream_distribution["publication"]:

            return None
        url = self.url(upstream_distribution)
        # Check if there is a remote pointing to this distribution
        try:
            remote = self.remote_model.objects.get(name=upstream_distribution["name"])
            if remote.url != url:
                remote.url = url
                remote.save()
        except self.remote_model.DoesNotExist:
            # Create the remote
            remote = self.remote_model(name=upstream_distribution["name"], url=url)
            remote.save()

        return remote

    def repository_extra_fields(self, remote):
        return {}

    def create_or_update_repository(self, remote):
        try:
            repository = self.repository_model.objects.get(name=remote.name)
            # Update the existing repository with latest values
            repository.remote = remote
            for field_name, value in self.repository_extra_fields(remote).items():
                setattr(repository, field_name, value)
            repository.save()
        except self.repository_model.DoesNotExist:
            repository = self.repository_model(
                name=remote.name, remote=remote, **self.repository_extra_fields(remote)
            )
            repository.save()
        return repository

    def create_or_update_distribution(self, repository, upstream_distribution):
        try:
            distro = self.distribution_model.objects.get(name=upstream_distribution["name"])
            # Check that the distribution has the right repository associated
            if (
                not distro.repository
                or distro.repository.pk != repository.pk
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

    def sync_params(self, repository):
        """This method returns a dict that will be passed as kwargs to the sync task."""
        raise NotImplementedError("Each replicator must supply its own sync params.")

    def sync(self, repository):
        dispatch(
            self.sync_task,
            task_group=self.task_group,
            shared_resources=[repository.remote],
            exclusive_resources=[repository],
            kwargs=self.sync_params(repository),
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

    def url(self, upstream_distribution):
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

    def repository_extra_fields(self, remote):
        return dict(manifest=remote.url.split("/")[-1], autopublish=True)

    def sync_params(self, repository):
        return dict(
            remote_pk=str(repository.remote.pk),
            repository_pk=str(repository.pk),
            mirror=True,
        )


class RpmReplicator(Replicator):
    def __init__(self, pulp_ctx, task_group):
        self.pulp_ctx = pulp_ctx
        self.remote_ctx = PulpRpmRemoteContext
        self.repository_ctx = PulpRpmRepositoryContext
        self.distribution_ctx = PulpRpmDistributionContext
        self.publication_ctx = PulpRpmPublicationContext
        self.app_label = "rpm"
        self.remote_model = RpmRemote
        self.repository_model = RpmRepository
        self.distribution_model = RpmDistribution
        self.serializer_name = "RpmDistributionSerializer"
        self.task_group = task_group
        self.sync_task = rpm_synchronize

    def repository_extra_fields(self, remote):
        # TODO: determine which RPM repository fields should also be included
        return dict(autopublish=True)

    def sync_params(self, repository):
        return dict(
            remote_pk=repository.remote.pk,
            repository_pk=repository.pk,
            sync_policy="mirror_content_only",
            skip_types=[],
            optimize=True,
        )


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
    supported_replicators = [FileReplicator(ctx, task_group), RpmReplicator(ctx, task_group)]

    for replicator in supported_replicators:
        distros = replicator.get_upstream_distributions()

        for distro in distros:
            # Create remote
            remote = replicator.create_or_update_remote(upstream_distribution=distro)
            if not remote:
                # The upstream distribution is not serving any content, cleanup an existing local distribution
                try:
                    local_distro = replicator.distribution_model.objects.get(name=distro["name"])
                    local_distro.repository = None
                    local_distro.publication = None
                    local_distro.save()
                    continue
                except replicator.distribution_model.DoesNotExist:
                    continue
            # Check if there is already a repository
            repository = replicator.create_or_update_repository(remote=remote)

            # Dispatch a sync task
            replicator.sync(repository)

            # Get or create a distribution
            replicator.create_or_update_distribution(repository, distro)
