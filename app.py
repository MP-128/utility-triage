"""Utility Asset Triage - a Flask web app for reviewing asset health."""
import hmac

from flask import Flask, render_template, request

from config import ON_VERCEL, local_now, setting
from data_source import ASSET_TYPES, NETWORKS, load_assets
from risk import RATINGS, cv_rating, days_until_maintenance, rate_asset

app = Flask(__name__)

# No scripts are allowed to run at all, which blocks script injection even if some data slipped through.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
}


def _matches(given, expected):
    """Compare secrets in constant time, so response timing doesn't leak how much was right."""
    return hmac.compare_digest((given or "").encode("utf-8"), expected.encode("utf-8"))


@app.before_request
def require_password():
    """Shared-password protection (HTTP Basic Auth), switched on by the APP_PASSWORD environment variable.

    Locally, no password means the app is open. On Vercel, no password means the app refuses to run,
    so a forgotten setting can never leave it public.
    """
    if request.endpoint == "healthz":
        return None
    password = setting("APP_PASSWORD")
    if not password:
        if ON_VERCEL:
            return "Password not configured: set APP_PASSWORD in Vercel, then redeploy.", 503
        return None
    username = setting("APP_USERNAME", "triage")
    auth = request.authorization
    if auth and _matches(auth.username, username) and _matches(auth.password, password):
        return None
    return (
        "Sign-in required.",
        401,
        {"WWW-Authenticate": 'Basic realm="Utility Asset Triage", charset="UTF-8"'},
    )


@app.after_request
def add_security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


def rated_assets(today):
    """Load assets, add rating/reasons/days to each, and sort most urgent first."""
    assets, source = load_assets()
    rows = []
    for asset in assets:
        rating, reasons = rate_asset(asset, today)
        rows.append({**asset, "rating": rating, "reasons": reasons, "days": days_until_maintenance(asset, today)})
    rows.sort(key=lambda row: (RATINGS.index(row["rating"]), row["days"]))
    return rows, source


def current_filters():
    """The dashboard filters from the URL, ignoring blank or unknown values."""
    allowed = {"type": ASSET_TYPES, "network": NETWORKS, "risk": RATINGS}
    return {key: request.args.get(key) for key, options in allowed.items() if request.args.get(key) in options}


@app.template_filter("days_label")
def days_label(days):
    """-5 -> 'Overdue 5 days', 0 -> 'Due today', 23 -> '23 days'."""
    def plural(n):
        return f"{n} day" if n == 1 else f"{n} days"

    if days < 0:
        return f"Overdue {plural(-days)}"
    if days == 0:
        return "Due today"
    return plural(days)


@app.route("/")
def dashboard():
    today = local_now().date()
    rows, source = rated_assets(today)
    filters = current_filters()

    # Tiles count within the chosen type/network, so clicking one narrows the current view.
    in_scope = [
        r for r in rows
        if r["asset_type"] == filters.get("type", r["asset_type"])
        and r["network"] == filters.get("network", r["network"])
    ]
    counts = {rating: sum(1 for r in in_scope if r["rating"] == rating) for rating in RATINGS}
    shown = [r for r in in_scope if r["rating"] == filters.get("risk", r["rating"])]

    return render_template(
        "dashboard.html",
        assets=shown,
        total=len(rows),
        counts=counts,
        filters=filters,
        source=source,
        today=today,
        ratings=RATINGS,
        asset_types=ASSET_TYPES,
        networks=NETWORKS,
    )


@app.route("/asset/<asset_id>")
def asset_detail(asset_id):
    today = local_now().date()
    rows, source = rated_assets(today)
    asset = next((r for r in rows if r["asset_id"] == asset_id), None)
    if asset is None:
        return render_template("404.html", message=f"There is no asset with ID “{asset_id}”.", source=source), 404
    rating, label = cv_rating(asset["cv_health_score"])
    return render_template(
        "asset.html",
        a=asset,
        cv_rating=rating,
        cv_label=label,
        days_since_inspection=(today - asset["last_inspection_date"]).days,
        filters=current_filters(),
        source=source,
        today=today,
    )


@app.route("/healthz")
def healthz():
    """For uptime checks: says the app is running, without touching or revealing any data."""
    return {"status": "ok"}


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, port=5001)
