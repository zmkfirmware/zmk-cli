"""
Methods for requesting information from a remote Git repository.
"""

import math
import re
import subprocess

import giturlparse

DEFAULT_TIMEOUT = 10


class Remote:
    """Represents a remote Git repository"""

    url: str

    _impl: "_RemoteImpl | None" = None

    def __init__(self, url: str):
        self.url = url

        p = giturlparse.parse(url)

        match p.platform:
            case "github":
                self._impl = _GitHubRemote(p)

    @property
    def firmware_download_url(self) -> str:
        """URL of a page where users can download firmware builds"""
        if self._impl:
            return self._impl.firmware_download_url

        raise NotImplementedError(f"Cannot get download URL for {self.url}")

    def repo_exists(self) -> bool:
        """Get whether the remote URL points to a valid repo"""

        # Git will return a non-zero status code if it can't access the given URL.
        status = subprocess.call(
            ["git", "ls-remote", self.url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return status == 0

    def revision_exists(self, revision: str) -> bool:
        """Get whether the remote repo contains a commit with a given revision"""

        # If the given revision is a tag or branch, then ls-remote can find it.
        # The output will be empty if the revision isn't found.
        if subprocess.check_output(["git", "ls-remote", self.url, revision]):
            return True

        # If the given revision is a (possibly abbreviated) commit hash, then
        # check if it can be fetched from the remote repo without actually
        # fetching it. (This works for commit hashes and tags, but not branches.)
        status = subprocess.call(
            [
                "git",
                "fetch",
                self.url,
                revision,
                "--negotiate-only",
                "--negotiation-tip",
                revision,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return status == 0

    def get_tags(self) -> list[str]:
        """
        Get a list of tags from the remote repo.

        Tags are sorted in descending order by version.
        """
        lines = subprocess.check_output(
            ["git", "ls-remote", "--tags", "--refs", self.url], text=True
        ).splitlines()

        # ls-remote output is "<hash> refs/tags/<tag>" for each tag.
        # Return only the text after "refs/tags/".
        tags = (line.split()[-1].removeprefix("refs/tags/") for line in lines)

        return sorted(
            tags,
            key=_TaggedVersion,
            reverse=True,
        )


class _RemoteImpl:
    """Implementation for platform-specific accessors"""

    @property
    def firmware_download_url(self) -> str:
        """URL of a page where users can download firmware builds"""
        raise NotImplementedError()


class _GitHubRemote(_RemoteImpl):
    """Implementation for GitHub"""

    def __init__(self, parsed: giturlparse.GitUrlParsed):
        self._parsed = parsed

    @property
    def owner(self) -> str:
        """Username of the repo's owner"""
        return self._parsed.owner

    @property
    def repo(self) -> str:
        """Name of the repo"""
        return self._parsed.repo

    @property
    def firmware_download_url(self) -> str:
        return (
            f"https://github.com/{self.owner}/{self.repo}/actions/workflows/build.yml"
        )


class _TaggedVersion:
    major: int | None = None
    minor: int | None = None
    patch: int | None = None

    def __init__(self, tag: str):
        self.tag = tag

        if m := re.match(r"v(\d+)(?:\.(\d+))?(?:\.(\d+))?", self.tag):
            self.major = _try_int(m.group(1))
            self.minor = _try_int(m.group(2))
            self.patch = _try_int(m.group(3))

    def __lt__(self, other: "_TaggedVersion"):
        return self._sort_key < other._sort_key

    @property
    def _sort_key(self):
        return (
            _int_or_inf(self.major),
            _int_or_inf(self.minor),
            _int_or_inf(self.patch),
        )


def _try_int(val: str | None):
    return None if val is None else int(val)


def _int_or_inf(val: int | None):
    return math.inf if val is None else val
