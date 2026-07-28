import json
import subprocess
from datetime import datetime, timedelta
from config import GERRIT_HOST, GERRIT_PORT, GERRIT_USER


DEFAULT_options = [
    "--all-reviewers",
    "--comments",
    "--patch-sets",
    "--current-patch-set",
    "--submit-records",
]


def fetch_changes(start_date=None, end_date=None, owner=None, project=None, topic=None, reviewer=None, commenter=None, options=None):
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

    if not query_terms:
        fallback_end = datetime.now()
        fallback_start = fallback_end - timedelta(days=365)
        query_terms.extend([
            f'after:"{fallback_start.strftime("%Y-%m-%d")}"',
            f'before:"{fallback_end.strftime("%Y-%m-%d")}"',
        ])

    if options is None:
        options = DEFAULT_options

    cmd = [
        "ssh",
        "-p", str(GERRIT_PORT),
        f"{GERRIT_USER}@{GERRIT_HOST}",
        "gerrit",
        "query",
        *query_terms,
        "--format=JSON",
        *options,
    ]
    print(cmd)
    print(f"[DEBUG] Running SSH command to {GERRIT_HOST}:{GERRIT_PORT}")
    if query_terms:
        print(f"[DEBUG] Query terms: {' '.join(query_terms)}")
    else:
        print("[DEBUG] Query terms: <no filters>")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        print("[ERROR] SSH connection timed out. Check Gerrit server connectivity.")
        return []
    except Exception as e:
        print(f"[ERROR] SSH execution failed: {str(e)}")
        return []

    # Check for SSH errors
    if result.returncode != 0:
        print(f"[ERROR] SSH command failed with return code {result.returncode}")
        print(f"[ERROR] stderr: {result.stderr}")
        return []

    changes = []
    line_count = 0

    for line in result.stdout.splitlines():
        line_count += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[WARN] Failed to parse JSON on line {line_count}: {str(e)}")
            continue

        # Skip Gerrit statistics row
        if "rowCount" in obj:
            print(f"[INFO] Query returned {obj.get('rowCount')} total matches")
            continue

        changes.append(dict(obj))

    print(f"[INFO] Processed {line_count} lines from SSH output")
    print(f"[INFO] Parsed {len(changes)} valid changes")

    return changes

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
    print(f"[DEBUG] READING FROM JSON FILE")
    changes = []
    line_count = 0

    with open("data/last_300_changes.json", "r") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Failed to parse JSON on line {line_count}: {str(e)}")
                continue

            # Skip Gerrit statistics row
            if "rowCount" in obj:
                print(f"[INFO] Query returned {obj.get('rowCount')} total matches")
                continue

            changes.append(dict(obj))

    print(f"[INFO] Processed {line_count} lines from SSH output")
    print(f"[INFO] Parsed {len(changes)} valid changes")

    return changes


def ls_projects():
    """Return a list of Gerrit projects via SSH ls-projects."""
    cmd = [
        "ssh",
        "-p", str(GERRIT_PORT),
        f"{GERRIT_USER}@{GERRIT_HOST}",
        "gerrit",
        "ls-projects",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print("[ERROR] SSH connection timed out while listing projects.")
        return []
    except Exception as e:
        print(f"[ERROR] SSH execution failed while listing projects: {str(e)}")
        return []

    if result.returncode != 0:
        print(f"[ERROR] ls-projects failed with return code {result.returncode}")
        print(f"[ERROR] stderr: {result.stderr}")
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


