"""
app.py — NYC Taxi query explorer.

Each query in QUERIES is a small dict with the SQL, the source table, and a
chart hint. The app runs the SQL against the bundled SQLite sample and
renders the result as a table plus an auto-chosen chart.
"""

import sqlite3
import tempfile
from pathlib import Path

import gradio as gr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ART = Path(__file__).parent / "artifacts"
DB_YELLOW = ART / "nyc_yellow_taxi_sample.db"
DB_GREEN = ART / "nyc_green_taxi_sample.db"


# ─────────────────────────────────────────────────────────────
# Pre-built queries (replays of the coursework's Task 4 EDA)
# ─────────────────────────────────────────────────────────────
QUERIES = {
    "Top 10 pickup zones (yellow)": {
        "db": "yellow",
        "sql": (
            "SELECT PULocationID, COUNT(*) AS trip_count "
            "FROM yellow_taxi_data "
            "GROUP BY PULocationID "
            "ORDER BY trip_count DESC "
            "LIMIT 10"
        ),
        "chart": "bar",
        "x": "PULocationID",
        "y": "trip_count",
        "title": "Top 10 yellow-taxi pickup zones (by trip count)",
    },
    "Trips by hour of day (yellow)": {
        "db": "yellow",
        "sql": (
            "SELECT CAST(strftime('%H', tpep_pickup_datetime) AS INTEGER) AS hour, "
            "COUNT(*) AS trip_count "
            "FROM yellow_taxi_data "
            "GROUP BY hour "
            "ORDER BY hour"
        ),
        "chart": "line",
        "x": "hour",
        "y": "trip_count",
        "title": "Yellow-taxi trips by hour of day",
    },
    "Average fare by distance bin (yellow)": {
        "db": "yellow",
        "sql": (
            "SELECT CASE "
            " WHEN trip_distance < 1 THEN '0–1 mi' "
            " WHEN trip_distance < 3 THEN '1–3 mi' "
            " WHEN trip_distance < 5 THEN '3–5 mi' "
            " WHEN trip_distance < 10 THEN '5–10 mi' "
            " ELSE '10+ mi' END AS distance_bin, "
            "ROUND(AVG(fare_amount), 2) AS avg_fare, "
            "COUNT(*) AS trips "
            "FROM yellow_taxi_data "
            "GROUP BY distance_bin "
            "ORDER BY MIN(trip_distance)"
        ),
        "chart": "bar",
        "x": "distance_bin",
        "y": "avg_fare",
        "title": "Average yellow-taxi fare by distance bin",
    },
    "Top 5 drop-off zones by avg fare (yellow)": {
        "db": "yellow",
        "sql": (
            "SELECT DOLocationID, "
            "ROUND(AVG(fare_amount), 2) AS avg_fare, "
            "COUNT(*) AS trips "
            "FROM yellow_taxi_data "
            "GROUP BY DOLocationID "
            "HAVING trips >= 5 "
            "ORDER BY avg_fare DESC "
            "LIMIT 5"
        ),
        "chart": "bar",
        "x": "DOLocationID",
        "y": "avg_fare",
        "title": "Top 5 drop-off zones by average yellow-taxi fare (≥5 trips)",
    },
    "Weekend vs weekday trips (yellow)": {
        "db": "yellow",
        "sql": (
            "SELECT CASE "
            "  WHEN CAST(strftime('%w', tpep_pickup_datetime) AS INTEGER) IN (0, 6) "
            "    THEN 'Weekend' ELSE 'Weekday' END AS day_type, "
            "COUNT(*) AS trip_count, "
            "ROUND(AVG(fare_amount), 2) AS avg_fare "
            "FROM yellow_taxi_data "
            "GROUP BY day_type"
        ),
        "chart": "bar",
        "x": "day_type",
        "y": "trip_count",
        "title": "Yellow-taxi trip counts — weekend vs weekday",
    },
    "Average fare for trips > 10 miles (yellow)": {
        "db": "yellow",
        "sql": (
            "SELECT "
            "ROUND(AVG(fare_amount), 2) AS avg_fare_over_10mi, "
            "ROUND(AVG(total_amount), 2) AS avg_total_over_10mi, "
            "COUNT(*) AS trips "
            "FROM yellow_taxi_data "
            "WHERE trip_distance > 10"
        ),
        "chart": "table",
        "title": "Yellow-taxi long trips (>10 mi) — averages",
    },
    "Most common payment method (yellow)": {
        "db": "yellow",
        "sql": (
            "SELECT payment_type, COUNT(*) AS trips "
            "FROM yellow_taxi_data "
            "GROUP BY payment_type "
            "ORDER BY trips DESC"
        ),
        "chart": "pie",
        "label": "payment_type",
        "value": "trips",
        "title": "Yellow-taxi payment methods (1 = credit card · 2 = cash · 3 = no charge · 4 = dispute)",
    },
    "Yellow vs Green — average fare & trip count": {
        "db": "both",
        "sql": (
            "SELECT 'Yellow' AS taxi_type, COUNT(*) AS trips, "
            "ROUND(AVG(fare_amount), 2) AS avg_fare "
            "FROM yellow_taxi_data "
            "UNION ALL "
            "SELECT 'Green' AS taxi_type, COUNT(*) AS trips, "
            "ROUND(AVG(fare_amount), 2) AS avg_fare "
            "FROM green_taxi_data"
        ),
        "chart": "bar",
        "x": "taxi_type",
        "y": "avg_fare",
        "title": "Yellow vs Green — average fare per trip",
    },
}


# ─────────────────────────────────────────────────────────────
def _run_sql(query_name):
    q = QUERIES[query_name]
    if q["db"] == "yellow":
        conn = sqlite3.connect(DB_YELLOW)
    elif q["db"] == "green":
        conn = sqlite3.connect(DB_GREEN)
    else:
        # Attach both DBs into one connection.
        conn = sqlite3.connect(":memory:")
        conn.execute(f"ATTACH DATABASE '{DB_YELLOW}' AS y")
        conn.execute(f"ATTACH DATABASE '{DB_GREEN}' AS g")
        # Create views in the main DB pointing to the attached tables.
        conn.execute("CREATE VIEW yellow_taxi_data AS SELECT * FROM y.yellow_taxi_data")
        conn.execute("CREATE VIEW green_taxi_data AS SELECT * FROM g.green_taxi_data")
    df = pd.read_sql_query(q["sql"], conn)
    conn.close()
    return df


def _save_fig(fig):
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.tight_layout()
    fig.savefig(tmp.name, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return tmp.name


def _render_chart(df, q):
    chart = q["chart"]
    title = q.get("title", "")

    if chart == "table":
        # No chart — return None for image.
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))

    if chart == "bar":
        x_col, y_col = q["x"], q["y"]
        x_vals = df[x_col].astype(str).tolist()
        y_vals = df[y_col].tolist()
        bars = ax.bar(x_vals, y_vals, color="#fbbf24", edgecolor="#92400e")
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h, f"{h:g}",
                    ha="center", va="bottom", fontsize=9)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        if len(x_vals) > 6:
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    elif chart == "line":
        x_col, y_col = q["x"], q["y"]
        ax.plot(df[x_col], df[y_col], marker="o", color="#0ea5e9", linewidth=2)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.grid(True, alpha=0.3)
        ax.set_xticks(df[x_col])

    elif chart == "pie":
        label_col, value_col = q["label"], q["value"]
        ax.pie(df[value_col], labels=df[label_col].astype(str),
               autopct="%1.1f%%", colors=["#fbbf24", "#10b981", "#6366f1", "#ef4444", "#94a3b8"])

    ax.set_title(title, fontsize=11)
    return _save_fig(fig)


def run_query(query_name):
    q = QUERIES[query_name]
    df = _run_sql(query_name)
    plot_path = _render_chart(df, q)

    sql_md = (
        f"### {q.get('title', query_name)}\n\n"
        f"**SQL**\n\n"
        f"```sql\n{q['sql']}\n```\n\n"
        f"**Rows returned:** {len(df)}"
    )
    return sql_md, df, plot_path


# ─────────────────────────────────────────────────────────────
with gr.Blocks(theme=gr.themes.Soft(), title="NYC Taxi Query Explorer") as demo:
    gr.Markdown(
        "# NYC Taxi Query Explorer\n"
        "Replay of EDA queries from a PySpark coursework pipeline. Pick a pre-built query — "
        "the app runs it against the bundled SQLite samples and shows the SQL, the result table, "
        "and a chart. The original pipeline ran the same logic on Spark over 2020–2024 Parquet "
        "ingest; what you're querying here is the persisted SQLite output."
    )

    with gr.Row():
        query_dd = gr.Dropdown(
            choices=list(QUERIES.keys()),
            value=list(QUERIES.keys())[0],
            label="Query",
        )
        run_btn = gr.Button("Run query", variant="primary", size="sm")

    sql_view = gr.Markdown()
    result_table = gr.Dataframe(label="Results", interactive=False, wrap=True)
    chart = gr.Image(label="Chart", type="filepath", show_download_button=False)

    run_btn.click(run_query, inputs=query_dd, outputs=[sql_view, result_table, chart])
    query_dd.change(run_query, inputs=query_dd, outputs=[sql_view, result_table, chart])

if __name__ == "__main__":
    demo.launch(show_api=False)
