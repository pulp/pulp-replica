from pulp_replica.app.models import Server
from pulpcore.cli.common.generic import PulpCLIContext
from pulpcore.cli.file.context import PulpFileDistributionContext, PulpFilePublicationContext, PulpFileRemoteContext, PulpFileRepositoryContext

from pulp_file.app.models import FileDistribution, FileRemote, FileRepository
from pulp_file.app.tasks import synchronize as file_synchronize

from pulpcore.plugin.models import Task, TaskGroup
from pulpcore.plugin.tasking import dispatch #, general_create, general_update
from pulpcore.plugin.util import get_url
from pulpcore.constants import TASK_FINAL_STATES, TASK_STATES

from pulpcore.app import tasks

def replicate_distributions(server_pk):
    server = Server.objects.get(pk=server_pk)

    api_kwargs = dict(base_url=server.base_url, username=server.username,
                      password=server.password, user_agent="pulpcore-3.22")
    ctx = PulpCLIContext(api_root=server.api_root, api_kwargs=api_kwargs, format="json", background_tasks=False, timeout=0)
    distribution_ctx = PulpFileDistributionContext(ctx)
    distros = distribution_ctx.list(1000, 0, {})

    task_dict = {}
    task_group = TaskGroup.current()
    for distro in distros:
        # Check if a distribution is repository or publication based
        if distro["repository"]:
            manifest = PulpFileRepositoryContext(ctx, distro["repository"]).entity["manifest"]
        elif distro["publication"]:
            manifest = PulpFilePublicationContext(ctx, distro["publication"]).entity["manifest"]
        else:
            # This distribution doesn't serve any content
            continue

        url = f"{distro['base_url']}{manifest}"

        # Check if there is a remote pointing to this distribution
        try:
            remote = FileRemote.objects.get(name=distro["name"])
            if remote.url != url:
                remote.url = url
                remote.save()
        except FileRemote.DoesNotExist:
            # Create the remote
            remote = FileRemote(name=distro["name"], url=url)
            remote.save()

        # Check if there is already a repository
        try:
            repository = FileRepository.objects.get(name=distro["name"])
            if repository.remote.pk != remote.pk or not repository.autopublish:
                repository.remote = remote
                repository.autopublish = True
                repository.save()
        except FileRepository.DoesNotExist:
            repository = FileRepository(name=distro["name"], remote=remote, autopublish=True)
            repository.save()

        try:
            local_distro = FileDistribution.objects.get(name=distro["name"])
            # Check that the distribution has the right repository associated
            if local_distro.repository.pk == repository.pk and local_distro.base_path == distro["base_path"]:
                # Dispatch sync task
                dispatch(
                    file_synchronize,
                    task_group=task_group,
                    shared_resources=[remote],
                    exclusive_resources=[repository],
                    kwargs={
                        "remote_pk": str(remote.pk),
                        "repository_pk": str(repository.pk),
                        "mirror": True,
                    },
                )
            else:
                # Update the distribution
                app_label = "file"
                serializer_name = "FileDistributionSerializer"
                task = dispatch(
                    tasks.base.general_update,
                    task_group=task_group,
                    exclusive_resources=["/api/v3/distributions/"],
                    args=(local_distro.pk, app_label, serializer_name),
                    kwargs={"data": {"name": distro["name"], "base_path": distro["base_path"],
                                     "repository": get_url(repository)}},
                )
                task_dict[str(task.pk)] = distro["name"]
        except FileDistribution.DoesNotExist:
            # Dispatch a task to create the distribution
            app_label = "file"
            serializer_name = "FileDistributionSerializer"
            task = dispatch(
                tasks.base.general_create,
                task_group=task_group,
                exclusive_resources=["/api/v3/distributions/"],
                args=(app_label, serializer_name),
                kwargs={"data": {"name": distro["name"], "base_path": distro["base_path"], "repository": get_url(repository)}},
            )
            task_dict[str(task.pk)] = distro["name"]
    import pydevd_pycharm
    pydevd_pycharm.settrace('host.containers.internal', port=3013, stdoutToServer=True, stderrToServer=True)

    dispatch(check_distribution_and_sync, task_group=task_group, args=(task_dict,))

def check_distribution_and_sync(task_dict):
    import pydevd_pycharm
    pydevd_pycharm.settrace('host.containers.internal', port=3013, stdoutToServer=True, stderrToServer=True)
    tasks = Task.objects.filter(pk__in=list(task_dict.keys()))
    for task in tasks:
        if task.state in TASK_FINAL_STATES:
            if task.state == TASK_STATES.COMPLETED:
                # Sync
                distro = FileDistribution.objects.get()
            task_dict.pop(str(task.pk))
    if task_dict:
        dispatch(check_distribution_and_sync, task_group=task.task_group, args=(task_dict,))
    else:
        task.task_group.finish()
    return
