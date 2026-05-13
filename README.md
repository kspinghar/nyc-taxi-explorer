---
title: NYC Taxi Query Explorer
emoji: 🚕
colorFrom: yellow
colorTo: green
sdk: gradio
sdk_version: 4.44.1
python_version: "3.10"
app_file: app.py
pinned: false
license: mit
---

# NYC Taxi Query Explorer

Companion demo to a PySpark coursework project that processed 2020–2024 NYC Yellow + Green Taxi trip records. The full pipeline ran on Spark over Parquet ingest; this Space ships the cleaned SQLite samples the pipeline produced and lets you replay the EDA queries against them. Pick a query from the dropdown and see the SQL, the result table, and an inline chart.

## What this demo does

- Bundled data: cleaned SQLite samples of NYC Yellow Taxi (~1.6k trips) and Green Taxi (~500 trips), Jan 2020.
- Eight pre-built EDA queries lifted from the original coursework notebook (top pickup zones, fare-by-distance, hour-of-day distribution, weekend vs weekday, payment-method mix, long-trip averages, etc.).
- Each query is executed live against the SQLite sample with `sqlite3` — the results render as a table plus an auto-chosen chart (bar, line, or pie depending on shape).
- A "Show SQL" toggle reveals the underlying query so you can see what's actually running.

## Pipeline (the bigger story)

The full coursework pipeline:
1. **Ingest** — Parquet downloads of 2020–2024 Yellow + Green Taxi trip records.
2. **PySpark processing** — schema standardization, null handling, fare-cleansing, feature engineering (time-based features, distance bins, one-hot encoding of categoricals).
3. **Persist** — write cleaned data back out as SQLite for downstream consumption (the files this Space loads).
4. **EDA + ML** — Spark SQL aggregations + a Spark ML linear regression to predict `fare_amount`.

The Space replays step 4's EDA portion against the persisted samples.

## Source code

https://github.com/kspinghar/nyc-taxi-explorer
