"""Read the public-records archive at a pinned commit.

The archive is the only input. Everything here reads committed files from a clean checkout of
ericdf/berkeley-public-records and runs the archive's own meeting join (tools/meeting_map.py), so
the rules for which document belongs to which meeting live in one place.
"""
import json
import os
import subprocess
import sys

ARCHIVE_REPO = "ericdf/berkeley-public-records"
ARCHIVE_WEB = f"https://github.com/{ARCHIVE_REPO}"


class ArchiveError(Exception):
    pass


def _git(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise ArchiveError(f"git {' '.join(args)} failed in {root}: {r.stderr.strip()}")
    return r.stdout.strip()


class Archive:
    def __init__(self, root, allow_dirty=False):
        self.root = os.path.abspath(root)
        if not os.path.isfile(os.path.join(self.root, "catalog", "city-council-agendas", "meetings.json")):
            raise ArchiveError(f"{self.root} is not a berkeley-public-records checkout")
        self.commit = _git(self.root, "rev-parse", "HEAD")
        if not allow_dirty and _git(self.root, "status", "--porcelain", "--", "catalog", "manifest", "L2", "tools"):
            raise ArchiveError(f"{self.root} has uncommitted changes; generate from a clean commit")
        self._manifest = {}

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def load(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as f:
            return json.load(f)

    def catalog(self):
        return self.load("catalog", "city-council-agendas", "meetings.json")

    def entry(self, archive_id):
        if archive_id not in self._manifest:
            self._manifest[archive_id] = self.load("manifest", f"{archive_id}.json")
        return self._manifest[archive_id]

    def meeting_map(self):
        """The archive's join of City meetings to archived documents, as its tool computes it."""
        tool = self.path("tools", "meeting_map.py")
        r = subprocess.run([sys.executable, "-I", tool, "--json", "-"], capture_output=True, text=True,
                           cwd=self.root)
        if r.returncode != 0:
            raise ArchiveError(f"tools/meeting_map.py failed: {r.stderr.strip()}")
        return json.loads(r.stdout)

    def archive_url(self, entry):
        """Where a reader opens the archived bytes: the Internet Archive item for an external blob,
        the file in the public repository at the pinned commit otherwise."""
        if entry.get("file"):
            return f"{ARCHIVE_WEB}/blob/{self.commit}/{entry['file']}"
        for copy in (entry.get("blob") or {}).get("copies") or []:
            if copy.get("store") == "internet_archive" and copy.get("item"):
                return f"https://archive.org/details/{copy['item']}"
        return None

    def manifest_url(self, archive_id):
        return f"{ARCHIVE_WEB}/blob/{self.commit}/manifest/{archive_id}.json"
