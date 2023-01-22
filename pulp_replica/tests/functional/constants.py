"""Constants for Pulp Replica plugin tests."""
from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_DISTRIBUTION_PATH,
    BASE_PUBLICATION_PATH,
    BASE_REMOTE_PATH,
    BASE_REPO_PATH,
    BASE_CONTENT_PATH,
)

# FIXME: list any download policies supported by your plugin type here.
# If your plugin supports all download policies, you can import this
# from pulp_smash.pulp3.constants instead.
# DOWNLOAD_POLICIES = ["immediate", "streamed", "on_demand"]
DOWNLOAD_POLICIES = ["immediate"]

# FIXME: replace 'unit' with your own content type names, and duplicate as necessary for each type
REPLICA_CONTENT_NAME = "replica.unit"

# FIXME: replace 'unit' with your own content type names, and duplicate as necessary for each type
REPLICA_CONTENT_PATH = urljoin(BASE_CONTENT_PATH, "replica/units/")

REPLICA_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, "replica/replica/")

REPLICA_REPO_PATH = urljoin(BASE_REPO_PATH, "replica/replica/")

REPLICA_PUBLICATION_PATH = urljoin(BASE_PUBLICATION_PATH, "replica/replica/")

REPLICA_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, "replica/replica/")

# FIXME: replace this with your own fixture repository URL and metadata
REPLICA_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, "replica/")
"""The URL to a replica repository."""

# FIXME: replace this with the actual number of content units in your test fixture
REPLICA_FIXTURE_COUNT = 3
"""The number of content units available at :data:`REPLICA_FIXTURE_URL`."""

REPLICA_FIXTURE_SUMMARY = {REPLICA_CONTENT_NAME: REPLICA_FIXTURE_COUNT}
"""The desired content summary after syncing :data:`REPLICA_FIXTURE_URL`."""

# FIXME: replace this with the location of one specific content unit of your choosing
REPLICA_URL = urljoin(REPLICA_FIXTURE_URL, "")
"""The URL to an replica file at :data:`REPLICA_FIXTURE_URL`."""

# FIXME: replace this with your own fixture repository URL and metadata
REPLICA_INVALID_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, "replica-invalid/")
"""The URL to an invalid replica repository."""

# FIXME: replace this with your own fixture repository URL and metadata
REPLICA_LARGE_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, "replica_large/")
"""The URL to a replica repository containing a large number of content units."""

# FIXME: replace this with the actual number of content units in your test fixture
REPLICA_LARGE_FIXTURE_COUNT = 25
"""The number of content units available at :data:`REPLICA_LARGE_FIXTURE_URL`."""
