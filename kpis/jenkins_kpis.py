def build_success_rate(builds):

    if not builds:
        return 0

    success = sum(
        1 for b in builds
        if b.get("result") == "SUCCESS"
    )

    return success * 100 / len(builds)


def average_build_duration(builds):

    durations = [
        b.get("duration", 0)
        for b in builds
        if b.get("duration")
    ]

    if not durations:
        return 0

    return sum(durations) / len(durations) / 60000