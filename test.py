from api.utils import load_changes
from kpis.gerrit_kpis import _reviewer_added_ts

changes = load_changes(live=True,start_date=None,end_date=None,reviewer='a.amani')
for c in changes[:5]:
    added = _reviewer_added_ts(c, 'a.amani')
    first_comment = None
    for cm in c.get('comments', []):
        if cm.get('reviewer',{}).get('username') == 'a.amani':
            ts = cm.get('timestamp')
            if first_comment is None or ts < first_comment:
                first_comment = ts
    print(f'change={c.get("number")}: added_ts={added}, first_comment_ts={first_comment}, ok={first_comment and added and first_comment > added}')