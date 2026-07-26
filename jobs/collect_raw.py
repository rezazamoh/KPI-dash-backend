from datetime import datetime, timedelta
from collectors.gerrit_ssh import fetch_changes , fetch_changes_from_json
from database.crud import upsert_gerrit_change


def collect_gerrit_changes(start_date=None, end_date=None):
    """
    Collect Gerrit changes from SSH query and store in database.
    
    Args:
        start_date (str): Start date in format "YYYY-MM-DD". 
                         Defaults to 30 days ago if not provided.
        end_date (str): End date in format "YYYY-MM-DD". 
                       Defaults to today if not provided.
    """
    
    # Set default date range if not provided
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    if not start_date:
        thirty_days_ago = datetime.now() - timedelta(days=30)
        start_date = thirty_days_ago.strftime("%Y-%m-%d")
    
    print(f"Fetching Gerrit changes from {start_date} to {end_date}")
    
    # Fetch changes from Gerrit via SSH
    #changes = fetch_changes(start_date, end_date)
    changes = fetch_changes_from_json(start_date, end_date)
    
    # Upsert each change into the database
    for change in changes:
        upsert_gerrit_change(change)
    
    print(f"Successfully loaded {len(changes)} Gerrit changes into database")


if __name__ == "__main__":
    collect_gerrit_changes()