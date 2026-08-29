import builtins
from datetime import datetime

_original_print = builtins.print


def _timestamped_print(*args, **kwargs):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _original_print(f"[{timestamp}]", *args, **kwargs)


builtins.print = _timestamped_print
