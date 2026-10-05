"""Triage rules: decides how urgent each asset is. Kept apart from the web pages so it's easy to test and change.

Every function takes `today` as an argument, so results are deterministic and easy to test.
"""

RATINGS = ["Critical", "High", "Medium", "Low"]  # most to least severe


def days_until_maintenance(asset, today):
    """Days from today to the next scheduled maintenance. Negative means overdue."""
    return (asset["next_maintenance_date"] - today).days


def _days(n):
    return f"{n} day" if n == 1 else f"{n} days"


def time_rating(days):
    """Rating from how soon maintenance is due."""
    if days < 0:
        return "Critical"
    if days <= 60:
        return "High"
    if days <= 120:
        return "Medium"
    return "Low"


def cv_rating(score):
    """Rating and a plain-English label from the computer-vision health score (100 = perfect)."""
    if score < 20:
        return "Critical", "very poor"
    if score < 40:
        return "High", "poor"
    if score < 60:
        return "Medium", "fair"
    return "Low", "good"


def rate_asset(asset, today):
    """Return (rating, reasons). The more severe of the time and CV signals wins."""
    days = days_until_maintenance(asset, today)
    score = asset["cv_health_score"]
    by_time = time_rating(days)
    by_cv, cv_label = cv_rating(score)

    reasons = []
    if by_time != "Low":
        if days < 0:
            reasons.append(f"Maintenance overdue by {_days(-days)}")
        elif days == 0:
            reasons.append("Maintenance due today")
        else:
            reasons.append(f"Maintenance due in {_days(days)}")
    if by_cv != "Low":
        reasons.append(f"CV health {score}/100 ({cv_label})")
    if not reasons:
        reasons.append(f"No issues: maintenance in {_days(days)}, CV health {score}/100")

    rating = min(by_time, by_cv, key=RATINGS.index)
    return rating, reasons


if __name__ == "__main__":
    from config import local_now
    from data_source import load_assets

    today = local_now().date()
    assets, info = load_assets()
    print(f"{len(assets)} assets ({info['mode']}), rated as of {today}\n")
    rated = sorted(
        ((rate_asset(a, today), a) for a in assets),
        key=lambda item: (RATINGS.index(item[0][0]), days_until_maintenance(item[1], today)),
    )
    print(f"{'Asset':<10}{'Type':<15}{'Network':<14}{'Days':>6}{'CV':>5}  {'Rating':<10}Reasons")
    print("-" * 110)
    for (rating, reasons), a in rated:
        print(
            f"{a['asset_id']:<10}{a['asset_type']:<15}{a['network']:<14}"
            f"{days_until_maintenance(a, today):>6}{a['cv_health_score']:>5}  {rating:<10}{'; '.join(reasons)}"
        )
    counts = {r: sum(1 for (rating, _), _a in rated if rating == r) for r in RATINGS}
    print("\nCounts:", ", ".join(f"{r} {n}" for r, n in counts.items()))
    missing = [r for r, n in counts.items() if n == 0]
    print("All four ratings present." if not missing else f"Missing ratings: {', '.join(missing)}")
