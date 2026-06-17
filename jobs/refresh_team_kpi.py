from database.crud import get_gerrit_changes
from database.crud import save_team_snapshot

from kpis.team_kpis import build_team_graph


changes = get_gerrit_changes()

team_graph = build_team_graph(changes)

save_team_snapshot(team_graph)