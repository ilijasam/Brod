# Slavonski Brod Weather App (Python)

A Flask web app that loads historical weather data for Slavonski Brod using the Open-Meteo Archive API.

## Features

- Select `from` and `to` date range.
- Select last `N` years to compare.
- Show table with average, minimum, and maximum temperature per year.
- Open daily average temperature chart in a new tab.
- Open hourly temperature chart in a new tab.
- Graph Y-axis fixed to **-5°C to 30°C**.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://localhost:8000>.

## Render.com start command

```bash
gunicorn app:app
```
