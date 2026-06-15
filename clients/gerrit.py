import json
import subprocess
from config import *


class GerritClient:

    def _run(self, args):

        cmd = [
            "ssh",
            "-p", str(GERRIT_PORT),
            f"{GERRIT_USER}@{GERRIT_HOST}",
            "gerrit",
        ] + args

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        rows = []

        for line in result.stdout.splitlines():

            try:
                obj = json.loads(line)
            except:
                continue

            if "rowCount" in obj:
                continue

            rows.append(obj)

        return rows

    def get_merged_changes(self, limit=200):

        return self._run([
            "query",
            "status:merged",
            f"limit:{limit}",
            "--patch-sets",
            "--comments",
            "--all-reviewers",
            "--submit-records",
            "--current-patch-set",
            "--format", "JSON"
        ])