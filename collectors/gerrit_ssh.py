import json
import subprocess
from datetime import datetime
from config import GERRIT_HOST, GERRIT_PORT, GERRIT_USER


def fetch_changes(start_date, end_date):
    """
    Fetch Gerrit changes via SSH query for a given date range.
    
    Args:
        start_date (str): Start date in format "YYYY-MM-DD" or Gerrit date format
        end_date (str): End date in format "YYYY-MM-DD" or Gerrit date format
    
    Returns:
        list: List of parsed change objects with raw JSON
    """
    
    cmd = [
        "ssh",
        "-p", str(GERRIT_PORT),
        f"{GERRIT_USER}@{GERRIT_HOST}",
        "gerrit",
        "query",
        f'after:"{start_date}"',
        f'before:"{end_date}"',
        "--format=JSON",
        "--all-reviewers",
        "--comments",
        "--patch-sets",
        "--current-patch-set",
        "--submit-records"
    ]

    print(f"[DEBUG] Running SSH command to {GERRIT_HOST}:{GERRIT_PORT}")
    print(f"[DEBUG] Query: after:{start_date} before:{end_date}")

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

        # Parse and enrich the change object
        change = _parse_change(obj)
        changes.append(change)

    print(f"[INFO] Processed {line_count} lines from SSH output")
    print(f"[INFO] Parsed {len(changes)} valid changes")

    return changes


def _parse_change(obj):
    """
    Parse a raw Gerrit change object and extract required fields.
    
    Args:
        obj (dict): Raw Gerrit change object
    
    Returns:
        dict: Parsed change with required fields
    """
    
    # Extract owner information
    owner_data = obj.get("owner", {})
    owner_username = owner_data.get("username", "unknown")
    
    # Extract dates - Gerrit timestamps are in seconds since epoch
    created_timestamp = obj.get("createdOn", 0)
    updated_timestamp = obj.get("lastUpdated", 0)
    
    created_at = datetime.fromtimestamp(created_timestamp) if created_timestamp else None
    updated_at = datetime.fromtimestamp(updated_timestamp) if updated_timestamp else None
    
    # Build the parsed change object
    change = {
        "id": obj.get("id"),
        "change_number": obj.get("number"),
        "project": obj.get("project"),
        "owner": owner_data,
        "status": obj.get("status"),
        "created_at": created_at,
        "updated_at": updated_at,
        # Keep full raw JSON for analysis
        "raw_json": obj
    }
    
    return change
