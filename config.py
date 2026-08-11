import os
from pathlib import Path


def _load_dotenv() -> None:
    dotenv_path = Path(__file__).resolve().parent / ".env"
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


# Gerrit
GERRIT_HOST = os.getenv("GERRIT_HOST", "")
GERRIT_PORT = int(os.getenv("GERRIT_PORT", ""))
GERRIT_USER = os.getenv("GERRIT_USER", "")
GERRIT_REST_URL = os.getenv("GERRIT_REST_URL", "")
GERRIT_HTTP_USER = os.getenv("GERRIT_HTTP_USER", "")
GERRIT_HTTP_PASSWORD = os.getenv("GERRIT_HTTP_PASSWORD", "")

# Jenkins
JENKINS_URL = os.getenv("JENKINS_URL", "")
JENKINS_USER = os.getenv("JENKINS_USER", "")
JENKINS_TOKEN = os.getenv("JENKINS_TOKEN", "")

# Jira (mock for now, real later)
JIRA_URL = os.getenv("JIRA_URL", "")
JIRA_USER = os.getenv("JIRA_USER", "")
JIRA_PASSWORD = os.getenv("JIRA_PASSWORD", "")