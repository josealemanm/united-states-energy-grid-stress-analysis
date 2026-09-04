"""
06_build_dashboard.py
Builds a standalone interactive HTML dashboard from the star schema, and
PNG screenshots of the key pages for the README.

This exists because Power BI Desktop has no macOS build, so the dashboard
phase of the guide (Part 9-11) was adapted from Power BI to Plotly. The
underlying star schema in data/processed/*.parquet is still Power BI-ready:
follow Part 9-11 of docs/TUTORIAL_FROM_SCRATCH.md on Windows to load it there instead.

Run:  python src/06_build_dashboard.py   (after 04_export_for_bi.py)
"""

from pathlib import Path
import duckdb
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

DB_PATH = Path("data/interim/grid.duckdb")
MANIFEST_PATH = Path("reports/pull_manifest.csv")
OUT_HTML = Path("powerbi/dashboard.html")
SCREEN_DIR = Path("docs/screenshots")
SCREEN_DIR.mkdir(parents=True, exist_ok=True)

ACCENT_DEMAND = "#2E5EAA"
ACCENT_FORECAST = "#E8A33D"
GREY = "#8C8C8C"
RED = "#C0392B"
TEMPLATE = "plotly_white"

def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    manifest = pd.read_csv(MANIFEST_PATH)
    window_start, window_end = manifest["window_start"].iloc[0], manifest["window_end"].iloc[0]

    penalty = con.execute("SELECT * FROM analysis_stress_penalty ORDER BY stress_penalty_pp DESC").df()
    overall_normal = con.execute("SELECT AVG(abs_pct_error) FROM fact_grid_hourly WHERE NOT is_stress_hour").fetchone()[0]
    overall_stress = con.execute("SELECT AVG(abs_pct_error) FROM fact_grid_hourly WHERE is_stress_hour").fetchone()[0]
    overall_penalty = overall_stress - overall_normal
    overall_multiple = overall_stress / overall_normal
    stress_cost_upper_bound_central_m = con.execute("""
        SELECT SUM(shortfall_mw) * 100 / 1e6 FROM fact_grid_hourly WHERE is_stress_hour
    """).fetchone()[0]

    skill = con.execute("""
        SELECT
          1 - AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END)
            / AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error_persistence END) AS skill_normal,
          1 - AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
            / AVG(CASE WHEN is_stress_hour THEN abs_pct_error_persistence END)     AS skill_stress
        FROM fact_grid_hourly
    """).df().iloc[0]

    figs = {}

    # ---------------------------------------------------------------------------
    # PAGE 1: SUMMARY
    # ---------------------------------------------------------------------------
    ci = pd.read_csv(Path("reports/bootstrap_intervals.csv"))
    ci = ci[ci["metric"] == "stress_penalty_pp"].set_index("ba_code")
    penalty = penalty.join(ci[["lo", "hi"]], on="ba_code")
    penalty["crosses_zero"] = (penalty["lo"] < 0) & (penalty["hi"] > 0)
    n_significant = int((~penalty["crosses_zero"]).sum())

    bar = go.Figure(go.Bar(
        y=penalty["ba_name"], x=penalty["stress_penalty_pp"], orientation="h",
        marker_color=[GREY if z else ACCENT_DEMAND for z in penalty["crosses_zero"]],
        error_x=dict(
            type="data", symmetric=False,
            array=penalty["hi"] - penalty["stress_penalty_pp"],
            arrayminus=penalty["stress_penalty_pp"] - penalty["lo"],
            color="#444", thickness=1.5, width=6,
        ),
        hovertemplate="%{y}<br>%{x:.2f} pp [%{customdata[0]:.2f}, %{customdata[1]:.2f}]<extra></extra>",
        customdata=penalty[["lo", "hi"]].to_numpy(),
    ))
    bar.add_vline(x=0, line_color=RED, line_width=1)
    sig_deg = penalty.loc[(~penalty["crosses_zero"]) & (penalty["stress_penalty_pp"] > 0), "ba_code"].tolist()
    bar.update_layout(
        template=TEMPLATE, height=420,
        title=(f"Only {n_significant} of 8 regions differ from zero; "
               f"{', '.join(sig_deg) if sig_deg else 'none'} is the only one that degrades under stress"),
        xaxis_title="Stress penalty (pp of MAPE), with 95% block-bootstrap intervals",
        yaxis_title="", yaxis=dict(categoryorder="total ascending"),
    )
    figs["summary_bar"] = bar

    scatter = go.Figure(go.Scatter(
        x=penalty["avg_net_import_stress_mw"], y=penalty["stress_penalty_pp"],
        mode="markers+text", text=penalty["ba_code"], textposition="top center",
        marker=dict(size=penalty["mape_stress"] * 3 + 10,
                    color=ACCENT_DEMAND, opacity=0.75),
    ))
    scatter.update_layout(
        template=TEMPLATE, height=420,
        title="Forecast penalty vs. net imports at peak, by region",
        xaxis_title="Avg net imports during stress hours (MW)",
        yaxis_title="Stress penalty (pp)",
    )
    figs["summary_scatter"] = scatter

    kpis = dict(
        mape_normal=overall_normal, mape_stress=overall_stress,
        penalty=overall_penalty, multiple=overall_multiple, cost_m=stress_cost_upper_bound_central_m,
        skill_normal=skill["skill_normal"], skill_stress=skill["skill_stress"],
    )

    skill_fig = go.Figure()
    skill_fig.add_trace(go.Bar(x=penalty["ba_code"], y=penalty["skill_vs_persistence_normal"],
                               name="Normal hours", marker_color=GREY))
    skill_fig.add_trace(go.Bar(x=penalty["ba_code"], y=penalty["skill_vs_persistence_stress"],
                               name="Stress hours", marker_color=ACCENT_DEMAND))
    skill_fig.add_hline(y=0, line_color=RED,
                        annotation_text="below 0 = worse than yesterday's demand",
                        annotation_position="bottom right")
    skill_fig.update_layout(
        template=TEMPLATE, barmode="group", height=400,
        title="Forecast skill vs. a 24-hour persistence baseline",
        yaxis_title="Skill (1 - forecast error / baseline error)", xaxis_title="",
    )
    figs["skill"] = skill_fig

    # Hero chart: normal vs stress error side by side, so the framing question
    # is answered by the picture without needing a caption.
    hero_src = penalty.sort_values("stress_penalty_pp", ascending=False)
    hero = go.Figure()
    hero.add_trace(go.Bar(
        x=hero_src["ba_code"], y=hero_src["mape_normal"],
        name="Normal hours", marker_color=GREY,
    ))
    # Three states, so color means one thing: red = a real increase in error,
    # blue = a real decrease, grey = not distinguishable from no change.
    def stress_colour(row):
        if row["crosses_zero"]:
            return "#B9BDC4"
        return RED if row["stress_penalty_pp"] > 0 else ACCENT_DEMAND

    hero.add_trace(go.Bar(
        x=hero_src["ba_code"], y=hero_src["mape_stress"],
        name="Stress hours (top 5% demand)",
        marker_color=[stress_colour(r) for _, r in hero_src.iterrows()],
    ))
    hero.update_layout(
        template=TEMPLATE, barmode="group", height=440,
        title=dict(
            text=("Forecast error barely moves under stress<br>"
                  "<sup>Only NYIS (red) measurably degrades. PJM and ISNE (blue) improve. "
                  "Grey is not distinguishable from no change.</sup>"),
        ),
        yaxis_title="MAPE (%)", xaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    hero.add_annotation(
        x="ISNE", y=hero_src.loc[hero_src["ba_code"] == "ISNE", "mape_stress"].iloc[0],
        text="ISNE: error halves at peak", showarrow=True, arrowhead=2, ay=-35,
    )
    figs["hero"] = hero

    # ---------------------------------------------------------------------------
    # PAGE 2: ANATOMY
    # ---------------------------------------------------------------------------
    by_hour = con.execute("""
        SELECT hour_local,
               AVG(CASE WHEN is_stress_hour THEN abs_pct_error END) AS mape_stress,
               AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END) AS mape_normal
        FROM fact_grid_hourly GROUP BY 1 ORDER BY 1
    """).df()
    hour_fig = go.Figure()
    hour_fig.add_trace(go.Scatter(x=by_hour["hour_local"], y=by_hour["mape_stress"], name="Stress hours", line=dict(color=RED)))
    hour_fig.add_trace(go.Scatter(x=by_hour["hour_local"], y=by_hour["mape_normal"], name="Normal hours", line=dict(color=GREY)))
    hour_fig.update_layout(template=TEMPLATE, height=380, title="Forecast error by hour of day",
                            xaxis_title="Local hour", yaxis_title="MAPE (%)")
    figs["anatomy_hour"] = hour_fig

    by_month = con.execute("""
        SELECT d.year_month, AVG(g.abs_pct_error) AS mape
        FROM fact_grid_hourly g JOIN dim_date d ON d.date_key = g.date_key
        GROUP BY 1 ORDER BY 1
    """).df()
    month_fig = go.Figure(go.Bar(x=by_month["year_month"], y=by_month["mape"], marker_color=ACCENT_DEMAND))
    month_fig.update_layout(template=TEMPLATE, height=380, title="Forecast error by month",
                             xaxis_title="", yaxis_title="MAPE (%)")
    figs["anatomy_month"] = month_fig

    err_dist = con.execute("SELECT pct_error FROM fact_grid_hourly").df()
    hist_fig = go.Figure(go.Histogram(x=err_dist["pct_error"], xbins=dict(size=1), marker_color=ACCENT_DEMAND))
    hist_fig.add_vline(x=0, line_dash="dash", line_color=GREY)
    hist_fig.update_layout(template=TEMPLATE, height=380, title="Distribution of signed forecast error",
                            xaxis_title="Forecast error (%, + = forecast ran high)", yaxis_title="Hours")
    figs["anatomy_hist"] = hist_fig

    bias = con.execute("""
        SELECT b.ba_name, AVG(g.pct_error) AS bias FROM fact_grid_hourly g
        JOIN dim_ba b ON b.ba_code = g.ba_code GROUP BY 1 ORDER BY bias
    """).df()
    bias_fig = go.Figure(go.Bar(x=bias["ba_name"], y=bias["bias"], marker_color=ACCENT_FORECAST))
    bias_fig.update_layout(template=TEMPLATE, height=380, title="Forecast bias by region",
                            xaxis_title="", yaxis_title="Bias (%, + = forecast runs high)")
    figs["anatomy_bias"] = bias_fig

    tails = con.execute("""
        SELECT ba_code,
               p95_abs_pct_error_normal, p95_abs_pct_error_stress,
               p99_abs_pct_error_stress, worst_hour_abs_pct_error
        FROM analysis_stress_penalty ORDER BY p99_abs_pct_error_stress DESC
    """).df()
    tail_table = go.Figure(go.Table(
        header=dict(values=["Region", "P95 normal", "P95 stress", "P99 stress", "Worst hour"],
                    fill_color=ACCENT_DEMAND, font=dict(color="white")),
        cells=dict(values=[tails[c] for c in tails.columns]),
    ))
    tail_table.update_layout(height=320, title="Tail forecast error (%), where the mean stops being useful")
    figs["anatomy_tails"] = tail_table

    worst_hours = con.execute("""
        SELECT ba_code, ts_local, ROUND(demand_mw) AS demand_mw,
               ROUND(forecast_mw) AS forecast_mw, ROUND(pct_error, 1) AS pct_error
        FROM fact_grid_hourly ORDER BY abs_pct_error DESC LIMIT 10
    """).df()
    worst_hours["ts_local"] = worst_hours["ts_local"].astype(str)
    worst_table = go.Figure(go.Table(
        header=dict(values=["Region", "Local time", "Demand (MW)", "Forecast (MW)", "Error (%)"],
                    fill_color=RED, font=dict(color="white")),
        cells=dict(values=[worst_hours[c] for c in worst_hours.columns]),
    ))
    worst_table.update_layout(height=340, title="The 10 worst forecast hours in the study")
    figs["anatomy_worst"] = worst_table

    # ---------------------------------------------------------------------------
    # PAGE 3: DEEP DIVE (worst extreme hour and the week around it)
    # ---------------------------------------------------------------------------
    worst_hour = con.execute("""
        SELECT ba_code, ts_local, date_key FROM fact_grid_hourly
        WHERE is_extreme_hour ORDER BY abs_pct_error DESC LIMIT 1
    """).df().iloc[0]
    event_ba, event_date = worst_hour["ba_code"], str(worst_hour["date_key"])

    window = con.execute("""
        SELECT * FROM fact_grid_hourly
        WHERE ba_code = ?
          AND date_key BETWEEN CAST(? AS DATE) - INTERVAL 3 DAY
                            AND CAST(? AS DATE) + INTERVAL 3 DAY
        ORDER BY ts_local
    """, [event_ba, event_date, event_date]).df()

    demand_fc = go.Figure()
    demand_fc.add_trace(go.Scatter(x=window["ts_local"], y=window["demand_mw"], name="Actual demand", line=dict(color=ACCENT_DEMAND)))
    demand_fc.add_trace(go.Scatter(x=window["ts_local"], y=window["forecast_mw"], name="Day-ahead forecast", line=dict(color=ACCENT_FORECAST)))
    demand_fc.update_layout(template=TEMPLATE, height=360,
                             title=f"{event_ba}: demand vs. forecast, week of {event_date}",
                             xaxis_title="", yaxis_title="MW")
    figs["deepdive_demand"] = demand_fc

    err_fig = go.Figure(go.Scatter(x=window["ts_local"], y=window["forecast_error_mw"], fill="tozeroy", line=dict(color=RED)))
    err_fig.update_layout(template=TEMPLATE, height=300, title="Forecast error through the event",
                           xaxis_title="", yaxis_title="Forecast - actual (MW)")
    figs["deepdive_error"] = err_fig

    fuel_window = con.execute("""
        SELECT f.ts_utc, fl.fuel_name, f.generation_mw
        FROM fact_fuel_hourly f JOIN dim_fuel fl ON fl.fuel_code = f.fuel_code
        WHERE f.ba_code = ?
          AND CAST(f.ts_utc AS DATE) BETWEEN CAST(? AS DATE) - INTERVAL 3 DAY
                                          AND CAST(? AS DATE) + INTERVAL 3 DAY
    """, [event_ba, event_date, event_date]).df()
    fuel_fig = go.Figure()
    for fuel_name, grp in fuel_window.groupby("fuel_name"):
        fuel_fig.add_trace(go.Scatter(x=grp["ts_utc"], y=grp["generation_mw"], name=fuel_name, stackgroup="one"))
    fuel_fig.update_layout(template=TEMPLATE, height=380, title=f"{event_ba}: fuel mix through the event",
                            xaxis_title="", yaxis_title="MW")
    figs["deepdive_fuel"] = fuel_fig

    worst_row = window.loc[window["abs_pct_error"].idxmax()]
    deep_dive_text = (
        f"Worst extreme hour in the set: {event_ba} at {worst_row['ts_local']} local. "
        f"Demand {worst_row['demand_mw']:,.0f} MW vs. forecast {worst_row['forecast_mw']:,.0f} MW "
        f"({worst_row['abs_pct_error']:.1f}% error). Net imports at that hour: "
        f"{worst_row['net_import_mw']:,.0f} MW."
    )

    # ---------------------------------------------------------------------------
    # PAGE 4: FUEL & RAMP
    # ---------------------------------------------------------------------------
    fuel_share = con.execute("""
        SELECT CASE WHEN g.is_stress_hour THEN 'Stress' ELSE 'Normal' END AS bucket,
               fl.fuel_group, SUM(f.generation_mw) AS gen_mwh
        FROM fact_fuel_hourly f
        JOIN dim_fuel fl ON fl.fuel_code = f.fuel_code
        JOIN fact_grid_hourly g ON g.ba_code = f.ba_code AND g.ts_utc = f.ts_utc
        GROUP BY 1, 2
    """).df()
    fuel_share["pct"] = fuel_share.groupby("bucket")["gen_mwh"].transform(lambda s: 100 * s / s.sum())
    fuel_pivot = fuel_share.pivot(index="bucket", columns="fuel_group", values="pct").fillna(0)
    fuel_stack = go.Figure()
    for grp in fuel_pivot.columns:
        fuel_stack.add_trace(go.Bar(x=fuel_pivot.index, y=fuel_pivot[grp], name=grp))
    fuel_stack.update_layout(template=TEMPLATE, barmode="stack", height=380,
                              title="Generation mix, stress vs. normal hours", yaxis_title="% of generation")
    figs["fuel_stack"] = fuel_stack

    renew = con.execute("""
        SELECT b.ba_name,
               100.0 * SUM(CASE WHEN fl.is_renewable THEN f.generation_mw ELSE 0 END) / SUM(f.generation_mw) AS renew_pct
        FROM fact_fuel_hourly f
        JOIN dim_fuel fl ON fl.fuel_code = f.fuel_code
        JOIN dim_ba b ON b.ba_code = f.ba_code
        GROUP BY 1 ORDER BY renew_pct DESC
    """).df()
    renew_fig = go.Figure(go.Bar(x=renew["ba_name"], y=renew["renew_pct"], marker_color=ACCENT_DEMAND))
    renew_fig.update_layout(template=TEMPLATE, height=380, title="Renewable share of generation by region",
                             xaxis_title="", yaxis_title="%")
    figs["renew_share"] = renew_fig

    ciso = con.execute("""
        SELECT hour_local, AVG(demand_mw) AS demand, AVG(net_load_mw) AS net_load
        FROM fact_grid_hourly WHERE ba_code = 'CISO' GROUP BY 1 ORDER BY 1
    """).df()
    duck_fig = go.Figure()
    duck_fig.add_trace(go.Scatter(x=ciso["hour_local"], y=ciso["demand"], name="Demand", line=dict(color=ACCENT_DEMAND)))
    duck_fig.add_trace(go.Scatter(x=ciso["hour_local"], y=ciso["net_load"], name="Net load (demand - wind - solar)", line=dict(color=ACCENT_FORECAST)))
    duck_fig.update_layout(template=TEMPLATE, height=380, title="The duck curve: CISO net load vs. demand",
                            xaxis_title="Local hour", yaxis_title="MW")
    figs["duck_curve"] = duck_fig

    ramp = con.execute("""
        SELECT b.ba_name, MAX(g.ramp_1h_mw) AS gross_ramp, MAX(g.net_load_ramp_1h_mw) AS net_ramp
        FROM fact_grid_hourly g JOIN dim_ba b ON b.ba_code = g.ba_code GROUP BY 1 ORDER BY net_ramp DESC
    """).df()
    ramp_fig = go.Figure()
    ramp_fig.add_trace(go.Bar(x=ramp["ba_name"], y=ramp["gross_ramp"], name="Gross demand ramp", marker_color=GREY))
    ramp_fig.add_trace(go.Bar(x=ramp["ba_name"], y=ramp["net_ramp"], name="Net load ramp", marker_color=RED))
    ramp_fig.update_layout(template=TEMPLATE, barmode="group", height=380,
                            title="Max 1-hour ramp, gross demand vs. net load", yaxis_title="MW")
    figs["ramp"] = ramp_fig

    ramp_pen = con.execute("""
        SELECT r.ba_code, r.ba_name, r.ramp_stress_penalty_pp, r.ramp_stress_multiple,
               r.pct_overlap_with_demand_stress, d.stress_penalty_pp
        FROM analysis_ramp_stress_penalty r
        JOIN analysis_stress_penalty d USING (ba_code)
    """).df()
    ramp_ci = pd.read_csv(Path("reports/bootstrap_intervals.csv"))
    ramp_ci = ramp_ci[ramp_ci["metric"] == "ramp_stress_penalty_pp"].set_index("ba_code")
    ramp_pen = ramp_pen.join(ramp_ci[["lo", "hi"]], on="ba_code").sort_values("ramp_stress_penalty_pp")

    lens_fig = go.Figure()
    lens_fig.add_trace(go.Bar(
        y=ramp_pen["ba_name"], x=ramp_pen["stress_penalty_pp"], orientation="h",
        name="Stress = top 5% demand", marker_color=ACCENT_DEMAND,
    ))
    lens_fig.add_trace(go.Bar(
        y=ramp_pen["ba_name"], x=ramp_pen["ramp_stress_penalty_pp"], orientation="h",
        name="Stress = top 5% net-load ramp", marker_color=ACCENT_FORECAST,
        error_x=dict(type="data", symmetric=False,
                     array=ramp_pen["hi"] - ramp_pen["ramp_stress_penalty_pp"],
                     arrayminus=ramp_pen["ramp_stress_penalty_pp"] - ramp_pen["lo"],
                     color="#444", thickness=1.2, width=5),
    ))
    lens_fig.add_vline(x=0, line_color=RED, line_width=1)
    lens_fig.update_layout(
        template=TEMPLATE, barmode="group", height=460,
        title="Stress by ramp, not by level: the two definitions disagree",
        xaxis_title="Penalty (pp of MAPE)", yaxis_title="",
    )
    figs["lens_compare"] = lens_fig

    overlap_fig = go.Figure(go.Bar(
        x=ramp_pen["ba_code"], y=ramp_pen["pct_overlap_with_demand_stress"], marker_color=GREY,
    ))
    overlap_fig.update_layout(
        template=TEMPLATE, height=340,
        title="The two stress definitions pick out almost entirely different hours",
        xaxis_title="", yaxis_title="% of ramp-stress hours that are also demand-stress hours",
    )
    figs["lens_overlap"] = overlap_fig

    # ---------------------------------------------------------------------------
    # PAGE 5: METHODOLOGY AND DATA QUALITY
    # ---------------------------------------------------------------------------
    quality = con.execute("""
        SELECT b.ba_name,
               ROUND(AVG(ABS(g.imbalance_pct)), 2) AS avg_abs_imbalance_pct,
               SUM(CASE WHEN ABS(g.imbalance_pct) > 5 THEN 1 ELSE 0 END) AS hours_failing_balance_check
        FROM fact_grid_hourly g JOIN dim_ba b ON b.ba_code = g.ba_code
        GROUP BY 1 ORDER BY avg_abs_imbalance_pct DESC
    """).df()
    quality_table = go.Figure(go.Table(
        header=dict(values=["Region", "Avg abs imbalance (%)", "Hours failing balance check"], fill_color=ACCENT_DEMAND, font=dict(color="white")),
        cells=dict(values=[quality["ba_name"], quality["avg_abs_imbalance_pct"], quality["hours_failing_balance_check"]]),
    ))
    quality_table.update_layout(height=320, title="Balance identity check (net generation - interchange = demand)")
    figs["quality_table"] = quality_table

    con.close()

    # ---------------------------------------------------------------------------
    # ASSEMBLE ONE-PAGE HTML REPORT
    # ---------------------------------------------------------------------------
    def fig_html(fig):
        return pio.to_html(fig, include_plotlyjs=False, full_html=False)

    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
    <title>United States Energy Grid Stress Analysis</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
    body{{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:0 auto;padding:24px;color:#222}}
    h1{{margin-bottom:4px}} h2{{margin-top:56px;border-top:2px solid #eee;padding-top:24px}}
    .kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0}}
    .kpi{{background:#F4F6F8;border-radius:8px;padding:16px 20px;min-width:150px}}
    .kpi .label{{font-size:12px;color:#666;text-transform:uppercase}}
    .kpi .value{{font-size:28px;font-weight:600;color:#2E5EAA}}
    .subtitle{{color:#555}}
    .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
    nav{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;
         padding:10px 0;margin-bottom:8px;z-index:10;font-size:14px}}
    nav a{{color:#2E5EAA;text-decoration:none;margin-right:18px}}
    nav a:hover{{text-decoration:underline}}
    .repo{{font-size:13px;color:#666;margin-top:4px}}
    </style></head><body>
    <h1>United States Energy Grid Stress Analysis</h1>
    <p class="subtitle">Does the U.S. power grid forecast worst exactly when accuracy matters most?
    Eight balancing authorities, {window_start} to {window_end}.</p>
    <p class="repo">Code, data and the Power BI version:
    <a href="https://github.com/josealemanm/united-states-energy-grid-stress-analysis">github.com/josealemanm/united-states-energy-grid-stress-analysis</a></p>
    <nav>
      <a href="#summary">Summary</a>
      <a href="#anatomy">Error anatomy</a>
      <a href="#deepdive">Stress hour deep dive</a>
      <a href="#fuelramp">Fuel mix and ramp</a>
      <a href="#lens">Two definitions of stress</a>
      <a href="#methodology">Method and data quality</a>
    </nav>

    <h2 id="summary">Page 1 &middot; Summary</h2>
    <div class="kpi-row">
      <div class="kpi"><div class="label">MAPE, normal hours</div><div class="value">{kpis['mape_normal']:.2f}%</div></div>
      <div class="kpi"><div class="label">MAPE, stress hours</div><div class="value">{kpis['mape_stress']:.2f}%</div></div>
      <div class="kpi"><div class="label">Stress penalty</div><div class="value">+{kpis['penalty']:.2f} pp</div></div>
      <div class="kpi"><div class="label">Stress multiple</div><div class="value">{kpis['multiple']:.2f}x</div></div>
      <div class="kpi"><div class="label">Stress shortfall, upper bound ($100/MWh)</div><div class="value">${kpis['cost_m']:.1f}M</div></div>
      <div class="kpi"><div class="label">Skill vs. persistence, normal</div><div class="value">{kpis['skill_normal']:.0%}</div></div>
      <div class="kpi"><div class="label">Skill vs. persistence, stress</div><div class="value">{kpis['skill_stress']:.0%}</div></div>
    </div>
    {fig_html(figs['hero'])}
    {fig_html(figs['summary_bar'])}
    {fig_html(figs['skill'])}
    {fig_html(figs['summary_scatter'])}

    <h2 id="anatomy">Page 2 &middot; Forecast Accuracy Anatomy</h2>
    <div class="grid2">{fig_html(figs['anatomy_hour'])}{fig_html(figs['anatomy_month'])}</div>
    <div class="grid2">{fig_html(figs['anatomy_hist'])}{fig_html(figs['anatomy_bias'])}</div>
    {fig_html(figs['anatomy_tails'])}
    {fig_html(figs['anatomy_worst'])}

    <h2 id="deepdive">Page 3 &middot; Stress Hour Deep Dive</h2>
    <p>{deep_dive_text}</p>
    {fig_html(figs['deepdive_demand'])}
    {fig_html(figs['deepdive_error'])}
    {fig_html(figs['deepdive_fuel'])}

    <h2 id="fuelramp">Page 4 &middot; Fuel Mix and Ramp</h2>
    <div class="grid2">{fig_html(figs['fuel_stack'])}{fig_html(figs['renew_share'])}</div>
    <div class="grid2">{fig_html(figs['duck_curve'])}{fig_html(figs['ramp'])}</div>

    <h2 id="lens">Page 4b &middot; Stress by ramp, not by level</h2>
    <p>Every result above defines a stress hour by demand level. Defining it by how fast
    net load is moving instead picks out a nearly disjoint set of hours, and reverses
    several conclusions: PJM and Southern Company both improve under demand stress but
    degrade sharply under ramp stress. Which lens you choose decides which region you
    would fund, which is a reason to state the definition up front rather than bury it.</p>
    {fig_html(figs['lens_compare'])}
    {fig_html(figs['lens_overlap'])}

    <h2 id="methodology">Page 5 &middot; Methodology and Data Quality</h2>
    <p><b>Question:</b> When the U.S. power grid is under the most stress, does the day-ahead demand
    forecast get worse exactly when accuracy matters most, and which regions are most exposed?</p>
    <p><b>Stress hour definition:</b> the top 5% of demand hours within a balancing authority and season.
    Percentile within region makes differently sized grids comparable; percentile within season prevents
    the measure from collapsing into a summer-vs-winter comparison; the top-5% cutoff gives roughly 438
    hours per region per year, enough for stable statistics.</p>
    {fig_html(figs['quality_table'])}
    <p><b>Handling decisions:</b> hours missing demand, forecast, generation or interchange are excluded
    rather than interpolated. Hours with zero or negative demand are dropped as impossible per the
    EIA-930 form instructions. Balance identity failures are reported, not corrected.</p>
    <p><b>Limitations:</b> MISO and SWPP span multiple time zones and are each assigned one local zone.
    Raw rather than EIA-adjusted series are used, keeping provenance simple and reporting error visible.
    The cost-per-MWh figure is a sourced assumption with a sensitivity range, not a measurement.
    A 24-month window is short for weather-driven conclusions.</p>
    <p><b>Source:</b> U.S. Energy Information Administration, Form EIA-930, API v2.
    Data pulled {manifest['pulled_at_utc'].iloc[0]}.</p>
    </body></html>"""]

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text("".join(parts))
    print(f"Wrote {OUT_HTML}")

    # --- Screenshots for the README --------------------------------------------
    # The memo embeds this one, so it is written at memo proportions too.
    figs["summary_bar"].write_image(str(Path("reports/memo_chart.png")),
                                    width=800, height=400, scale=2)
    print("Wrote reports/memo_chart.png")

    screenshot_targets = {
        "normal_vs_stress": figs["hero"],
        "executive_summary": figs["summary_bar"],
        "anatomy": figs["anatomy_hour"],
        "deep_dive": figs["deepdive_demand"],
        "fuel_ramp": figs["duck_curve"],
    }
    for name, fig in screenshot_targets.items():
        fig.write_image(str(SCREEN_DIR / f"{name}.png"), width=1000, height=500, scale=2)
        print(f"Wrote {SCREEN_DIR / (name + '.png')}")


if __name__ == "__main__":
    main()
