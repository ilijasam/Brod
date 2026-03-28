from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import plotly.graph_objects as go
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

LATITUDE = 45.16
LONGITUDE = 18.01
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


@dataclass
class YearlyDailySeries:
    year: int
    times: list[str]
    mean: list[float]
    min_values: list[float]
    max_values: list[float]


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def safe_replace_year(original: date, target_year: int) -> date:
    try:
        return original.replace(year=target_year)
    except ValueError:
        # Handle 29-Feb in non-leap years by clamping to 28-Feb
        return original.replace(year=target_year, day=28)


def make_year_ranges(from_date: date, to_date: date, years: int) -> list[tuple[int, date, date]]:
    duration = (to_date - from_date).days
    end_year = to_date.year
    ranges: list[tuple[int, date, date]] = []

    for offset in range(years):
        year = end_year - offset
        start = safe_replace_year(from_date, year)
        end = start + timedelta(days=duration)
        ranges.append((year, start, end))

    return ranges


def fetch_daily_series(from_date: date, to_date: date, years: int) -> list[YearlyDailySeries]:
    results: list[YearlyDailySeries] = []

    for year, start, end in make_year_ranges(from_date, to_date, years):
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "temperature_2m_mean,temperature_2m_min,temperature_2m_max",
            "timezone": "Europe/Zagreb",
        }
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        daily = payload.get("daily") or {}
        times = daily.get("time") or []
        mean = daily.get("temperature_2m_mean") or []
        min_values = daily.get("temperature_2m_min") or []
        max_values = daily.get("temperature_2m_max") or []

        if times and mean and min_values and max_values:
            results.append(
                YearlyDailySeries(
                    year=year,
                    times=times,
                    mean=[float(x) for x in mean],
                    min_values=[float(x) for x in min_values],
                    max_values=[float(x) for x in max_values],
                )
            )

    return sorted(results, key=lambda item: item.year)


def fetch_hourly_series(from_date: date, to_date: date, years: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for year, start, end in make_year_ranges(from_date, to_date, years):
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": "temperature_2m",
            "timezone": "Europe/Zagreb",
        }

        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        values = hourly.get("temperature_2m") or []

        if times and values:
            output.append({
                "year": year,
                "times": times,
                "values": [float(x) for x in values],
            })

    return sorted(output, key=lambda item: item["year"])


def build_daily_plot_html(series: list[YearlyDailySeries]) -> str:
    figure = go.Figure()

    for item in series:
        figure.add_trace(
            go.Scatter(
                x=list(range(1, len(item.mean) + 1)),
                y=item.mean,
                mode="lines",
                name=str(item.year),
            )
        )

    figure.update_layout(
        title="Daily Average Temperature by Year",
        xaxis_title="Day in selected period",
        yaxis_title="Temperature (°C)",
        yaxis=dict(range=[-5, 30]),
        template="plotly_white",
    )
    return figure.to_html(full_html=False, include_plotlyjs="cdn")


def build_hourly_plot_html(series: list[dict[str, Any]]) -> str:
    figure = go.Figure()

    for item in series:
        values = item["values"]
        figure.add_trace(
            go.Scatter(
                x=list(range(1, len(values) + 1)),
                y=values,
                mode="lines",
                name=str(item["year"]),
            )
        )

    figure.update_layout(
        title="Hourly Temperature by Year",
        xaxis_title="Hour in selected period",
        yaxis_title="Temperature (°C)",
        yaxis=dict(range=[-5, 30]),
        template="plotly_white",
    )
    return figure.to_html(full_html=False, include_plotlyjs="cdn")


@app.get("/")
def home() -> str:
    today = datetime.now(tz=timezone.utc).date()
    default_from = today - timedelta(days=6)

    from_value = request.args.get("from", default_from.isoformat())
    to_value = request.args.get("to", today.isoformat())
    years_value = request.args.get("years", "5")

    from_date = parse_date(from_value)
    to_date = parse_date(to_value)

    summary_rows: list[dict[str, str | int | float]] = []
    error: str | None = None

    try:
        years = int(years_value)
    except ValueError:
        years = 5

    if years < 1 or years > 30:
        years = 5

    if from_date and to_date:
        if from_date > to_date:
            error = "From date must be before or equal to To date."
        else:
            try:
                daily_series = fetch_daily_series(from_date, to_date, years)
                for item in daily_series:
                    summary_rows.append(
                        {
                            "year": item.year,
                            "avg": round(sum(item.mean) / len(item.mean), 2),
                            "min": round(min(item.min_values), 2),
                            "max": round(max(item.max_values), 2),
                        }
                    )
            except requests.RequestException:
                error = "Failed to fetch weather data from Open-Meteo. Please try again."

    return render_template(
        "index.html",
        from_value=from_value,
        to_value=to_value,
        years_value=years,
        summary_rows=summary_rows,
        error=error,
    )


@app.get("/plot/daily")
def plot_daily() -> str:
    from_value = request.args.get("from", "")
    to_value = request.args.get("to", "")
    years_value = request.args.get("years", "5")

    from_date = parse_date(from_value)
    to_date = parse_date(to_value)
    years = int(years_value)

    if not from_date or not to_date or from_date > to_date:
        return "Invalid date range", 400

    series = fetch_daily_series(from_date, to_date, years)
    plot_html = build_daily_plot_html(series)
    return render_template("plot.html", title="Daily Average Temperature", plot_html=plot_html)


@app.get("/plot/hourly")
def plot_hourly() -> str:
    from_value = request.args.get("from", "")
    to_value = request.args.get("to", "")
    years_value = request.args.get("years", "5")

    from_date = parse_date(from_value)
    to_date = parse_date(to_value)
    years = int(years_value)

    if not from_date or not to_date or from_date > to_date:
        return "Invalid date range", 400

    series = fetch_hourly_series(from_date, to_date, years)
    plot_html = build_hourly_plot_html(series)
    return render_template("plot.html", title="Hourly Temperature", plot_html=plot_html)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
