-- ===========================================================================
-- 03_build_warehouse.sql
-- Builds a star schema from raw EIA-930 parquet files.
-- Engine: DuckDB
-- Grain: fact_grid_hourly  = balancing authority x UTC hour
--        fact_fuel_hourly  = balancing authority x UTC hour x fuel type
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- DIMENSION: BALANCING AUTHORITY
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_ba AS
SELECT * FROM (VALUES
    ('PJM',  'PJM Interconnection',      'Mid Atlantic', 'Eastern',     'America/New_York',    TRUE),
    ('MISO', 'Midcontinent ISO',         'Midwest',      'Eastern',     'America/New_York',    FALSE),
    ('CISO', 'California ISO',           'West',         'Western',     'America/Los_Angeles', FALSE),
    ('ERCO', 'ERCOT',                    'Texas',        'Texas',       'America/Chicago',     FALSE),
    ('ISNE', 'ISO New England',          'Northeast',    'Eastern',     'America/New_York',    FALSE),
    ('NYIS', 'New York ISO',             'Northeast',    'Eastern',     'America/New_York',    FALSE),
    ('SWPP', 'Southwest Power Pool',     'Central',      'Eastern',     'America/Chicago',     FALSE),
    ('SOCO', 'Southern Company',         'Southeast',    'Eastern',     'America/New_York',    FALSE)
) AS t(ba_code, ba_name, region, interconnection, local_tz, is_home_grid);

-- NOTE: MISO and SWPP span multiple time zones. A single local_tz is a
-- documented simplification. See memo limitations section.


-- ---------------------------------------------------------------------------
-- DIMENSION: FUEL TYPE
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_fuel AS
SELECT * FROM (VALUES
    ('COL', 'Coal',          'Thermal',      FALSE, TRUE,  1),
    ('NG',  'Natural gas',   'Thermal',      FALSE, TRUE,  2),
    ('NUC', 'Nuclear',       'Thermal',      FALSE, FALSE, 3),
    ('OIL', 'Petroleum',     'Thermal',      FALSE, TRUE,  4),
    ('WAT', 'Hydro',         'Renewable',    TRUE,  TRUE,  5),
    ('SUN', 'Solar',         'Renewable',    TRUE,  FALSE, 6),
    ('WND', 'Wind',          'Renewable',    TRUE,  FALSE, 7),
    ('OTH', 'Other',         'Other',        FALSE, FALSE, 8),
    ('UNK', 'Unknown',       'Other',        FALSE, FALSE, 9)
) AS t(fuel_code, fuel_name, fuel_group, is_renewable, is_dispatchable, sort_order);

-- is_dispatchable: can the operator call on it at will? Solar and wind cannot
-- be dispatched up, which is the entire reason net load ramp matters.


-- ---------------------------------------------------------------------------
-- STAGING: pivot the long region data into one row per BA hour
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_region AS
SELECT
    respondent                                          AS ba_code,
    CAST(strptime(period, '%Y-%m-%dT%H') AS TIMESTAMP)  AS ts_utc,
    MAX(CASE WHEN type = 'D'  THEN CAST(value AS DOUBLE) END) AS demand_mw,
    MAX(CASE WHEN type = 'DF' THEN CAST(value AS DOUBLE) END) AS forecast_mw,
    MAX(CASE WHEN type = 'NG' THEN CAST(value AS DOUBLE) END) AS net_gen_mw,
    MAX(CASE WHEN type = 'TI' THEN CAST(value AS DOUBLE) END) AS interchange_mw
FROM read_parquet('data/raw/region_*.parquet')
GROUP BY 1, 2;


-- ---------------------------------------------------------------------------
-- STAGING: apply local time, season, and quality filters
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_region_enriched AS
WITH lagged AS (
    -- Naive baselines, computed on the UNFILTERED staging table so the lag is a
    -- true 24 / 168 hour offset rather than "24 surviving rows back".
    SELECT
        ba_code,
        ts_utc,
        LAG(demand_mw, 24)  OVER (PARTITION BY ba_code ORDER BY ts_utc) AS naive_persistence_mw,
        LAG(demand_mw, 168) OVER (PARTITION BY ba_code ORDER BY ts_utc) AS naive_seasonal_mw
    FROM stg_region
)
SELECT
    s.ba_code,
    s.ts_utc,
    -- Convert UTC to local. The inner AT TIME ZONE declares that ts_utc IS UTC;
    -- the outer one converts that instant into local wall clock time. Applying
    -- AT TIME ZONE only once converts in the WRONG DIRECTION and silently shifts
    -- every hour by twice the offset. Verify against a known hour before trusting it.
    (s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz AS ts_local,
    s.demand_mw,
    s.forecast_mw,
    s.net_gen_mw,
    s.interchange_mw,
    l.naive_persistence_mw,
    l.naive_seasonal_mw,

    -- Season is defined on LOCAL time, because load is driven by local weather.
    CASE
        WHEN EXTRACT(month FROM ((s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz)) IN (12,1,2) THEN 'Winter'
        WHEN EXTRACT(month FROM ((s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz)) IN (3,4,5)  THEN 'Spring'
        WHEN EXTRACT(month FROM ((s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz)) IN (6,7,8)  THEN 'Summer'
        ELSE 'Fall'
    END                                                 AS season,

    -- Balance identity residual. See Part 4.4.
    s.net_gen_mw - s.interchange_mw - s.demand_mw       AS imbalance_mw

FROM stg_region s
JOIN dim_ba b ON b.ba_code = s.ba_code
LEFT JOIN lagged l ON l.ba_code = s.ba_code AND l.ts_utc = s.ts_utc
WHERE s.demand_mw  IS NOT NULL
  AND s.forecast_mw IS NOT NULL
  AND s.demand_mw  > 0
  AND s.forecast_mw > 0;
-- Rows failing these conditions are excluded, not interpolated.
-- Rationale is documented in reports/data_quality_report.md.
-- forecast_mw > 0 drops 92 NYIS hours that report a day-ahead forecast of
-- exactly zero. The form instructions require DF to be positive, so those are
-- missing values encoded as zero; left in, each one contributes a spurious
-- 100% error and inflates both NYIS's MAPE and every tail statistic.


-- ---------------------------------------------------------------------------
-- FACT: grid hourly (base)
-- This is where the window functions do the real work. Enriched into the
-- final fact_grid_hourly further down.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_grid_hourly_base AS
WITH ranked AS (
    SELECT
        *,
        -- Demand percentile WITHIN balancing authority AND season.
        -- This is the stress hour definition from Part 4.7.
        PERCENT_RANK() OVER (
            PARTITION BY ba_code, season
            ORDER BY demand_mw
        ) AS demand_pctile,

        -- Hour over hour ramp. Large positive ramps are when operators sweat.
        demand_mw - LAG(demand_mw) OVER (
            PARTITION BY ba_code
            ORDER BY ts_utc
        ) AS ramp_1h_mw,

        -- Rolling 24 hour average demand, for context on any single hour.
        AVG(demand_mw) OVER (
            PARTITION BY ba_code
            ORDER BY ts_utc
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS demand_ma24_mw

    FROM stg_region_enriched
)
SELECT
    ba_code,
    ts_utc,
    ts_local,
    CAST(ts_local AS DATE)                              AS date_key,
    EXTRACT(hour FROM ts_local)                         AS hour_local,
    season,

    demand_mw,
    forecast_mw,
    net_gen_mw,
    interchange_mw,
    naive_persistence_mw,
    naive_seasonal_mw,

    -- Positive interchange means the BA is a net EXPORTER, so imports are the
    -- negative of it. Flipping the sign here saves confusion downstream.
    -interchange_mw                                     AS net_import_mw,

    -- ---- Forecast error metrics ----
    forecast_mw - demand_mw                             AS forecast_error_mw,
    ABS(forecast_mw - demand_mw)                        AS abs_error_mw,
    100.0 * (forecast_mw - demand_mw) / demand_mw       AS pct_error,
    100.0 * ABS(forecast_mw - demand_mw) / demand_mw    AS abs_pct_error,

    -- Naive baselines. A forecast is only impressive relative to the cheapest
    -- thing you could have done instead: yesterday's demand, or last week's.
    100.0 * ABS(naive_persistence_mw - demand_mw) / demand_mw AS abs_pct_error_persistence,
    100.0 * ABS(naive_seasonal_mw - demand_mw) / demand_mw    AS abs_pct_error_seasonal,

    -- Under forecasting is the expensive direction: actual exceeded forecast,
    -- so the shortfall had to be bought in the real time market.
    CASE WHEN forecast_mw < demand_mw
         THEN demand_mw - forecast_mw ELSE 0 END        AS shortfall_mw,

    -- ---- Stress classification ----
    demand_pctile,
    CASE WHEN demand_pctile >= 0.95 THEN TRUE ELSE FALSE END AS is_stress_hour,
    CASE WHEN demand_pctile >= 0.99 THEN TRUE ELSE FALSE END AS is_extreme_hour,

    ramp_1h_mw,
    demand_ma24_mw,
    imbalance_mw,
    100.0 * imbalance_mw / demand_mw                    AS imbalance_pct,

    -- An hour where the reported numbers actually balance. Where they do not,
    -- a large "forecast error" may be a reporting artifact instead.
    ABS(100.0 * imbalance_mw / demand_mw) <= 5          AS is_balance_clean

FROM ranked;


-- ---------------------------------------------------------------------------
-- FACT: fuel hourly
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_fuel_hourly AS
WITH parsed AS (
    SELECT
        f.respondent                                        AS ba_code,
        CAST(strptime(f.period, '%Y-%m-%dT%H') AS TIMESTAMP) AS ts_utc,
        f.fueltype                                          AS fuel_code,
        CAST(f.value AS DOUBLE)                             AS generation_mw
    FROM read_parquet('data/raw/fuel_*.parquet') f
    WHERE f.value IS NOT NULL
)
SELECT
    p.ba_code,
    p.ts_utc,
    -- Same double AT TIME ZONE as the region fact. Carrying local time on the
    -- fuel table too means a fuel mix chart and a demand chart can share one
    -- x axis; without it the two facts can only be compared at UTC hours,
    -- which puts a California evening peak in the middle of the next morning.
    (p.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz   AS ts_local,
    CAST((p.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz AS DATE) AS date_key,
    p.fuel_code,
    p.generation_mw
FROM parsed p
JOIN dim_ba b ON b.ba_code = p.ba_code;
-- date_key is derived from LOCAL time, matching fact_grid_hourly, so both
-- facts land on the same calendar day in dim_date.


-- ---------------------------------------------------------------------------
-- FACT: grid hourly, enriched
-- Adds net load (demand minus the generation that cannot be dispatched, which
-- is what dispatchable plants actually have to chase), its ramp, and a second
-- stress lens keyed on ramp rather than demand level. A grid can be strained
-- by how fast load is moving, not only by how high it is, and whether the two
-- definitions pick out the same hours is itself worth knowing.
--
-- Built in one pass from fact_grid_hourly_base. Each CTE feeds the next
-- because a window function cannot be nested inside another one: the ramp
-- needs net load to exist first, and the ramp percentile needs the ramp.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_grid_hourly AS
WITH vre AS (
    SELECT
        ba_code,
        ts_utc,
        SUM(CASE WHEN fuel_code = 'SUN' THEN generation_mw ELSE 0 END) AS solar_mw,
        SUM(CASE WHEN fuel_code = 'WND' THEN generation_mw ELSE 0 END) AS wind_mw
    FROM fact_fuel_hourly
    GROUP BY 1, 2
),
with_net_load AS (
    SELECT
        g.*,
        COALESCE(v.solar_mw, 0)                                  AS solar_mw,
        COALESCE(v.wind_mw, 0)                                   AS wind_mw,
        g.demand_mw - COALESCE(v.solar_mw,0) - COALESCE(v.wind_mw,0) AS net_load_mw,
        100.0 * (COALESCE(v.solar_mw,0) + COALESCE(v.wind_mw,0))
            / NULLIF(g.demand_mw, 0)                             AS vre_share_pct
    FROM fact_grid_hourly_base g
    LEFT JOIN vre v
      ON v.ba_code = g.ba_code AND v.ts_utc = g.ts_utc
),
with_ramp AS (
    SELECT
        *,
        net_load_mw - LAG(net_load_mw) OVER (
            PARTITION BY ba_code ORDER BY ts_utc
        )                                                        AS net_load_ramp_1h_mw
    FROM with_net_load
)
SELECT
    *,
    PERCENT_RANK() OVER (
        PARTITION BY ba_code, season
        ORDER BY ABS(net_load_ramp_1h_mw)
    ) >= 0.95                                                    AS is_ramp_stress_hour
FROM with_ramp;


-- ---------------------------------------------------------------------------
-- DIMENSION: DATE
-- Built from the fact table so it always covers exactly the right span.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT MIN(date_key) AS d0, MAX(date_key) AS d1 FROM fact_grid_hourly
),
days AS (
    SELECT UNNEST(generate_series(
        (SELECT d0 FROM bounds),
        (SELECT d1 FROM bounds),
        INTERVAL 1 DAY
    )) AS d
)
SELECT
    CAST(d AS DATE)                                     AS date_key,
    EXTRACT(year   FROM d)                              AS year,
    EXTRACT(month  FROM d)                              AS month_num,
    strftime(d, '%B')                                   AS month_name,
    strftime(d, '%Y-%m')                                AS year_month,
    EXTRACT(quarter FROM d)                             AS quarter,
    EXTRACT(dow FROM d)                                 AS day_of_week_num,
    strftime(d, '%A')                                   AS day_name,
    CASE WHEN EXTRACT(dow FROM d) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
    CASE
        WHEN EXTRACT(month FROM d) IN (12,1,2) THEN 'Winter'
        WHEN EXTRACT(month FROM d) IN (3,4,5)  THEN 'Spring'
        WHEN EXTRACT(month FROM d) IN (6,7,8)  THEN 'Summer'
        ELSE 'Fall'
    END                                                 AS season
FROM days;


-- ---------------------------------------------------------------------------
-- THE HEADLINE ANALYSIS
-- Does forecast error get worse during stress hours?
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE analysis_stress_penalty AS
SELECT
    g.ba_code,
    b.ba_name,
    b.region,

    COUNT(*)                                                     AS total_hours,
    SUM(CASE WHEN is_stress_hour THEN 1 ELSE 0 END)              AS stress_hours,

    ROUND(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END), 3) AS mape_normal,
    ROUND(AVG(CASE WHEN is_stress_hour     THEN abs_pct_error END), 3) AS mape_stress,
    ROUND(AVG(CASE WHEN is_extreme_hour    THEN abs_pct_error END), 3) AS mape_extreme,

    -- The headline number: how much worse is the forecast when it matters?
    ROUND(
        AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
      - AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END)
    , 3)                                                         AS stress_penalty_pp,

    -- Ratio form, which is often the more quotable version.
    ROUND(
        AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
      / NULLIF(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END), 0)
    , 2)                                                         AS stress_multiple,

    -- ---- Tail error ----
    -- The mean is the wrong statistic for an operator: what hurts is the hour
    -- the forecast missed badly, not the average hour.
    ROUND(QUANTILE_CONT(CASE WHEN NOT is_stress_hour THEN abs_pct_error END, 0.95), 3) AS p95_abs_pct_error_normal,
    ROUND(QUANTILE_CONT(CASE WHEN is_stress_hour     THEN abs_pct_error END, 0.95), 3) AS p95_abs_pct_error_stress,
    ROUND(QUANTILE_CONT(CASE WHEN is_stress_hour     THEN abs_pct_error END, 0.99), 3) AS p99_abs_pct_error_stress,
    ROUND(MAX(abs_pct_error), 3)                                 AS worst_hour_abs_pct_error,

    -- ---- Restricted to hours where the reported data balances ----
    -- Separates "the forecast was wrong" from "the reporting does not add up".
    SUM(CASE WHEN is_balance_clean THEN 1 ELSE 0 END)            AS balance_clean_hours,
    ROUND(AVG(CASE WHEN is_balance_clean THEN abs_pct_error END), 3) AS mape_clean,
    ROUND(AVG(CASE WHEN is_balance_clean AND NOT is_stress_hour THEN abs_pct_error END), 3) AS mape_clean_normal,
    ROUND(AVG(CASE WHEN is_balance_clean AND is_stress_hour     THEN abs_pct_error END), 3) AS mape_clean_stress,
    ROUND(
        AVG(CASE WHEN is_balance_clean AND is_stress_hour THEN abs_pct_error END)
      - AVG(CASE WHEN is_balance_clean AND NOT is_stress_hour THEN abs_pct_error END)
    , 3)                                                         AS stress_penalty_clean_pp,

    -- ---- Naive baselines and skill scores ----
    -- Skill = 1 - (forecast error / baseline error). Positive means the
    -- day-ahead forecast beats the naive baseline by that fraction.
    ROUND(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error_persistence END), 3) AS mape_persistence_normal,
    ROUND(AVG(CASE WHEN is_stress_hour     THEN abs_pct_error_persistence END), 3) AS mape_persistence_stress,
    ROUND(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error_seasonal END), 3)    AS mape_seasonal_normal,
    ROUND(AVG(CASE WHEN is_stress_hour     THEN abs_pct_error_seasonal END), 3)    AS mape_seasonal_stress,

    ROUND(1 - AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END)
            / NULLIF(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error_persistence END), 0)
    , 3)                                                         AS skill_vs_persistence_normal,
    ROUND(1 - AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
            / NULLIF(AVG(CASE WHEN is_stress_hour THEN abs_pct_error_persistence END), 0)
    , 3)                                                         AS skill_vs_persistence_stress,
    ROUND(1 - AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END)
            / NULLIF(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error_seasonal END), 0)
    , 3)                                                         AS skill_vs_seasonal_normal,
    ROUND(1 - AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
            / NULLIF(AVG(CASE WHEN is_stress_hour THEN abs_pct_error_seasonal END), 0)
    , 3)                                                         AS skill_vs_seasonal_stress,

    -- Bias: positive means the forecast tends to run high.
    ROUND(AVG(CASE WHEN is_stress_hour THEN pct_error END), 3)   AS bias_stress_pct,

    -- Exposure context
    ROUND(AVG(CASE WHEN is_stress_hour THEN net_import_mw END), 0) AS avg_net_import_stress_mw,
    ROUND(MAX(ramp_1h_mw), 0)                                    AS max_1h_ramp_mw,
    ROUND(SUM(CASE WHEN is_stress_hour THEN shortfall_mw ELSE 0 END), 0) AS total_stress_shortfall_mwh

FROM fact_grid_hourly g
JOIN dim_ba b ON b.ba_code = g.ba_code
GROUP BY 1, 2, 3
ORDER BY stress_penalty_pp DESC;


-- ---------------------------------------------------------------------------
-- THE SAME ANALYSIS, KEYED ON RAMP STRESS INSTEAD OF DEMAND LEVEL
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE analysis_ramp_stress_penalty AS
SELECT
    g.ba_code,
    b.ba_name,
    b.region,

    COUNT(*)                                                     AS total_hours,
    SUM(CASE WHEN is_ramp_stress_hour THEN 1 ELSE 0 END)         AS ramp_stress_hours,

    -- How much do the two stress definitions actually overlap? If the answer
    -- is "barely", then which lens you pick decides your conclusion.
    ROUND(100.0 * SUM(CASE WHEN is_ramp_stress_hour AND is_stress_hour THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN is_ramp_stress_hour THEN 1 ELSE 0 END), 0), 1) AS pct_overlap_with_demand_stress,

    ROUND(AVG(CASE WHEN NOT is_ramp_stress_hour THEN abs_pct_error END), 3) AS mape_normal,
    ROUND(AVG(CASE WHEN is_ramp_stress_hour     THEN abs_pct_error END), 3) AS mape_ramp_stress,
    ROUND(
        AVG(CASE WHEN is_ramp_stress_hour THEN abs_pct_error END)
      - AVG(CASE WHEN NOT is_ramp_stress_hour THEN abs_pct_error END)
    , 3)                                                         AS ramp_stress_penalty_pp,
    ROUND(
        AVG(CASE WHEN is_ramp_stress_hour THEN abs_pct_error END)
      / NULLIF(AVG(CASE WHEN NOT is_ramp_stress_hour THEN abs_pct_error END), 0)
    , 2)                                                         AS ramp_stress_multiple

FROM fact_grid_hourly g
JOIN dim_ba b ON b.ba_code = g.ba_code
GROUP BY 1, 2, 3
ORDER BY ramp_stress_penalty_pp DESC;
