from database.crud import get_all_gerrit_changes, save_metric
from kpis.gerrit_kpis import *

changes = get_all_gerrit_changes()

for username, value in mean_patchsets(changes).items():
    save_metric(username, "mean_patchsets", value)

for username, value in comments_sent(changes).items():
    save_metric(username, "comments_sent", value)

for username, value in comments_received(changes).items():
    save_metric(username, "comments_received", value)

for username, value in review_requests_sent(changes).items():
    save_metric(username, "reviews_sent", value)

for username, value in review_requests_received(changes).items():
    save_metric(username, "reviews_received", value)