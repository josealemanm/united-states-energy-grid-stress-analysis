# The Power BI report

This is the Power BI half of the Grid Stress Dashboard, a study of whether U.S.
day-ahead electricity demand forecasts get worse on the highest-demand hours.
[The README](../README.md) covers the question, the data and the findings. This
file covers the model, the measures and the layout.

The report is built. It lives in `powerbi/` as a Power BI **project** rather
than a `.pbix`: the semantic model is TMDL and the report pages are JSON, so
every measure and every visual is text you can read in a diff.

**To open it:** install Power BI Desktop from the Microsoft Store, then
double-click `powerbi/grid_stress.pbip`. On first open the tables are empty and
a yellow bar offers **Refresh now**. Click it once. All 1.37 million rows
load in a few seconds.

If Desktop cannot find the data, the paths are wrong for your machine: **Home >
Transform data > Manage parameters**, set `RepoRoot` to wherever you cloned the
repo, and refresh again. That one parameter is the only machine-specific thing
in the model.

You do **not** need Python, a virtual environment, or an EIA API key. The raw
and processed parquet are committed.

**The rest of this file explains how the model is put together**, measure by
measure and page by page. Read it to understand what is there, or follow it
from section 2 to rebuild the whole thing by hand, which is the better way to
learn it. Either way the numbers in section 10 are what your visuals should
show.

> This supersedes Parts 9-11 of `TUTORIAL_FROM_SCRATCH.md`. That tutorial was
> written before the analysis existed and its table list, column names and
> headline numbers are all out of date. Where the two disagree, this file wins.

---

## 0. Setup (15 minutes)

Skip this if you already opened `powerbi/grid_stress.pbip`.

1. **Install Power BI Desktop** from the Microsoft Store. Search "Power BI
   Desktop", click Get. It is free. Use the Store version rather than the
   standalone download so it updates itself.
2. **Get the project.** In PowerShell:

   ```powershell
   gh repo clone josealemanm/grid-stress-dashboard
   ```

   Then:

   ```powershell
   cd grid-stress-dashboard
   ```

   Then:

3. **Confirm the data is there.** You should see seven `.parquet` files:

   ```powershell
   dir data\processed
   ```

If that folder is empty, you are on the wrong branch.

---

## 0b. Changing the layout

There are two ways to move things around. They do not mix well, so pick one.

### Option A: drag it in Power BI Desktop

Fine for a quick change, and the only option if you do not want to touch
Python.

1. Click the visual once. A grey frame appears with handles on the corners.
2. Drag the frame to move it, drag a handle to resize it.
3. For exact numbers instead of eyeballing it, open the **Format** pane (the
   paint roller), go to **General > Properties > Size** and **Position**, and
   type the pixel values. This is how you get two visuals the same height.
4. **Ctrl+S** to save.

To change a chart title: same Format pane, **General > Title**. To change what
is plotted, drag fields in and out of the wells in the **Visualizations** pane.
To change a color for every visual at once, use the theme (option B) rather
than setting it here, or you will be doing it forty times.

**If you edit here, stop running `make powerbi`.** It rewrites the report
folder from the script and your dragging is gone.

### Option B: edit the numbers in `src/08_build_powerbi_report.py`

Better if you want the pages to stay consistent, because you are changing the
rule rather than one visual. The whole layout is one block at the top of the
file:

```python
MARGIN = 20        # page edge to the first visual
GUTTER = 12        # gap between visuals, across and down
HEADER_H = 64      # navy band at the top
STRIP_H  = 52      # slicer row
FOOTER_H = 28      # grey band at the bottom

ROW_HEIGHTS = {
    "summary":   [96, "auto", 168],   # three rows, top to bottom
    ...
}

COLUMN_WEIGHTS = {
    "summary":   [[1, 1, 1, 1, 1], [3, 2], [2, 3]],
    ...
}
```

- **Row heights** are pixels, top to bottom. One row per page can be `"auto"`
  and it takes whatever height is left over, so you only have to do arithmetic
  for the rows you care about.
- **Column weights** are proportions, not pixels. `[3, 2]` means the first
  visual gets three fifths of the width and the second two fifths. `[1, 1, 1]`
  is three equal columns. The script works out the pixels, including the
  gutters, and makes the last column absorb any rounding so the right edge
  always lands on the margin.
- If the numbers do not fit, the script says so and names the page:
  `page 'summary': fixed rows total 900px, leaving -240px for the auto row.`

Then rebuild and reopen:

```powershell
cd ~/grid-stress-dashboard; .venv\Scripts\python.exe src/08_build_powerbi_report.py
```

Colors and font sizes live in `src/powerbi_theme.py`, in one palette block at
the top. Change `PT_VISUAL_TITLE` there and every chart title on all six pages
changes together.

### The skeleton every page shares

```
 0    full-bleed navy band, 64px:  report name, then this page's title,
                                   with the data window on the right
 72   52px strip:                  the page's slicers (four pages have them)
136   the content grid:            20px margin, 1240px wide, 12px gutter
692   full-bleed footer, 28px:     source on the left, page number on the right
```

Pages without slicers start their content at 72 instead of 136, so they do not
carry an empty strip.

### Conventions the report keeps to

- **A title says what is plotted.** "Mean absolute % error by region, normal
  and stress hours", not a sentence about what it means. Interpretation belongs
  in the memo, not on the chart.
- **Rows span the full grid**, margin to margin, so edges line up down the page.
- **A KPI tile reads label, number, unit.** The unit rides on the field's
  display name, because that is what renders under the value.
- **Two data colors, same meaning everywhere.** Light blue is the normal-hours
  series, dark navy the stress-hours series, because they are always dropped in
  that order. Red is only ever a zero line.

---

## 1. What you are looking at (5 minutes, do not skip)

Power BI has three views. The icons are on the **far left edge** of the window,
stacked vertically:

| Icon | View | What it is for |
|---|---|---|
| Bar chart | **Report** | Building the pages people look at |
| Grid/table | **Table** | Inspecting raw rows |
| Three boxes | **Model** | Drawing lines between tables |

The strip across the top (Home, Insert, Modeling, View) is the **ribbon**. The
buttons underneath change depending on which tab you click.

On the right you have the **Data pane** (your tables and columns) and the
**Visualizations pane** (chart type icons and, below them, the "field wells"
where you drag columns).

Two habits that will save you pain:

- **Ctrl+S constantly.** Power BI does not autosave.
- When a visual looks wrong, click it once and look at the field wells before
  changing anything else. Nine times out of ten a field is in the wrong well.

---

## 2. Load the data (20 minutes)

You are loading **eight** things: seven parquet tables and one CSV.

For **each** of the seven parquet files:

1. **Home** ribbon → **Get data** → **More...**
2. Type `Parquet` in the search box, select **Parquet**, click **Connect**
3. Click **Browse**, go to `data\processed`, pick the file, **Open**
4. Click **OK**, then in the preview window click **Load**

The seven files:

| File | Rows | What it is |
|---|---|---|
| `dim_ba.parquet` | 8 | The eight balancing authorities |
| `dim_fuel.parquet` | 9 | Fuel types |
| `dim_date.parquet` | 731 | Calendar |
| `fact_grid_hourly.parquet` | 139,055 | **The main table.** One row per region per hour |
| `fact_fuel_hourly.parquet` | 1,233,230 | Generation by fuel, with its own `ts_local` and `date_key`. Slow to load, be patient |
| `analysis_stress_penalty.parquet` | 8 | Pre-computed results, demand-stress lens |
| `analysis_ramp_stress_penalty.parquet` | 8 | Pre-computed results, ramp-stress lens |

Then the CSV, which the old tutorial does not mention and which matters more
than anything else on this list:

8. **Get data** → **Text/CSV** → `reports\bootstrap_intervals.csv` → **Load**

**Why that CSV matters.** It holds the 95% confidence intervals. Without it you
will build charts showing point estimates, and the point estimates lie: they say
Southwest Power Pool is the second-worst region at +0.42 percentage points, when
its interval is [−0.98, +1.93], i.e. indistinguishable from no effect at all.
Half the value of this project is showing that distinction.

> **If the Parquet connector errors out** (older Power BI builds sometimes do),
> there is an escape hatch. On the Mac, run `make csv`, which writes `.csv`
> copies next to the parquet. Load those with **Text/CSV** instead. They are
> 86 MB so they are deliberately not committed, so you would need to copy them
> across manually.

---

## 3. Fix the column types (10 minutes)

A wrong type breaks filters silently, with no error. Check these.

**Home** → **Transform data** opens the Power Query Editor. Click each table in
the Queries list on the left and look at the small icon on the left of each
column header.

On `fact_grid_hourly`:

| Column | Must be | Why |
|---|---|---|
| `date_key` | Date | Joins to the calendar |
| `ts_utc`, `ts_local` | Date/Time | Time-of-day charts |
| `hour_local` | Whole Number | Axis ordering |
| anything ending `_mw`, `_pct`, `_mwh` | Decimal Number | Arithmetic |
| `is_stress_hour`, `is_extreme_hour`, `is_balance_clean`, `is_ramp_stress_hour` | **True/False** | **Your DAX compares these to TRUE** |

Those four `is_` columns are the ones that actually break things. If any comes
in as Text, click its type icon and change it to True/False.

On `dim_date`: `date_key` must be Date, `is_weekend` True/False.

When done, **Close & Apply** (top left). This takes a minute on the fuel table.

---

## 4. The fuel table already has its date (nothing to do)

An earlier draft of this guide had you add `date_key` to `fact_fuel_hourly` as
a DAX calculated column, derived from `ts_utc`. Don't. Two reasons.

The small one is speed: a `FORMAT` inside a calculated column runs 1.2 million
times and is locale-dependent.

The real one is that `ts_utc` is the wrong clock. `fact_grid_hourly[date_key]`
comes from **local** time, so a UTC-derived key on the fuel table would put a
California evening into the next calendar day and quietly misalign the two
facts by one day for a third of every year.

`src/03_build_warehouse.sql` now converts once, in SQL, and carries both
`ts_local` and `date_key` on the fuel table. Both facts land on the same
calendar day, and a fuel chart and a demand chart can share one x axis. If your
copy of `fact_fuel_hourly` has only `ts_utc`, re-run `make warehouse`.

---

## 5. Draw the relationships (15 minutes)

Go to **Model view** (three-boxes icon).

First, **delete every line Power BI drew by itself.** Click a line, press
Delete. Auto-detected relationships are frequently wrong and you want to know
exactly what your model does.

Now drag each field on the left onto the field on the right:

| Drag from | Drop on |
|---|---|
| `fact_grid_hourly[ba_code]` | `dim_ba[ba_code]` |
| `fact_grid_hourly[date_key]` | `dim_date[date_key]` |
| `fact_fuel_hourly[ba_code]` | `dim_ba[ba_code]` |
| `fact_fuel_hourly[fuel_code]` | `dim_fuel[fuel_code]` |
| `fact_fuel_hourly[date_key]` | `dim_date[date_key]` |
| `analysis_stress_penalty[ba_code]` | `dim_ba[ba_code]` |
| `analysis_ramp_stress_penalty[ba_code]` | `dim_ba[ba_code]` |
| `bootstrap_intervals[ba_code]` | `dim_ba[ba_code]` |

**Check every one.** Double-click each line. The dialog must say
**Many to one (\*:1)** with the fact/analysis table on the "many" side, and
**Cross filter direction: Single**.

Never set cross-filter to "Both". Single direction, dimension filters fact, is
correct star-schema wiring and is the first thing anyone who knows Power BI will
check in an interview.

**Mark the date table:** click `dim_date` in the Data pane → **Table tools**
ribbon → **Mark as date table** → choose `date_key` → OK.

---

## 6. Make a home for measures (2 minutes)

1. **Home** → **Enter data**
2. Do not type any data. Set **Name** to `_Measures` (the underscore sorts it to
   the top) and click **Load**
3. After you create your first measure below, right-click the leftover empty
   `Column1` and delete it

---

## 7. The cost slider (5 minutes)

1. **Modeling** ribbon → **New parameter** → **Numeric range**
2. Name: `Price per MWh`
3. Minimum `40`, Maximum `200`, Increment `10`, Default `100`
4. Leave "Add slicer to this page" checked → **Create**

These are the sourced low/central/high values from the Excel assumptions
register. The slider lets a viewer watch the dollar figure move, which makes it
obvious the number is an assumption rather than a measurement.

**Save now** (Ctrl+S) into `powerbi\` as `grid_stress`.

---

## 8. The measures (45 minutes)

For each one: click `_Measures` in the Data pane, then **Home** → **New
measure**, then paste the whole block including the name and `=`. One measure
per New measure click. Do not paste several at once.

### Base

```dax
Hours Analyzed = COUNTROWS ( fact_grid_hourly )
```

```dax
Avg Demand (MW) = AVERAGE ( fact_grid_hourly[demand_mw] )
```

```dax
Peak Demand (MW) = MAX ( fact_grid_hourly[demand_mw] )
```

### Forecast accuracy: the core

```dax
MAPE (%) = AVERAGE ( fact_grid_hourly[abs_pct_error] )
```

```dax
MAPE Normal (%) = CALCULATE ( [MAPE (%)], fact_grid_hourly[is_stress_hour] = FALSE )
```

```dax
MAPE Stress (%) = CALCULATE ( [MAPE (%)], fact_grid_hourly[is_stress_hour] = TRUE )
```

```dax
Stress Penalty (pp) = [MAPE Stress (%)] - [MAPE Normal (%)]
```

```dax
Stress Multiple = DIVIDE ( [MAPE Stress (%)], [MAPE Normal (%)] )
```

```dax
Forecast Bias (%) = AVERAGE ( fact_grid_hourly[pct_error] )
```

```dax
Hours Forecast Ran High (%) =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_grid_hourly ), fact_grid_hourly[pct_error] > 0 ),
    COUNTROWS ( fact_grid_hourly )
)
```

```dax
Bias Share of Error = DIVIDE ( ABS ( [Forecast Bias (%)] ), [MAPE (%)] )
```

These last two are worth more than they look. MAPE throws away the sign, so a
region that misses by 3 points in both directions and a region that misses by 3
points low every single hour score identically. `Bias Share of Error` recovers
that: near zero means the misses cancel and the forecast is noisy, near 100%
means almost every miss goes the same way and the forecast is calibrated wrong.
Those are different problems with different fixes, and on this data most
regions are the second kind.

### Confidence intervals: the ones that keep you honest

```dax
Penalty Low =
IF (
    HASONEVALUE ( dim_ba[ba_code] ),
    CALCULATE ( SUM ( bootstrap_intervals[lo] ), bootstrap_intervals[metric] = "stress_penalty_pp" )
)
```

```dax
Penalty High =
IF (
    HASONEVALUE ( dim_ba[ba_code] ),
    CALCULATE ( SUM ( bootstrap_intervals[hi] ), bootstrap_intervals[metric] = "stress_penalty_pp" )
)
```

The `HASONEVALUE` guard is the whole point. The intervals are per region. Drop
these on a card with all eight regions selected and a bare `SUM` cheerfully
adds eight lower bounds together and shows you a number that means nothing.
Blank is the honest answer there, so that is what it returns.

```dax
Is Significant =
VAR Lo = [Penalty Low]
VAR Hi = [Penalty High]
RETURN
    IF (
        NOT ISBLANK ( Lo ),
        IF ( Lo > 0 || Hi < 0, "Real effect", "Not distinguishable from zero" )
    )
```

```dax
Penalty With Interval =
VAR Pt = [Stress Penalty (pp)]
VAR Lo = [Penalty Low]
VAR Hi = [Penalty High]
RETURN
    IF (
        ISBLANK ( Lo ),
        FORMAT ( Pt, "+0.00;-0.00" ) & " pp (pooled)",
        FORMAT ( Pt, "+0.00;-0.00" ) & " pp [" & FORMAT ( Lo, "+0.00;-0.00" ) & ", "
            & FORMAT ( Hi, "+0.00;-0.00" ) & "]"
    )
```

`Penalty With Interval` is the one to put in tables. It prints e.g.
`+0.82 pp [+0.44, +1.19]`, so a reader never sees a point estimate naked, and
it falls back to `-0.05 pp (pooled)` rather than an invented interval when more
than one region is in scope.

### Skill against a naive baseline

```dax
MAPE Persistence (%) = AVERAGE ( fact_grid_hourly[abs_pct_error_persistence] )
```

```dax
Skill vs Persistence = 1 - DIVIDE ( [MAPE (%)], [MAPE Persistence (%)] )
```

```dax
Skill Normal = CALCULATE ( [Skill vs Persistence], fact_grid_hourly[is_stress_hour] = FALSE )
```

```dax
Skill Stress = CALCULATE ( [Skill vs Persistence], fact_grid_hourly[is_stress_hour] = TRUE )
```

Skill is "how much better than just reusing yesterday's demand at this hour".
Below zero means the published day-ahead forecast is worse than doing nothing.

### Data quality

```dax
Avg Abs Imbalance (%) = AVERAGEX ( fact_grid_hourly, ABS ( fact_grid_hourly[imbalance_pct] ) )
```

```dax
Hours Failing Balance Check =
CALCULATE ( COUNTROWS ( fact_grid_hourly ), fact_grid_hourly[is_balance_clean] = FALSE )
```

```dax
MAPE Clean (%) = CALCULATE ( [MAPE (%)], fact_grid_hourly[is_balance_clean] = TRUE )
```

If asked to explain one measure in an interview, pick `Avg Abs Imbalance (%)`.
`AVERAGEX` iterates row by row so `ABS()` applies before averaging; a plain
`AVERAGE` would let positive and negative imbalances cancel and report a
misleadingly clean number. That is an analytical point, not a syntax point.

### Ramp lens

```dax
MAPE Ramp Stress (%) = CALCULATE ( [MAPE (%)], fact_grid_hourly[is_ramp_stress_hour] = TRUE )
```

```dax
MAPE Ramp Normal (%) = CALCULATE ( [MAPE (%)], fact_grid_hourly[is_ramp_stress_hour] = FALSE )
```

```dax
Ramp Stress Penalty (pp) = [MAPE Ramp Stress (%)] - [MAPE Ramp Normal (%)]
```

```dax
Ramp Penalty Low =
IF (
    HASONEVALUE ( dim_ba[ba_code] ),
    CALCULATE ( SUM ( bootstrap_intervals[lo] ), bootstrap_intervals[metric] = "ramp_stress_penalty_pp" )
)
```

```dax
Ramp Penalty High =
IF (
    HASONEVALUE ( dim_ba[ba_code] ),
    CALCULATE ( SUM ( bootstrap_intervals[hi] ), bootstrap_intervals[metric] = "ramp_stress_penalty_pp" )
)
```

```dax
Ramp Penalty With Interval =
VAR Pt = [Ramp Stress Penalty (pp)]
VAR Lo = [Ramp Penalty Low]
VAR Hi = [Ramp Penalty High]
RETURN
    IF (
        ISBLANK ( Lo ),
        FORMAT ( Pt, "+0.00;-0.00" ) & " pp (pooled)",
        FORMAT ( Pt, "+0.00;-0.00" ) & " pp [" & FORMAT ( Lo, "+0.00;-0.00" ) & ", "
            & FORMAT ( Hi, "+0.00;-0.00" ) & "]"
    )
```

The ramp lens needs its own interval measures for the same reason the demand
lens does, and it needs them more: it is the lens where the largest point
estimate and the best-established one belong to different regions.

### Exposure and dollars

```dax
Shortfall (MWh) = SUM ( fact_grid_hourly[shortfall_mw] )
```

```dax
Stress Shortfall (MWh) = CALCULATE ( [Shortfall (MWh)], fact_grid_hourly[is_stress_hour] = TRUE )
```

```dax
Stress Shortfall Upper Bound ($M) =
DIVIDE ( [Stress Shortfall (MWh)] * 'Price per MWh'[Price per MWh Value], 1000000 )
```

```dax
Net Import at Stress (MW) =
CALCULATE ( AVERAGE ( fact_grid_hourly[net_import_mw] ), fact_grid_hourly[is_stress_hour] = TRUE )
```

Call the dollar measure an **upper bound**, not a cost. It assumes every
under-forecast megawatt is bought at the cited real-time price, when in practice
reserves and demand response absorb some of it.

### Formatting

Select each measure, then **Measure tools** ribbon:

- `(%)` and `(pp)` → Decimal, 2 places
- skill measures, `Hours Forecast Ran High (%)`, `Bias Share of Error` →
  Percentage, 1 place. These are fractions, not percentage points; formatting
  them as plain decimals shows `0.26` where a reader expects `26.1%`
- `(MW)`, `(MWh)` → Whole number, thousands separator
- `($M)` → Currency, 1 decimal
- `Stress Multiple` → Decimal, 2 places

Fourteen decimal places is the fastest way to make good work look unfinished.

---

## 9. The six pages (90 minutes)

Add a page with the **+** at the bottom. Double-click the tab to rename. Pages
are named `1 Summary`, `2 Anatomy` and so on, so the tab strip reads in order.

Every visual is built the same way: click empty canvas → click a chart icon in
the Visualizations pane → drag fields from the Data pane into the field wells →
use the paint-roller **Format** icon to set the title, subtitle and position.

**Rule for every title: say what is plotted.** "Mean absolute % error by
region, normal and stress hours". Not a sentence about what it means: a chart
title that argues a conclusion stops being a label and starts being a caption,
and the reader has to check it against the bars. Conclusions live in
`reports/memo.pdf`.

Each page also gets the header band, the strip and the footer described in
section 0b. They are text boxes, not images: navy fill, no border, square
corners, and the same two of them on every page with only the finding line
changing.

### Page geometry, as built

These come from `ROW_HEIGHTS` and `COLUMN_WEIGHTS` in
`src/08_build_powerbi_report.py`; the script prints them when it runs.

| Page | Rows |
|---|---|
| 1 Summary | 5 KPI tiles (96) · column chart 3 : table 2 (256) · scatter 2 : table 3 (168) |
| 2 Anatomy | line : column (264) · histogram : bias column : bias table (268) |
| 3 Skill | 4 KPI tiles (96) · column 3 : table 2 (256) · column : line (168) |
| 4 Deep Dive | 4 KPI tiles (96) · load line 2 : error area 1 (210) · fuel area 2 : imports line 1 (214) |
| 5 Two Lenses | bar : table (328) · ramp column 2 : overlap column 1 (268) |
| 6 Methodology | three definition panels (268) · balance table 2 : intervals panel 1 (328) |

### Page 1: `Summary`

Slicers first: add a **Slicer**, drag `dim_ba[ba_name]` in. Add a second with
`dim_date[season]`. Put them top-right.

Five **Card** visuals across the top: `MAPE Normal (%)`, `MAPE Stress (%)`,
`Penalty With Interval`, `Skill Normal`, `Stress Shortfall Upper Bound ($M)`.
Retitle each card in Format → General → Title, since the raw measure name is not
self-explanatory.

The third card is `Penalty With Interval`, not `Stress Penalty (pp)`, and that
is deliberate: a bare penalty on a card is exactly the naked point estimate this
report exists to avoid. It holds a string rather than a number, so drop its
value font to about 15pt in Format → Callout value, or it truncates.

Main visual, **Clustered column chart**: `dim_ba[ba_code]` on X-axis;
`MAPE Normal (%)` and `MAPE Stress (%)` both on Y-axis. This is the picture that
answers the question. Two bars per region, and they are nearly the same height
almost everywhere.

Below it, a **Table** visual: `dim_ba[ba_name]`, `Penalty With Interval`,
`Is Significant`. This is the honesty panel.

Title the page with the real finding:

> Forecast error barely moves under stress: only NYIS measurably degrades

### Page 2: `Anatomy`

| Visual | Fields |
|---|---|
| Line chart | X `fact_grid_hourly[hour_local]`; Y `MAPE Stress (%)` and `MAPE Normal (%)` |
| Column chart | X `dim_date[year_month]`; Y `MAPE (%)` |
| Column chart | X `fact_grid_hourly[pct_error_bin]`; Y `Hours Analyzed` |
| Column chart | X `dim_ba[ba_code]`; Y `Forecast Bias (%)`, with a constant line at 0 |
| Table | `dim_ba[ba_code]`, `Forecast Bias (%)`, `MAPE (%)`, `Bias Share of Error`, `Hours Forecast Ran High (%)` |

`pct_error_bin` is a calculated column in the model, `ROUND(pct_error, 0)`. Use
it rather than binning `pct_error` in the visual: 139,055 distinct values makes
an unreadable chart, and one-percentage-point buckets are the right resolution
for this anyway.

**Read the histogram and the table together, and read the table second.**
Pooled, the signed error is a tight spike on zero, and it is tempting to stop
there and write "the error is noise". Split by region it is nothing of the kind.
CISO's mean signed error is -6.95 points against a MAPE of 8.36, so 83% of its
average error is one-directional under-forecasting, and only 21% of its hours
come in above actual. SWPP is the mirror image at +6.14 against 7.70, running
high in 71% of hours. MISO runs high in 84% of hours, NYIS runs low in 84%.
Seven of the eight regions land on one side in more than 65% of their hours.
ERCOT, at 58%, is the only one that is close to even.

That distinction decides what you would do about it. A noisy forecast needs a
better model. A forecast that misses the same way nearly every hour needs its
calibration fixed, which is cheaper, and it tells you which direction the
exposure runs: a region that under-forecasts buys energy short in the real-time
market, a region that over-forecasts commits capacity it does not need.

### Page 3: `Skill`

This page did not exist in the old tutorial and it is one of the strongest.

| Visual | Fields |
|---|---|
| 4 cards | `Skill Normal`, `Skill Stress`, `MAPE (%)`, `MAPE Persistence (%)` |
| Clustered column | X `dim_ba[ba_code]`; Y `Skill Normal` and `Skill Stress` |
| Table | `ba_code`, `Skill Normal`, `Skill Stress`, `MAPE (%)`, `MAPE Clean (%)` |
| Two text panels | why skill rather than error; why the two negatives differ |

Add a constant line at zero: select the chart → **Add further analyses** (the
magnifying glass) → **Constant line** → Value 0 → make it red.

CISO and SWPP go below the line. That is the finding. The table earns the tall
row rather than the text, because it has nine rows to show and text does not
care how much height it gets.

### Page 4: `Deep Dive`

Add a **Slicer** with `dim_date[date_key]`, and in Format set its style to
**Between**, so you can zoom the page to one week.

| Visual | Fields |
|---|---|
| Line chart | X `ts_local`; Y `demand_mw` and `forecast_mw` |
| Area chart | X `ts_local`; Y `forecast_error_mw` |
| Stacked area | X `ts_local`; Y `generation_mw`; Legend `dim_fuel[fuel_name]` |
| Line chart | X `ts_local`; Y `net_import_mw` |

Then look up what the weather actually was that week and put one sentence in a
text box. It takes four minutes and makes the project about the real world
instead of a CSV.

### Page 5: `Two Lenses`

| Visual | Fields |
|---|---|
| Clustered bar | Y `dim_ba[ba_code]`; X `Stress Penalty (pp)` and `Ramp Stress Penalty (pp)` |
| Table | `dim_ba[ba_name]`, `Penalty With Interval`, `Ramp Penalty With Interval`, `analysis_ramp_stress_penalty[pct_overlap_with_demand_stress]` |

The two definitions of "stress" share only 5-12% of their hours and produce
different rankings. Get the next sentence right, because it is easy to get
wrong. Only two ramp penalties clear zero on the positive side. Southern
Company has the larger point estimate, +1.85 pp, and the widest interval in the
study, [+0.38, +4.56]. PJM's is +1.78 pp at [+1.52, +2.04], an interval eight
times narrower, and PJM is a region that improves under the demand definition.
Largest and best-pinned-down are different regions here. An earlier draft of
this guide, and the memo, both said one region was both.

Title it:

> Change the definition of stress and the ranking changes

### Page 6: `Methodology`

Mostly text boxes (**Insert** → **Text box**) and one table. Almost nobody
builds this page, which is exactly why it is worth building.

1. The question, verbatim
2. The stress-hour definition and its three justifications
3. A **Table**: `dim_ba[ba_name]`, `Avg Abs Imbalance (%)`, `Hours Failing
   Balance Check`, `MAPE Clean (%)`. This is the CISO story
4. Text: the handling decisions (impossible values dropped not interpolated,
   92 zero-forecast NYIS hours excluded, balance failures reported not corrected)
5. Text: limitations (MISO/SWPP timezone simplification, raw not adjusted series,
   the price band is an assumption, 24 months is short)
6. Text: source and pull date, from `reports/pull_manifest.csv`

When you walk someone through this file: sixty seconds on page 1, then jump
straight here. Volunteering your own limitations before anyone asks is the
single most credibility-building move in a portfolio review.

---

## 10. The numbers your pages should show

Sanity-check against these. If a visual disagrees, the visual is wrong.

| Fact | Value |
|---|---|
| Rows in `fact_grid_hourly` | 139,055, of which 6,961 are stress hours |
| Pooled MAPE, stress vs normal | 3.88% vs 3.93% |
| Only region that measurably degrades | **NYIS, +0.82 pp [+0.44, +1.19], 1.31x** |
| Regions that measurably improve | ISNE −1.73 pp (0.40x), PJM −0.30 pp |
| SWPP (looks bad, is not) | +0.42 pp **[−0.98, +1.93]** |
| Skill vs persistence | +26.1% normal, +31.9% stress |
| Negative skill | CISO (−73.3% normal) and SWPP (−77.2% normal) |
| CISO MAPE, all vs balance-clean hours | 8.36% → 6.95% |
| CISO penalty, all vs clean | +0.15 pp → **−1.67 pp** |
| CISO hours failing the balance check | 6,396 of the 17,304 it can be run on |
| Largest ramp-lens penalty | SOCO +1.85 pp, but [+0.38, +4.56] |
| The one the interval pins down | PJM +1.78 pp [+1.52, +2.04] |
| Largest one-directional bias | CISO −6.95 pp, SWPP +6.14 pp |
| Regions missing one way in >65% of hours | 7 of 8; only ERCOT is near even |
| PJM, week of 20 Jun 2025 | peak 160,560 MW, 4.51% MAPE, worst hour 13.7% |
| Stress-hour shortfall, upper bound at $100/MWh | $733.9M over 24 months |
| The same at the $40 and $200 ends of the band | $293.6M and $1,467.8M |

---

## 11. Saving, and why there is no .pbix

If you built this by hand, save it with **File > Save as > Power BI project
file (.pbip)** into `powerbi\`, not as a `.pbix`.

A `.pbix` is a zip with the data compressed inside it. It is 30-60 MB, it is
opaque in a diff, and two people editing it produce a merge conflict nobody can
resolve. A `.pbip` is the same report as text: TMDL for the model, JSON for the
pages. Rename a measure and the diff shows you a renamed measure. `.gitignore`
excludes `*.pbix` for that reason.

For screenshots, **File > Export > Export to PDF** and crop, or the Snipping
Tool (Win+Shift+S), into `docs\screenshots\`.

---

## 12. When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Stress measures return blank | `is_stress_hour` imported as Text | Power Query → change to True/False → Close & Apply |
| Relationship refuses to create | Type mismatch on the key | Both `ba_code` must be Text, both `date_key` must be Date |
| Numbers look doubled or wrong after slicing | A relationship is set to "Both" | Double-click the line, set Cross filter to Single |
| Parquet connector errors | Older Power BI build | Update via Microsoft Store, or use the `make csv` fallback |
| Fuel table will not join the calendar | Missing calculated column | Redo section 4 |
| Peak demand appears at 3am | Timezone converted backwards | Not possible here: the warehouse already did this correctly. Daily peaks land at hours 17-19 local in every region, and CISO net load bottoms out at 14:00 and peaks at 21:00, which is the duck curve. If you see 3am you are charting `ts_utc` instead of `ts_local` |
| A slicer shows the right dates but filters nothing | A default selection saved on a slicer does not always apply on open | Set the range as a page filter in the Filters pane instead. Page 4 does it that way |
| Everything is slow | 1.2M-row fuel table | Normal. Avoid putting `fact_fuel_hourly` on a page without a filter |

---

## What "done" looks like

- `powerbi/grid_stress.pbip` committed, opening and refreshing cleanly
- At least one screenshot in `docs/screenshots/`
- Every page title states a finding
- Page 1 leads with the null result, not a false headline
- No point estimate shown anywhere without its interval

All five hold for what is in `powerbi/` now.
