from pulpcore.plugin import PulpPluginAppConfig


class PulpReplicaPluginAppConfig(PulpPluginAppConfig):
    """Entry point for the replica plugin."""

    name = "pulp_replica.app"
    label = "replica"
    version = "0.1.0a1.dev"
    python_package_name = "pulp-replica"
