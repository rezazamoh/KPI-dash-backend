import json
import subprocess
from datetime import datetime, timedelta
from config import GERRIT_HOST, GERRIT_PORT, GERRIT_USER
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

DEFAULT_options = [
    "--all-reviewers",
    "--comments",
    "--patch-sets",
    "--files",
    "--current-patch-set",
    "--submit-records",
]


def run_command(cmd, timeout=30):
    """Run a subprocess command with UTF-8-safe decoding."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print("[ERROR] SSH connection timed out. Check Gerrit server connectivity.")
        return None
    except Exception as e:
        print(f"[ERROR] SSH execution failed: {str(e)}")
        return None


def fetch_changes_ssh(start_date=None, end_date=None, owner=None, project=None, topic=None, reviewer=None, commenter=None, status=None, issue=None, options=None):
    """
    Fetch Gerrit changes via SSH query with optional filtering parameters.
    
    Args:
        start_date (str|datetime, optional): Start date in YYYY-MM-DD format.
        end_date (str|datetime, optional): End date in YYYY-MM-DD format.
        owner (str, optional): Gerrit owner username filter.
        project (str, optional): Gerrit project filter.
        topic (str, optional): Gerrit topic filter.
        status (str | list[str], optional): Gerrit status filter such as NEW, MERGED, ABANDONED.
    
    Returns:
        list: List of parsed change objects with raw JSON
    """
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "owner": owner,
        "project": project,
        "topic": topic,
        "reviewer": reviewer,
        "commenter": commenter,
        "status": status,
        "issue": issue,
        "options": options,
    }

    #logger.info(
    #    "[FETCH_CHANGES] %s",
    #    " ".join(f"{k}={v}" for k, v in params.items() if v is not None)
    #)
    def format_value(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        return str(value)
    
    def add_query_terms(query_terms, key, value):
        if not value:
            return

        if isinstance(value, str):
            value = [value]

        if key in ("reviewer", "commentby"):
            if len(value) == 1:
                query_terms.append(
                    f'({key}:"{value[0]}" not owner:"{value[0]}")'
                )
            else:
                parts = [
                    f'({key}:"{v}" not owner:"{v}")'
                    for v in value
                ]
                query_terms.append(f"({' OR '.join(parts)})")
            return

        if len(value) == 1:
            query_terms.append(f'{key}:"{value[0]}"')
        else:
            joined = " OR ".join(f'{key}:"{v}"' for v in value)
            query_terms.append(f"({joined})")
    query_terms = []
    formatted_start = format_value(start_date)
    formatted_end = format_value(end_date)

    if formatted_start:
        query_terms.append(f'after:"{formatted_start}"')
    if formatted_end:
        query_terms.append(f'before:"{formatted_end}"')
        
    add_query_terms(query_terms, "owner", owner)
    add_query_terms(query_terms, "reviewer", reviewer)
    add_query_terms(query_terms, "commentby", commenter)
    add_query_terms(query_terms, "project", project)
    add_query_terms(query_terms, "topic", topic)
    add_query_terms(query_terms, "status", status)
    add_query_terms(query_terms, "message", issue)

    if not query_terms:
        fallback_end = datetime.now()
        fallback_start = fallback_end - timedelta(days=365)
        query_terms.extend([
            f'after:"{fallback_start.strftime("%Y-%m-%d")}"',
            f'before:"{fallback_end.strftime("%Y-%m-%d")}"',
        ])

    if options is None:
        options = DEFAULT_options
        
    changes = []
    start = 0
    batch_size = 500

    while True:
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            "-p", str(GERRIT_PORT),
            f"{GERRIT_USER}@{GERRIT_HOST}",
            "gerrit",
            "query",
            *query_terms,
            "--format=JSON",
            "--start", str(start),
            *options,
            "limit:", str(batch_size),
        ]

        print(cmd)
        print(
            f"[DEBUG] Running SSH command to "
            f"{GERRIT_HOST}:{GERRIT_PORT})"
        )
        result = run_command(cmd, timeout=15)

        if result is None:
            print("[ERROR] SSH command returned no result")
            break

        if result.returncode != 0:
            print(
                f"[ERROR] SSH command failed with "
                f"return code {result.returncode}"
            )
            print(f"[ERROR] stderr: {result.stderr}")
            break

        batch_changes = []
        more_changes = False
        line_count = 0

        for line in result.stdout.splitlines():
            line_count += 1

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(
                    f"[WARN] Failed to parse JSON on line "
                    f"{line_count}: {str(e)}"
                )
                continue

            # Gerrit query statistics row
            if obj.get("type") == "stats" or "rowCount" in obj:
                #print(f"[INFO] Batch returned "f"{obj.get('rowCount')} total matches")

                more_changes = obj.get("moreChanges", False)
                continue

            batch_changes.append(dict(obj))

        changes.extend(batch_changes)

        #print( f"[INFO] Processed {line_count} lines " f"from SSH output")
        #print( f"[INFO] Parsed {len(batch_changes)} changes " f"in this batch")
        #print(f"[INFO] Total parsed changes: {len(changes)}")

        if not more_changes:
            break

        # Move to the next page.
        # Use the number actually received rather than assuming
        # that Gerrit returned exactly batch_size changes.
        if not batch_changes:
            print(
                "[WARN] Gerrit reported more changes, "
                "but the current batch contained no changes. "
                "Stopping to avoid an infinite loop."
            )
            break

        start += len(batch_changes)

    print(f"[INFO] Final parsed change count: {len(changes)}")

    return changes


def fetch_changes(
    start_date=None,
    end_date=None,
    owner=None,
    project=None,
    topic=None,
    reviewer=None,
    commenter=None,
    status=None,
    issue=None,
    options=None,
):
    """REST-backed compatibility wrapper for existing call sites."""
    from collectors.gerrit_rest import fetch_changes as rest_fetch_changes

    return rest_fetch_changes(
        start_date=start_date,
        end_date=end_date,
        owner=owner,
        project=project,
        topic=topic,
        reviewer=reviewer,
        commenter=commenter,
        status=status,
        issue=issue,
        options=options,
    )


def fetch_changes_from_json(start_date=None, end_date=None, owner=None, project=None, topic=None, reviewer=None, options=None):
    """
    Fetch Gerrit changes via SSH query with optional filtering parameters.
    
    Args:
        start_date (str|datetime, optional): Start date in YYYY-MM-DD format.
        end_date (str|datetime, optional): End date in YYYY-MM-DD format.
        owner (str, optional): Gerrit owner username filter.
        project (str, optional): Gerrit project filter.
        topic (str, optional): Gerrit topic filter.
    
    Returns:
        list: List of parsed change objects with raw JSON
    """
    print("[DEBUG] READING FROM JSON FILE")

    with open("data/mock_data.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Expected mock_data.json to contain a JSON array")

    changes = data

    print(f"[INFO] Parsed {len(changes)} valid changes")

    return changes

def ls_projects_ssh():
    """Return a list of Gerrit projects via SSH ls-projects."""
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(GERRIT_PORT),
        f"{GERRIT_USER}@{GERRIT_HOST}",
        "gerrit",
        "ls-projects",
    ]

    result = run_command(cmd, timeout=5)
    if result is None:
        return []

    if result.returncode != 0:
        print(f"[ERROR] ls-projects failed with return code {result.returncode}")
        print(f"[ERROR] stderr: {result.stderr}")
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip() and "template" not in line.strip().lower()]


def ls_projects():
    """REST-backed compatibility wrapper for existing call sites."""
    from collectors.gerrit_rest import ls_projects as rest_ls_projects

    return rest_ls_projects()


def ls_groups_ssh():
    """Return a list of Gerrit groups via SSH ls-groups."""
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(GERRIT_PORT),
        f"{GERRIT_USER}@{GERRIT_HOST}",
        "gerrit ls-groups",
    ]

    result = run_command(cmd, timeout=5)
    if result is None:
        return []

    if result.returncode != 0:
        print(f"[ERROR] ls-groups failed with return code {result.returncode}")
        print(f"[ERROR] stderr: {result.stderr}")
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def ls_groups():
    """REST-backed compatibility wrapper for existing call sites."""
    from collectors.gerrit_rest import ls_groups as rest_ls_groups

    return rest_ls_groups()


def ls_members_ssh(group, recursive=False):
    """Return members for a Gerrit group."""

    remote_cmd = f'gerrit ls-members "{group}"'

    if recursive:
        remote_cmd += " --recursive"

    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(GERRIT_PORT),
        f"{GERRIT_USER}@{GERRIT_HOST}",
        remote_cmd,
    ]

    result = run_command(cmd, timeout=30)

    if result is None:
        return []

    if result.returncode != 0:
        print(f"[ERROR] ls-members failed for '{group}'")
        print(f"[ERROR] stderr: {result.stderr}")
        return []

    members = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        fields = line.split("\t")

        if len(fields) >= 2:
            members.append(fields[1].strip())

    return members


def ls_members(group, recursive=False):
    """REST-backed compatibility wrapper for existing call sites."""
    from collectors.gerrit_rest import ls_members as rest_ls_members

    return rest_ls_members(group, recursive=recursive)


def all_members_ssh():
    """Return unique members from all Gerrit groups containing 'Developers'."""

    groups = ls_groups_ssh()

    if not groups:
        print("[WARNING] No Gerrit groups found")
        return []

    developer_groups = [
        group for group in groups
        if "developers" in group.lower()
    ]

    print(
        f"[INFO] Found {len(developer_groups)} groups containing 'Developers'"
    )

    members = set()

    for group in developer_groups:
        group_members = ls_members_ssh(group)

        print(
            f"[INFO] Group '{group}': "
            f"{len(group_members)} members"
        )

        members.update(group_members)

    result = sorted(members)

    print()
    print("=" * 60)
    print(f"Developer groups scanned: {len(developer_groups)}")
    print(f"Total unique members:      {len(result)}")
    print("=" * 60)

    return result


def all_members():
    """REST-backed compatibility wrapper for existing call sites."""
    from collectors.gerrit_rest import all_members as rest_all_members

    return rest_all_members()