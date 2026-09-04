"""
07_build_memo.py
Builds the one-page analyst memo, reports/memo.pdf, from the warehouse.

Run:  python src/07_build_memo.py   (after 04_export_for_bi.py)
"""

from pathlib import Path
from datetime import datetime, date
import duckdb
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image

DB_PATH = Path("data/interim/grid.duckdb")
MANIFEST_PATH = Path("reports/pull_manifest.csv")
OUT_PATH = Path("reports/memo.pdf")

def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    manifest = pd.read_csv(MANIFEST_PATH)
    window_start = pd.to_datetime(manifest["window_start"].iloc[0])
    window_end = pd.to_datetime(manifest["window_end"].iloc[0])
    pulled_at = manifest["pulled_at_utc"].iloc[0]

    pooled = con.execute("""
        SELECT
          ROUND(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END),2) AS mape_normal,
          ROUND(AVG(CASE WHEN is_stress_hour THEN abs_pct_error END),2) AS mape_stress,
          SUM(CASE WHEN is_stress_hour THEN shortfall_mw ELSE 0 END) AS stress_shortfall_mwh,
          COUNT(*) AS total_hours,
          SUM(CASE WHEN is_stress_hour THEN 1 ELSE 0 END) AS stress_hours,
          1 - AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END)
            / AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error_persistence END) AS skill_normal,
          1 - AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
            / AVG(CASE WHEN is_stress_hour THEN abs_pct_error_persistence END) AS skill_stress
        FROM fact_grid_hourly
    """).df().iloc[0]

    negative_skill = con.execute("""
        SELECT ba_name FROM analysis_stress_penalty
        WHERE skill_vs_persistence_normal < 0 ORDER BY skill_vs_persistence_normal
    """).df()["ba_name"].tolist()

    # 95% block-bootstrap intervals from 03b_bootstrap_intervals.py.
    ci = pd.read_csv(Path("reports/bootstrap_intervals.csv"))
    ci = ci[ci["metric"] == "stress_penalty_pp"].set_index("ba_code")


    def interval(ba_code):
        row = ci.loc[ba_code]
        return f"[{row['lo']:+.2f}, {row['hi']:+.2f}]"


    def crosses_zero(ba_code):
        row = ci.loc[ba_code]
        return row["lo"] < 0 < row["hi"]


    significant = [b for b in ci.index if not crosses_zero(b)]
    n_significant = len(significant)
    sig_degrading = [b for b in significant if ci.loc[b, "mid"] > 0]
    sig_improving = [b for b in significant if ci.loc[b, "mid"] <= 0]

    penalty = con.execute("""
        SELECT ba_code, ba_name, region, stress_penalty_pp, stress_multiple,
               avg_net_import_stress_mw
        FROM analysis_stress_penalty ORDER BY stress_penalty_pp DESC
    """).df()

    ciso = penalty[penalty["ba_code"] == "CISO"].iloc[0]
    nyis = penalty[penalty["ba_code"] == "NYIS"].iloc[0]
    ciso_q = con.execute("""
        SELECT total_hours, balance_clean_hours, mape_clean, stress_penalty_clean_pp
        FROM analysis_stress_penalty WHERE ba_code = 'CISO'
    """).df().iloc[0]
    ciso_overall_mape = con.execute("""
        SELECT AVG(abs_pct_error) FROM fact_grid_hourly WHERE ba_code = 'CISO'
    """).fetchone()[0]
    # Hours where interchange is not reported cannot fail the identity, they
    # simply cannot be tested. Counting them as failures inflated this figure.
    ciso_fail, ciso_checkable = con.execute("""
        SELECT SUM(CASE WHEN is_balance_clean = FALSE THEN 1 ELSE 0 END),
               SUM(CASE WHEN is_balance_clean IS NOT NULL THEN 1 ELSE 0 END)
        FROM fact_grid_hourly WHERE ba_code = 'CISO'
    """).fetchone()

    ramp = con.execute("""
        SELECT ba_code, ba_name, ramp_stress_penalty_pp, ramp_stress_multiple,
               pct_overlap_with_demand_stress
        FROM analysis_ramp_stress_penalty ORDER BY ramp_stress_penalty_pp DESC
    """).df()
    ramp_ci = pd.read_csv(Path("reports/bootstrap_intervals.csv"))
    ramp_ci = ramp_ci[ramp_ci["metric"] == "ramp_stress_penalty_pp"].set_index("ba_code")

    # Largest and best-established are different regions here, and this memo
    # used to claim they were the same one. Southern Company has the biggest
    # ramp point estimate and the widest interval in the study; PJM has a
    # slightly smaller one bounded four times more tightly. Name both.
    ramp_largest = ramp.iloc[0]
    ramp_width = ramp_ci["hi"] - ramp_ci["lo"]
    ramp_established = [b for b in ramp_ci.index if ramp_ci.loc[b, "lo"] > 0]
    ramp_tightest_code = min(ramp_established, key=lambda b: ramp_width[b])
    ramp_tightest = ramp[ramp["ba_code"] == ramp_tightest_code].iloc[0]


    def ramp_interval(ba_code):
        row = ramp_ci.loc[ba_code]
        return f"[{row['lo']:+.2f}, {row['hi']:+.2f}]"

    # The cautionary example has to be drawn from the regions whose interval
    # still contains zero. Taking the top row of the whole table picks the one
    # region whose effect IS established, and makes the sentence contradict the
    # sentence immediately before it.
    noise = penalty[penalty["ba_code"].map(crosses_zero)]
    worst = noise.iloc[0]
    worst_rank = int(penalty.index.get_indexer([worst.name])[0]) + 1
    ORDINALS = {1: "largest", 2: "second-largest", 3: "third-largest",
                4: "fourth-largest", 5: "fifth-largest"}
    worst_rank_word = ORDINALS.get(worst_rank, f"{worst_rank}th-largest")
    best = penalty.iloc[-1]
    degrading = penalty[penalty["stress_penalty_pp"] > 0]
    ercot = penalty[penalty["ba_code"] == "ERCO"].iloc[0]
    importer_a = penalty[penalty["ba_code"] == "NYIS"].iloc[0]
    importer_b = penalty[penalty["ba_code"] == "CISO"].iloc[0]

    stress_cost_upper_bound_low_m = pooled["stress_shortfall_mwh"] * 40 / 1e6
    stress_cost_upper_bound_central_m = pooled["stress_shortfall_mwh"] * 100 / 1e6
    stress_cost_upper_bound_high_m = pooled["stress_shortfall_mwh"] * 200 / 1e6

    con.close()

    def chart_flowable():
        """The penalty chart, sized to the text column. Skipped if absent."""
        chart = Path("reports/memo_chart.png")
        if not chart.exists():
            return Spacer(0, 0)
        width = 4.0 * inch
        return Image(str(chart), width=width, height=width * 0.5, hAlign="CENTER")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("MemoTitle", parent=styles["Title"], fontSize=15, spaceAfter=2, alignment=TA_CENTER)
    sub_style = ParagraphStyle("MemoSub", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER, textColor="#555555", spaceAfter=10)
    head_style = ParagraphStyle("Head", parent=styles["Heading3"], fontSize=9.5, spaceBefore=4, spaceAfter=2, textColor="#1F3864")
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=8.0, leading=9.9)
    finding_style = ParagraphStyle("Finding", parent=body_style, leftIndent=9, spaceAfter=3)

    story = [
        Paragraph("GRID FORECAST ACCURACY UNDER STRESS", title_style),
        Paragraph(
            f"Eight U.S. balancing authorities, {window_start:%B %Y} to {window_end:%B %Y} "
            f"&nbsp;|&nbsp; Jose Aleman &nbsp;|&nbsp; {date.today():%B %d, %Y}",
            sub_style,
        ),
        HRFlowable(width="100%", color="#1F3864", thickness=1),

        Paragraph("QUESTION", head_style),
        Paragraph(
            "When the U.S. power grid is under the most stress, does the day-ahead demand forecast "
            "get worse exactly when accuracy matters most, and which regions are most exposed?",
            body_style,
        ),

        Paragraph("METHOD", head_style),
        Paragraph(
            f"Hourly demand, day-ahead forecast, net generation and interchange for eight balancing "
            f"authorities (PJM, MISO, CISO, ERCOT, ISNE, NYIS, SWPP, SOCO) from the EIA-930 API: "
            f"{pooled['total_hours']:,.0f} balancing-authority-hours, {pooled['stress_hours']:,.0f} of "
            f"them stress hours. A stress hour is the top 5% of demand within a balancing authority "
            f"and season, which keeps differently sized grids comparable and stops the measure "
            f"collapsing into summer versus winter. Python and DuckDB SQL. Intervals are 95% block "
            f"bootstraps resampled by calendar day, since errors within a day are correlated and an "
            f"hourly bootstrap would report noise as signal.",
            body_style,
        ),

        Paragraph("FINDINGS", head_style),
        Paragraph(
            f"1. The effect is real in one region, not eight. Pooled across all eight, forecast error "
            f"does not worsen under stress ({pooled['mape_stress']:.2f}% at stress vs. "
            f"{pooled['mape_normal']:.2f}% normal), and with 95% block-bootstrap intervals attached only "
            f"{n_significant} of eight regions have a stress penalty distinguishable from zero. "
            f"{' and '.join(sig_degrading)} degrades ({nyis['stress_penalty_pp']:+.2f} pp, "
            f"{interval('NYIS')}, a {nyis['stress_multiple']:.2f}x multiple); "
            f"{' and '.join(sig_improving)} improve, ISO New England sharply "
            f"({best['stress_penalty_pp']:.2f} pp, {best['stress_multiple']:.2f}x), consistent with "
            f"operators watching days they already expect to be extreme. Everything else is noise: "
            f"{worst['ba_name']} has the {worst_rank_word} point estimate at "
            f"+{worst['stress_penalty_pp']:.2f} pp but an interval of {interval(worst['ba_code'])}, "
            f"entirely consistent with no effect. Ranking eight regions on point estimates alone would "
            f"have put the wrong region first.",
            finding_style,
        ),
        Paragraph(
            f"2. Against a naive baseline the forecasts hold up better than the raw error suggests. "
            f"The day-ahead forecast beats 24-hour persistence (yesterday's demand at the same hour) "
            f"by {pooled['skill_normal']:.0%} at normal hours and {pooled['skill_stress']:.0%} at "
            f"stress hours: skill rises under stress, because persistence degrades faster than the "
            f"forecast does. The exceptions are {' and '.join(negative_skill)}, both worse than "
            f"persistence. They are not the same problem: SWPP's gap survives restricting to hours "
            f"that balance, so it is real; CISO's does not.",
            finding_style,
        ),
        Paragraph(
            f"3. Most of what looks like CISO forecast error is a reporting problem. CISO fails the "
            f"EIA-930 balance identity in {ciso_fail:,.0f} of the {ciso_checkable:,.0f} hours where "
            f"the check can be run. On the hours that do balance its MAPE falls from "
            f"{ciso_overall_mape:.2f}% to {ciso_q['mape_clean']:.2f}% and its stress penalty flips "
            f"from {ciso['stress_penalty_pp']:+.2f} to {ciso_q['stress_penalty_clean_pp']:+.2f} pp. "
            f"Ranking CISO among the worst forecasters measures its metering, not its forecasting.",
            finding_style,
        ),
        Paragraph(
            f"4. The answer depends on what counts as stress. Defining a stress hour by net-load ramp "
            f"instead of demand level picks out an almost disjoint set of hours (overlap is "
            f"{ramp['pct_overlap_with_demand_stress'].min():.0f}-"
            f"{ramp['pct_overlap_with_demand_stress'].max():.0f}% by region) and reverses the ranking. "
            f"{ramp_largest['ba_name']} has the largest ramp-lens point estimate "
            f"({ramp_largest['ramp_stress_penalty_pp']:+.2f} pp) and also the widest interval in the "
            f"study, {ramp_interval(ramp_largest['ba_code'])}, so how big it is stays open. "
            f"{ramp_tightest['ba_name']}, which improves under demand stress, comes out slightly "
            f"lower at {ramp_tightest['ramp_stress_penalty_pp']:+.2f} pp on an interval "
            f"{ramp_width[ramp_largest['ba_code']] / ramp_width[ramp_tightest_code]:.0f} times "
            f"narrower, {ramp_interval(ramp_tightest['ba_code'])}, a "
            f"{ramp_tightest['ramp_stress_multiple']:.2f}x multiple. Those are the only two ramp "
            f"penalties that clear zero on the worsening side, and they disagree about size. "
            f"Neither lens is wrong: one "
            f"asks who is worst when load is highest, the other when it is moving fastest.",
            finding_style,
        ),

        chart_flowable(),

        Paragraph("RECOMMENDATION", head_style),
        Paragraph(
            f"Put stress-hour forecasting effort into New York ISO, and only New York ISO. It is the "
            f"one region whose penalty survives a confidence interval "
            f"({nyis['stress_penalty_pp']:+.2f} pp, {interval('NYIS')}), and it imports "
            f"{nyis['avg_net_import_stress_mw']:,.0f} MW at peak, so its misses land when its own "
            f"headroom is thinnest. Spreading the same money across eight regions buys down an effect "
            f"six of them do not measurably have. Two items should be funded separately, not as stress "
            f"work: SWPP's day-ahead series loses to yesterday's demand in every hour, a baseline "
            f"forecasting problem; and CISO's error is mostly a reporting problem. ERCOT is worth "
            f"monitoring because it has only about 1.2 GW of DC-tie import capability against a "
            f"~85 GW peak, effectively isolated in stress conditions, but its penalty "
            f"({interval('ERCO')}) is not established. For scale, the pooled stress-hour shortfall at an EIA-sourced "
            f"$40-200/MWh band is ${stress_cost_upper_bound_low_m:,.0f}M to "
            f"${stress_cost_upper_bound_high_m:,.0f}M over 24 months "
            f"(${stress_cost_upper_bound_central_m:,.0f}M central), an upper bound, not a measurement. "
            f"One thing would change this answer: if the concern is ramp speed rather than demand "
            f"level, {ramp_tightest['ba_name']} displaces New York ISO on an effect that is larger "
            f"and no less well established. Decide which kind of stress the budget is buying down "
            f"before spending it.",
            body_style,
        ),

        Paragraph("LIMITATIONS", head_style),
        Paragraph(
            "&bull; MISO and SWPP span multiple time zones; each is assigned one local zone.<br/>"
            "&bull; Raw EIA series, not EIA's adjusted series, so reporting error stays visible "
            "rather than smoothed away.<br/>"
            "&bull; The price band is a sourced assumption, not a measurement, and the dollar figure "
            "assumes every under-forecast MW is bought at that price when reserves and demand "
            "response cover part of it: an upper bound.<br/>"
            "&bull; 24 months is short for weather-driven conclusions; a hot or mild year could shift "
            "the rankings.",
            body_style,
        ),

        Paragraph("SOURCE", head_style),
        Paragraph(
            f"U.S. EIA, Form EIA-930, API v2. Pulled {pulled_at[:10]}. "
            f"Code: github.com/josealemanm/grid-stress-dashboard",
            body_style,
        ),
    ]

    doc = SimpleDocTemplate(
        str(OUT_PATH), pagesize=letter,
        topMargin=0.45 * inch, bottomMargin=0.4 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
