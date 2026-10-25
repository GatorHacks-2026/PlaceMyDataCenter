###v3

#!/usr/bin/env python3
"""
dc_site_report.py - ONE input block -> POWER + WATER + CARBON + NOISE report for a data-center site (US).

HOW THE MODULES ARE CONNECTED
  your input (STATE, LAT/LON, IT_MW, PUE, LOAD_FACTOR, WUE, ...)
     -> facility(): peak MW = IT*PUE, average MW = peak*load, MWh/yr, water need MGD   (the shared numbers)
     -> POWER  : EIA state surplus (kW) vs facility average kW
     -> WATER  : USGS river dry-period flow (MGD) vs facility water need
     -> CARBON : facility MWh/yr x state grid factor (+ diesel generator)
     -> NOISE  : source levels (scaled with MW) -> dB(A) at the house distance vs your limits
  -> SIMPLE REPORT (Marathi or English, no formulas) + one-line decision + "what could fix it"
  -> optional PROOF report (set OUTPUT["SHOW_PROOF"]=True) and a JSON brief you can give to an AI later (no AI is called here)
  A layer that fails (no key, no network, no data) is shown as NOT CHECKED; the others still run. Nothing is saved to disk.
Keys are never stored in the file: env EIA_API_KEY / API_USGS_PAT, or a hidden prompt.
Colab:  !pip -q install dataretrieval pandas requests   then run this cell.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd


import math
from dataclasses import dataclass, field

LB_TO_KG = 0.45359237
HOURS_YEAR = 8760.0

# eGRID2023 total-output CO2e, lb/MWh (EPA summary tables rev1)
EGRID_LB_PER_MWH = {
    "AKGD": 904.5, "AKMS": 521.4, "AZNM": 743.4, "CAMX": 438.2, "ERCT": 740.8, "FRCC": 804.5,
    "HIMS": 1132.0, "HIOA": 1498.8, "MROE": 1409.7, "MROW": 926.4, "NEWE": 541.1, "NWPP": 635.2,
    "NYCW": 976.1, "NYLI": 1189.3, "NYUP": 241.7, "PRMS": 1548.4, "RFCE": 597.0, "RFCM": 967.4,
    "RFCW": 916.0, "RMPA": 1042.0, "SPNO": 867.7, "SPSO": 894.7, "SRMV": 741.4, "SRMW": 1247.0,
    "SRSO": 844.6, "SRTV": 900.9, "SRVC": 593.1, "US": 775.2,
}
GRID_KG_PER_MWH = {k: v * LB_TO_KG for k, v in EGRID_LB_PER_MWH.items()}

DIESEL_CO2_KG_GAL = 10.21
DIESEL_CH4_G_MMBTU, DIESEL_N2O_G_MMBTU, DIESEL_MMBTU_GAL = 3.0, 0.60, 0.138
GWP_CH4, GWP_N2O = 28.0, 265.0
DIESEL_CO2E_KG_GAL = DIESEL_CO2_KG_GAL + DIESEL_MMBTU_GAL * (
    DIESEL_CH4_G_MMBTU * GWP_CH4 + DIESEL_N2O_G_MMBTU * GWP_N2O) / 1000.0


# ----------------------------------------------------------------------------- CARBON
def grid_factor(subregion: str = "US") -> float:
    """kg CO2e per MWh for an eGRID subregion code (e.g. ERCT, CAMX) or 'US'."""
    k = subregion.upper()
    if k not in GRID_KG_PER_MWH:
        raise KeyError(f"unknown eGRID subregion {subregion!r}; use one of {sorted(GRID_KG_PER_MWH)}")
    return GRID_KG_PER_MWH[k]


def carbon(it_mw: float, pue: float = 1.4, load_factor: float = 0.8, factor_kg_mwh: float | None = None,
           subregion: str = "US", renewable_share: float = 0.0, gen_mw: float = 0.0,
           gen_hours: float = 50.0, gen_gal_per_kwh: float = 0.07) -> dict:
    """Annual carbon of one site.
    it_mw          IT (server) load at full build-out, MW
    pue            facility MW / IT MW (>=1)
    load_factor    average share of full load over the year (0-1)
    factor_kg_mwh  grid factor; default = eGRID value of `subregion`
    renewable_share  0-1 share of energy covered by contracted clean power (market-based view)
    gen_mw, gen_hours  backup generator capacity and hours run per year (tests + outages)
    """
    if it_mw < 0 or pue < 1 or not 0 <= load_factor <= 1 or not 0 <= renewable_share <= 1:
        raise ValueError("need it_mw>=0, pue>=1, load_factor 0-1, renewable_share 0-1")
    if gen_mw < 0 or gen_hours < 0 or gen_gal_per_kwh < 0:
        raise ValueError("generator inputs must be >= 0")
    f = grid_factor(subregion) if factor_kg_mwh is None else float(factor_kg_mwh)
    if f < 0:
        raise ValueError("grid factor must be >= 0")
    mwh_it = it_mw * load_factor * HOURS_YEAR
    mwh_fac = mwh_it * pue
    scope2_loc_t = mwh_fac * f / 1000.0                       # location-based
    scope2_mkt_t = scope2_loc_t * (1.0 - renewable_share)     # market-based (simplified)
    gen_mwh = gen_mw * gen_hours
    gallons = gen_mwh * 1000.0 * gen_gal_per_kwh
    scope1_t = gallons * DIESEL_CO2E_KG_GAL / 1000.0
    tot_loc, tot_mkt = scope2_loc_t + scope1_t, scope2_mkt_t + scope1_t
    return dict(it_mwh=mwh_it, facility_mwh=mwh_fac, factor_kg_mwh=f, diesel_gal=gallons,
                scope1_t=scope1_t, scope2_location_t=scope2_loc_t, scope2_market_t=scope2_mkt_t,
                total_location_t=tot_loc, total_market_t=tot_mkt,
                kg_per_mwh_it=(tot_loc * 1000.0 / mwh_it) if mwh_it else float("nan"),
                t_per_it_mw=(tot_loc / it_mw) if it_mw else float("nan"))


# ----------------------------------------------------------------------------- NOISE
def db_sum(levels) -> float:
    """Add several dB levels (incoherent sources): 10*log10(sum 10^(L/10)). Empty -> -inf."""
    s = sum(10 ** (l / 10.0) for l in levels)
    return 10 * math.log10(s) if s > 0 else float("-inf")


@dataclass
class NoiseSource:
    name: str
    level_dba: float          # sound pressure level of ONE unit measured at ref_m
    ref_m: float = 10.0
    count: int = 1
    distance_m: float = 100.0  # distance from this source cluster to the receiver


# Typical-order-of-magnitude defaults (ASSUMED; press-article range 75-95 dB(A) "close range" for fan arrays).
DEFAULT_SOURCES = [
    NoiseSource("cooling fans / dry coolers (per unit)", 85.0, 10.0, 20, 150.0),
    NoiseSource("backup generators (per unit, in enclosure)", 80.0, 10.0, 10, 150.0),
    NoiseSource("transformers / substation", 70.0, 10.0, 2, 150.0),
]


def attenuate(level_at_ref: float, ref_m: float, dist_m: float, extra_loss_db: float = 0.0) -> float:
    """Point source in open field: L(d) = L(ref) - 20*log10(d/ref) - extra (wall/berm/air/ground)."""
    if ref_m <= 0 or dist_m <= 0:
        raise ValueError("distances must be > 0")
    return level_at_ref - 20.0 * math.log10(dist_m / ref_m) - extra_loss_db


def noise_at_receiver(sources=None, extra_loss_db: float = 0.0) -> float:
    """Combined dB(A) at the receiver from all sources (each has its own distance)."""
    sources = DEFAULT_SOURCES if sources is None else sources
    parts = []
    for s in sources:
        one = attenuate(s.level_dba, s.ref_m, s.distance_m, extra_loss_db)
        parts.append(one + 10 * math.log10(s.count) if s.count > 0 else float("-inf"))
    return db_sum([p for p in parts if p > float("-inf")])


def ldn(day_db: float, night_db: float) -> float:
    """Day-night level: 15 h day (07-22) + 9 h night (22-07) with +10 dB night penalty."""
    return 10 * math.log10((15 * 10 ** (day_db / 10) + 9 * 10 ** ((night_db + 10) / 10)) / 24.0)


def distance_for_limit(level_at_ref: float, ref_m: float, limit_db: float, extra_loss_db: float = 0.0) -> float:
    """How far from ONE equivalent source (level_at_ref at ref_m) until it falls to limit_db."""
    return ref_m * 10 ** ((level_at_ref - extra_loss_db - limit_db) / 20.0)


def noise_check(sources=None, limit_day=55.0, limit_night=45.0, ldn_limit=55.0, extra_loss_db: float = 0.0) -> dict:
    """Data centers run 24 h, so day level = night level = L. Pass/fail vs your limits."""
    L = noise_at_receiver(sources, extra_loss_db)
    d_ldn = ldn(L, L)
    return dict(level_dba=L, ldn_db=d_ldn, margin_day=limit_day - L, margin_night=limit_night - L,
                margin_ldn=ldn_limit - d_ldn,
                ok_day=L <= limit_day, ok_night=L <= limit_night, ok_ldn=d_ldn <= ldn_limit,
                limits=dict(day=limit_day, night=limit_night, ldn=ldn_limit))


# ----------------------------------------------------------------------------- REPORT
def report(it_mw=100, pue=1.4, load_factor=0.8, subregion="ERCT", renewable_share=0.0, gen_mw=150,
           gen_hours=50, sources=None, extra_loss_db=0.0, limit_day=55.0, limit_night=45.0):
    c = carbon(it_mw, pue, load_factor, None, subregion, renewable_share, gen_mw, gen_hours)
    n = noise_check(sources, limit_day, limit_night, 55.0, extra_loss_db)
    print(f"CARBON  ({it_mw:g} MW IT, PUE {pue:g}, load {load_factor:.0%}, grid {subregion} = {c['factor_kg_mwh']:.0f} kg/MWh)")
    print(f"  energy      : {c['facility_mwh']:,.0f} MWh/yr")
    print(f"  Scope 2 loc : {c['scope2_location_t']:,.0f} tCO2e/yr   market (renewable {renewable_share:.0%}): {c['scope2_market_t']:,.0f}")
    print(f"  Scope 1 gen : {c['scope1_t']:,.0f} tCO2e/yr  ({c['diesel_gal']:,.0f} gal diesel)")
    print(f"  TOTAL (loc) : {c['total_location_t']:,.0f} tCO2e/yr   = {c['kg_per_mwh_it']:.0f} kg per IT-MWh, {c['t_per_it_mw']:,.0f} t per IT-MW")
    print(f"NOISE  at receiver: {n['level_dba']:.1f} dB(A)   Ldn {n['ldn_db']:.1f}")
    print(f"  day limit {limit_day:g}: {'OK' if n['ok_day'] else 'FAIL'} ({n['margin_day']:+.1f})   "
          f"night limit {limit_night:g}: {'OK' if n['ok_night'] else 'FAIL'} ({n['margin_night']:+.1f})   "
          f"Ldn 55: {'OK' if n['ok_ldn'] else 'FAIL'} ({n['margin_ldn']:+.1f})")
    print("Screening only: assumptions for PUE, load, generator hours/fuel, source levels. Local ordinance limit may differ.")
    return c, n




# =============================================================================================
#  PART B  -  POWER + WATER + connection layer (one input block -> one report)
# =============================================================================================
import calendar
import os
from datetime import date, timedelta

# eGRID2023 STATE total-output CO2e, lb/MWh (EPA summary tables rev1; read from the PDF text - spot-check before reporting)
STATE_LB_PER_MWH = {
    "AK": 813.6, "AL": 714.0, "AR": 998.4, "AZ": 748.8, "CA": 402.5, "CO": 1090.4, "CT": 540.7, "DC": 395.0,
    "DE": 701.3, "FL": 808.3, "GA": 715.0, "HI": 1394.1, "IA": 634.0, "ID": 313.9, "IL": 474.3, "IN": 1465.5,
    "KS": 733.2, "KY": 1747.0, "LA": 790.5, "MA": 814.1, "MD": 522.1, "ME": 316.7, "MI": 792.1, "MN": 752.2,
    "MO": 1451.8, "MS": 828.3, "MT": 1063.9, "NC": 626.4, "ND": 1297.9, "NE": 1025.8, "NH": 276.2, "NJ": 468.9,
    "NM": 772.6, "NV": 642.7, "NY": 480.3, "OH": 1068.2, "OK": 648.3, "OR": 364.9, "PA": 645.6, "RI": 840.0,
    "SC": 556.6, "SD": 335.6, "TN": 656.5, "TX": 775.0, "UT": 1421.2, "VA": 533.5, "VT": 52.2, "WA": 266.6,
    "WI": 1165.1, "WV": 1968.3, "WY": 1833.3,
}
STATE_KG_PER_MWH = {k: v * LB_TO_KG for k, v in STATE_LB_PER_MWH.items()}

AREA = {"AL": 52420, "AK": 665384, "AZ": 113990, "AR": 53179, "CA": 163695, "CO": 104094, "CT": 5543,
        "DE": 2489, "DC": 68, "FL": 65758, "GA": 59425, "HI": 10932, "ID": 83569, "IL": 57914, "IN": 36420,
        "IA": 56273, "KS": 82278, "KY": 40408, "LA": 52378, "ME": 35380, "MD": 12406, "MA": 10554, "MI": 96714,
        "MN": 86936, "MS": 48432, "MO": 69707, "MT": 147040, "NE": 77348, "NV": 110572, "NH": 9349, "NJ": 8723,
        "NM": 121590, "NY": 54555, "NC": 53819, "ND": 70698, "OH": 44826, "OK": 69899, "OR": 98379, "PA": 46054,
        "RI": 1545, "SC": 32020, "SD": 77116, "TN": 42144, "TX": 268596, "UT": 84897, "VT": 9616, "VA": 42775,
        "WA": 71298, "WV": 24230, "WI": 65496, "WY": 97813}

CFS_TO_MGD, MI = 0.646317, 1609.344
GREEN, AMBER, RED, UNKNOWN = "GREEN", "AMBER", "RED", "UNKNOWN"

# ----------------------------------------------------------------------------- THE INPUT BLOCK
# >>> YOU ONLY EDIT THIS PART <<<
USER_INPUT = dict(
    STATE="GA", LAT=33.7490, LON=-84.3880, RADIUS_MILES=25,    # where
    IT_MW=100.0,       # size of the data center: power used by the servers alone, in MW
                       # (or instead give  SERVERS=20000, SERVER_TYPE="standard"  or  "ai_gpu" )
)
# >>> everything below is handled for you (defaults; change later if you want) <<<
DEFAULTS = dict(
    SERVERS=None, SERVER_TYPE="standard", KW_PER_SERVER=None,   # used only if SERVERS is given: standard 0.4 kW / ai_gpu 10 kW each, or set KW_PER_SERVER
    PUE=1.4,                # facility MW / IT MW (cooling, losses)             ASSUMPTION
    LOAD_FACTOR=0.8,        # average share of full load over a year             ASSUMPTION
    WUE=1.8,                # liters of water per IT kWh (0 = air cooled)        commonly quoted average
    RENEWABLE_SHARE=0.0,    # 0-1 contracted clean power (market-based carbon)
    GEN_HOURS=50,           # backup-generator hours per year                    ASSUMPTION
    SUBREGION=None,         # None = state grid factor; or an eGRID subregion code e.g. "SRSO"
    HOUSE_DIST_M=400,       # nearest house, metres                              ASSUMPTION (measure on the map)
    AMBIENT_DB=40.0,        # background noise at that house BEFORE the data center, dB(A)   ASSUMPTION (rural night ~30-40, suburban ~40-50, urban 50+; measure it)
    BARRIER_DB=0.0,         # wall / berm benefit, dB
    LIMIT_DAY=55.0, LIMIT_NIGHT=45.0,   # noise limits dB(A): EPA guidance, NOT your local law
    MONTHS=24, LOSS_PCT=5.0, DAYS=365, MAX_SITES=8, TAKE_PCT=5.0,
)
CFG = dict(DEFAULTS, **USER_INPUT)
SOURCES_URL = dict(
    eia="https://api.eia.gov/v2/ (electricity/electric-power-operational-data, electricity/retail-sales)",
    usgs="https://api.waterdata.usgs.gov/ogcapi/v1 (via python package dataretrieval.waterdata)",
    egrid="https://www.epa.gov/system/files/documents/2025-01/egrid2023_summary_tables_rev1.pdf",
    diesel="https://www.epa.gov/system/files/documents/2022-04/ghg_emission_factors_hub.pdf",
    noise="EPA 1974 noise 'Levels' document (55 dB outdoor / Ldn 55), as summarized at engineeringtoolbox.com/amp/epa-protective-noise-level-d_720.html",
)


SERVER_TYPES = {"standard": 0.4, "ai_gpu": 10.0}     # kW per server. ASSUMPTION: typical order of magnitude (a normal 2-socket server is a few hundred W; an 8-GPU AI server is ~10 kW). Check vendor specs.
OUTPUT = dict(SHOW_PROOF=False, SHOW_AI_BRIEF=True)   # SHOW_PROOF=True also prints the detailed proof report


def normalize(cfg) -> dict:
    """If SERVERS is given, IT_MW = SERVERS x kW-per-server / 1000. Records how the size was obtained."""
    cfg = dict(cfg)
    if cfg.get("SERVERS"):
        kw = cfg.get("KW_PER_SERVER") or SERVER_TYPES.get(cfg.get("SERVER_TYPE") or "standard")
        if not kw:
            raise ValueError(f"unknown SERVER_TYPE {cfg.get('SERVER_TYPE')!r}; use {sorted(SERVER_TYPES)} or set KW_PER_SERVER")
        cfg["IT_MW"] = cfg["SERVERS"] * kw / 1000.0
        cfg["size_note"] = f"{cfg['SERVERS']:,} servers x {kw:g} kW = {cfg['IT_MW']:.2f} MW (kW per server is an ASSUMPTION)"
    else:
        cfg["size_note"] = f"IT_MW given directly = {cfg['IT_MW']:g} MW"
    return cfg


def get_key(name: str) -> str:
    """Key from the environment, else ask once (Colab). Never written in the code."""
    v = os.environ.get(name, "")
    if v:
        return v
    try:
        from getpass import getpass
        return getpass(f"{name} (Enter = skip): ").strip()
    except Exception:                                        # noqa: BLE001
        return ""


def facility(cfg) -> dict:
    """The link between all modules: ONE set of derived numbers every layer uses."""
    peak = cfg["IT_MW"] * cfg["PUE"]
    avg = peak * cfg["LOAD_FACTOR"]
    return dict(fac_peak_mw=peak, fac_avg_mw=avg, annual_mwh=avg * HOURS_YEAR,
                gen_mw=peak,                                   # ASSUMPTION: backup sized for the full facility
                water_need_mgd=cfg["IT_MW"] * 1000.0 * cfg["WUE"] * 24.0 / 3.785411784 / 1e6)


# ----------------------------------------------------------------------------- POWER (EIA)
def eia_get(route, params, key):
    import requests
    rows, offset = [], 0
    while True:
        q = dict(params, api_key=key, offset=offset, length=5000)
        r = requests.get(f"https://api.eia.gov/v2/{route}", params=q, timeout=60)
        r.raise_for_status()
        body = r.json().get("response", {})
        data = body.get("data", [])
        rows += data
        offset += 5000
        if not data or offset >= int(body.get("total", len(rows))):
            break
    return rows


def to_series(rows, field, total_code, value_key):
    """month -> value. Use the 'ALL' row if present, else sum (and warn)."""
    from collections import defaultdict
    tot = [r for r in rows if r.get(field) == total_code]
    if tot:
        rows = tot
    elif rows and len({r.get(field) for r in rows}) > 1:
        print(f"WARNING: no '{total_code}' row for {field}; categories were summed - check double counting.")
    out = defaultdict(float)
    for r in rows:
        try:
            out[r["period"]] += float(r[value_key])
        except (KeyError, TypeError, ValueError):
            pass
    return dict(out)


def fetch_power(cfg, key, getter=eia_get):
    """Monthly generation - sales for the state (and the radius share). Returns a DataFrame (kW = average power)."""
    state = cfg["STATE"].upper()
    start = (date.today() - timedelta(days=31 * (cfg["MONTHS"] + 3))).strftime("%Y-%m")
    gp = {"frequency": "monthly", "data[]": ["generation"], "facets[location][]": [state], "facets[sectorid][]": ["99"],
          "facets[fueltypeid][]": ["ALL"], "start": start, "sort[0][column]": "period", "sort[0][direction]": "asc"}
    route = "electricity/electric-power-operational-data/data"
    rows = getter(route, gp, key)
    if not rows:
        gp.pop("facets[fueltypeid][]")
        rows = getter(route, gp, key)
    gen = to_series(rows, "fueltypeid", "ALL", "generation")                       # GWh
    sp = {"frequency": "monthly", "data[]": ["sales"], "facets[stateid][]": [state], "facets[sectorid][]": ["ALL"],
          "start": start, "sort[0][column]": "period", "sort[0][direction]": "asc"}
    sales = to_series(getter("electricity/retail-sales/data", sp, key), "sectorid", "ALL", "sales")   # GWh
    if not gen or not sales:
        raise RuntimeError(f"EIA returned no data (generation={len(gen)}, sales={len(sales)})")
    share = min(1.0, math.pi * cfg["RADIUS_MILES"] ** 2 / AREA[state]) if cfg.get("RADIUS_MILES") else 1.0
    out = []
    for p in sorted(set(gen) & set(sales)):
        y, m = map(int, p.split("-"))
        hours = calendar.monthrange(y, m)[1] * 24
        demand = sales[p] / (1 - cfg["LOSS_PCT"] / 100.0)
        surplus = gen[p] - demand
        kw = surplus * 1_000_000 / hours
        out.append(dict(month=p, gen_GWh=gen[p], sales_GWh=sales[p], demand_GWh=demand, surplus_GWh=surplus,
                        state_avg_kW=kw, area_avg_kW=kw * share))
    df = pd.DataFrame(out).tail(cfg["MONTHS"]).reset_index(drop=True)
    df.attrs["share"] = share
    df.attrs["evidence"] = dict(source=SOURCES_URL["eia"], state=state, generation_rows=len(rows), generation_months=len(gen),
                                sales_months=len(sales), first=df["month"].iloc[0], last=df["month"].iloc[-1],
                                area_sqmi=AREA[state], loss_pct=cfg["LOSS_PCT"],
                                fetched_at=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"))
    return df


def power_layer(df, fac):
    worst = df.loc[df["area_avg_kW"].idxmin()]
    need_kw = fac["fac_avg_mw"] * 1000.0
    ratio = worst["area_avg_kW"] / need_kw if need_kw > 0 else float("inf")
    status = RED if ratio < 1 else AMBER if ratio < 2 else GREEN
    hours = calendar.monthrange(*map(int, str(worst["month"]).split("-")))[1] * 24 if "gen_GWh" in df else None
    sales12 = float(df.tail(12)["sales_GWh"].sum()) if "sales_GWh" in df else None
    gen12 = float(df.tail(12)["gen_GWh"].sum()) if "gen_GWh" in df else None
    return dict(status=status, state_sales_12m_gwh=sales12, state_gen_12m_gwh=gen12, worst_row=worst.to_dict(), hours=hours, evidence=df.attrs.get("evidence", {}),
                last12_kw=float(df.tail(12)["area_avg_kW"].mean()), worst_month=worst["month"],
                worst_kw=float(worst["area_avg_kW"]), need_kw=need_kw, ratio=float(ratio),
                share=df.attrs.get("share", 1.0), table=df,
                note="energy-based; PEAK capacity and connection must be confirmed with the utility")


# ----------------------------------------------------------------------------- WATER (USGS dataretrieval)
def miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def gauge_coordinates(geometry):
    """Return (latitude, longitude) from the USGS GeoJSON or GeoPandas point."""
    if hasattr(geometry, "x") and hasattr(geometry, "y"):
        return float(geometry.y), float(geometry.x)
    if isinstance(geometry, (list, tuple)) and len(geometry) >= 2:
        return float(geometry[1]), float(geometry[0])
    return float("nan"), float("nan")


def fetch_river(cfg, key):
    """Active discharge gauges in the radius -> one row per gauge (MGD). Needs `pip install dataretrieval`."""
    import datetime as dt
    if key:
        os.environ["API_USGS_PAT"] = key
    from dataretrieval import waterdata
    lat, lon, rad = cfg["LAT"], cfg["LON"], cfg["RADIUS_MILES"]
    dlat = rad * MI / 111_320
    dlon = dlat / max(math.cos(math.radians(lat)), 0.01)
    ts, _ = waterdata.get_time_series_metadata(bbox=[lon - dlon, lat - dlat, lon + dlon, lat + dlat],
                                               parameter_code="00060", statistic_id="00003")
    ts_all = ts
    ts = ts.copy()
    ts["end"] = pd.to_datetime(ts["end"], utc=True, errors="coerce")
    ts = ts[ts["end"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=60)].drop_duplicates("monitoring_location_id")
    if "geometry" in ts and ts["geometry"].map(lambda g: g is not None).any():
        coordinates = [gauge_coordinates(g) for g in ts["geometry"]]
        ts["gauge_lat"] = [point[0] for point in coordinates]
        ts["gauge_lng"] = [point[1] for point in coordinates]
        ts["miles"] = [miles(lat, lon, y, x) if np.isfinite(y) and np.isfinite(x) else np.nan
                       for y, x in coordinates]
        ts = ts[ts["miles"] <= rad]
    else:
        ts["miles"] = np.nan
        ts["gauge_lat"] = np.nan
        ts["gauge_lng"] = np.nan
    if ts.empty:
        raise RuntimeError("no active discharge gauges inside the radius (try a bigger radius)")
    loc, _ = waterdata.get_monitoring_locations(monitoring_location_id=list(ts["monitoring_location_id"]), skip_geometry=True)
    if "monitoring_location_id" not in loc:
        loc = loc.rename(columns={"id": "monitoring_location_id"})
    loc = loc.copy()
    loc["drainage_area"] = pd.to_numeric(loc.get("drainage_area"), errors="coerce")
    sites = ts[["monitoring_location_id", "miles", "gauge_lat", "gauge_lng"]].merge(
        loc[["monitoring_location_id", "monitoring_location_name", "drainage_area"]], on="monitoring_location_id", how="left")
    sites = sites.sort_values(["drainage_area", "miles"], ascending=[False, True]).head(cfg["MAX_SITES"])
    end = dt.date.today()
    daily, _ = waterdata.get_daily(monitoring_location_id=list(sites["monitoring_location_id"]), parameter_code="00060",
                                   statistic_id="00003", time=f"{end - dt.timedelta(days=cfg['DAYS'])}/{end}")
    daily = daily.copy()
    daily["time"] = pd.to_datetime(daily["time"])
    daily["cfs"] = pd.to_numeric(daily["value"], errors="coerce")
    daily = daily.dropna(subset=["cfs"])
    daily = daily[daily["cfs"] >= 0]
    rows = []
    for sid, g in daily.sort_values("time").groupby("monitoring_location_id"):
        if len(g) < 30:
            continue
        s = g.set_index("time")["cfs"]
        meta = sites[sites["monitoring_location_id"] == sid].iloc[0]
        rows.append(dict(site=sid, name=str(meta["monitoring_location_name"])[:34], miles=meta["miles"],
                         lat=meta["gauge_lat"], lng=meta["gauge_lng"],
                         area_sqmi=meta["drainage_area"], days=len(s), latest=s.iloc[-1] * CFS_TO_MGD,
                         median=s.median() * CFS_TO_MGD, p10=s.quantile(.10) * CFS_TO_MGD,
                         week_low=s.rolling("7D").mean().min() * CFS_TO_MGD))
    if not rows:
        raise RuntimeError("gauges found, but none had >= 30 days of discharge data")
    out = pd.DataFrame(rows)
    out.attrs["evidence"] = dict(source=SOURCES_URL["usgs"], series_in_box=int(len(ts_all)), active_in_radius=int(len(ts)),
                                 analysed=list(out["site"]), history_days=cfg["DAYS"],
                                 first=str(daily["time"].min().date()), last=str(daily["time"].max().date()),
                                 fetched_at=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"))
    return out


def water_layer(res, fac, take_pct):
    """Honest: compares the DC need with an ASSUMED share of the dry-period flow of the LARGEST river (by drainage area)."""
    key = "area_sqmi" if res["area_sqmi"].notna().any() else "median"
    big = res.loc[res[key].idxmax()]
    need = fac["water_need_mgd"]
    allowed = float(big["p10"]) * take_pct / 100.0
    ratio = (need / allowed) if allowed > 0 else float("inf")
    if need == 0:
        status = GREEN
    else:
        status = GREEN if ratio <= 1 else AMBER if ratio <= 5 else RED
    return dict(status=status, big_row=big.to_dict(), chosen_by=key, evidence=res.attrs.get("evidence", {}),
                river=big["name"] or big["site"], median_mgd=float(big["median"]), p10_mgd=float(big["p10"]),
                need_mgd=need, assumed_take_mgd=allowed, take_pct=take_pct, ratio=float(ratio), table=res,
                note="river flow is NOT a water right; AMBER/RED means use municipal/reclaimed water or air cooling")


# ----------------------------------------------------------------------------- CARBON + NOISE (from the connected numbers)
def carbon_layer(cfg, fac):
    state = cfg["STATE"].upper()
    if cfg.get("SUBREGION"):
        f, src = grid_factor(cfg["SUBREGION"]), f"eGRID subregion {cfg['SUBREGION'].upper()}"
    elif state in STATE_KG_PER_MWH:
        f, src = STATE_KG_PER_MWH[state], f"eGRID state {state}"
    else:
        f, src = grid_factor("US"), "US average"
    c = carbon(cfg["IT_MW"], cfg["PUE"], cfg["LOAD_FACTOR"], f, "US", cfg["RENEWABLE_SHARE"],
               fac["gen_mw"], cfg["GEN_HOURS"])
    rel = f / grid_factor("US")
    status = GREEN if rel <= 0.8 else AMBER if rel <= 1.25 else RED          # RELATIVE to the US-average grid, not a legal limit
    return dict(status=status, factor_src=src, rel_to_us=rel, **c,
                note="status compares the grid to the US average; it is not a legal limit")


def noise_layer(cfg, fac):
    d = cfg["HOUSE_DIST_M"]
    src = [NoiseSource("cooling fans / dry coolers", 85.0, 10.0, max(1, math.ceil(cfg["IT_MW"] / 5.0)), d),
           NoiseSource("backup generators", 80.0, 10.0, max(1, math.ceil(fac["gen_mw"] / 2.5)), d),
           NoiseSource("transformers", 70.0, 10.0, max(1, math.ceil(fac["fac_peak_mw"] / 75.0)), d)]
    cont = [src[0], src[2]]        # continuous sources (24 h): fans + transformers. Generators run only for tests/outages.
    n = noise_check(cont, cfg["LIMIT_DAY"], cfg["LIMIT_NIGHT"], 55.0, cfg["BARRIER_DB"])
    status = GREEN if (n["ok_day"] and n["ok_night"] and n["ok_ldn"]) else AMBER if n["ok_day"] else RED
    # distance at which the combined plant (all sources lumped at 10 m reference) meets the night limit
    lumped = db_sum([s.level_dba + 10 * math.log10(s.count) for s in cont])
    lines = []
    for x in src:
        one = attenuate(x.level_dba, x.ref_m, x.distance_m, cfg["BARRIER_DB"])
        lines.append(dict(name=x.name, continuous=(x in cont), count=x.count, level_ref=x.level_dba, ref_m=x.ref_m, dist=x.distance_m,
                          one_unit=one, group=one + 10 * math.log10(x.count)))
    n.update(status=status, sources=src, lines=lines, gen_level_dba=lines[1]['group'], safe_distance_night_m=distance_for_limit(lumped, 10.0, cfg["LIMIT_NIGHT"], cfg["BARRIER_DB"]),
             note="source levels and unit counts are ASSUMPTIONS (fans MW/5, gens MW/2.5, transformers MW/75); status uses CONTINUOUS sources only")
    return n


# ----------------------------------------------------------------------------- RUNNER
def safe(name, fn):
    """A failing layer is reported as UNKNOWN with the reason; the others still run."""
    try:
        return fn()
    except Exception as ex:                                  # noqa: BLE001
        return dict(status=UNKNOWN, error=f"{type(ex).__name__}: {str(ex)[:160]}")


def run(cfg=None, eia_key=None, usgs_key=None, power_fetch=None, river_fetch=None):
    """power_fetch / river_fetch can be replaced (used by the tests and by anyone with their own data)."""
    given = set(cfg) if cfg is not None else set(USER_INPUT)
    cfg = normalize(dict(CFG, **(cfg or {})))
    if cfg["STATE"].upper() not in AREA:
        raise ValueError(f"unknown state {cfg['STATE']!r} (use the 2-letter code)")
    fac = facility(cfg)
    out = dict(cfg=cfg, facility=fac, given=given)
    out["power"] = safe("power", lambda: power_layer(
        (power_fetch or (lambda c: fetch_power(c, eia_key or get_key("EIA_API_KEY"))))(cfg), fac))
    out["water"] = safe("water", lambda: water_layer(
        (river_fetch or (lambda c: fetch_river(c, usgs_key if usgs_key is not None else get_key("API_USGS_PAT"))))(cfg),
        fac, cfg["TAKE_PCT"]))
    out["carbon"] = safe("carbon", lambda: carbon_layer(cfg, fac))
    out["noise"] = safe("noise", lambda: noise_layer(cfg, fac))
    st = {k: out[k]["status"] for k in ("power", "water", "carbon", "noise")}
    known = [v for v in st.values() if v != UNKNOWN]
    out["statuses"] = st
    out["overall"] = RED if RED in known else AMBER if AMBER in known else GREEN if known else UNKNOWN
    out["unchecked"] = [k for k, v in st.items() if v == UNKNOWN]
    return out


def print_report(o):
    """Detailed report WITH PROOF, printed to the terminal only (nothing is saved)."""
    c, f, given = o["cfg"], o["facility"], o.get("given", set())
    W = 90
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC")

    def H(t): print("\n" + "=" * W + f"\n{t}\n" + "=" * W)
    def S(t): print(f"\n--- {t} " + "-" * max(3, W - len(t) - 5))

    p, w, k, n = o["power"], o["water"], o["carbon"], o["noise"]
    H(f"DATA CENTER SITE SCREENING REPORT   (generated {now}; nothing saved to disk)")
    print("TAGS:  [LIVE] fetched from the API during this run   [TABLE] fixed published number inside the code (source shown)")
    print("       [ASSUMPTION] my assumption, not a standard    [CALC] arithmetic, shown step by step so you can re-check it")

    # ---------------- 1. verdict
    S("1. VERDICT")
    why = {
        "power": (f"surplus/need = {p['ratio']:.2f}  (GREEN >= 2, AMBER 1-2, RED < 1)" if p["status"] != UNKNOWN else p["error"]),
        "water": (f"need/allowed = {w['ratio']:.2f}  (GREEN <= 1, AMBER 1-5, RED > 5)" if w["status"] != UNKNOWN else w["error"]),
        "carbon": (f"grid is {k['rel_to_us']:.2f} x US average  (GREEN <= 0.8, AMBER <= 1.25, RED above)" if k["status"] != UNKNOWN else k["error"]),
        "noise": (f"{n['level_dba']:.1f} dB(A) at {c['HOUSE_DIST_M']:g} m; day {'OK' if n['ok_day'] else 'FAIL'}, night {'OK' if n['ok_night'] else 'FAIL'}, "
                  f"Ldn {'OK' if n['ok_ldn'] else 'FAIL'}" if n["status"] != UNKNOWN else n["error"]),
    }
    for key in ("power", "water", "carbon", "noise"):
        print(f"  {key.upper():<7}{o[key]['status']:<9}{why[key]}")
    print(f"  OVERALL {o['overall']}   (worst of the checked layers)" + (f"   NOT CHECKED: {', '.join(o['unchecked'])}" if o["unchecked"] else ""))
    print("  GREEN/AMBER/RED limits are MY thresholds for screening, not laws or standards.")

    # ---------------- 2. inputs
    S("2. INPUTS  (GIVEN = you typed it, DEFAULT = I filled it in)")
    rows = [("STATE", c["STATE"]), ("LAT, LON", f"{c['LAT']}, {c['LON']}"), ("RADIUS_MILES", c["RADIUS_MILES"]), ("IT_MW", f"{c['IT_MW']:g}"),
            ("PUE", c["PUE"]), ("LOAD_FACTOR", c["LOAD_FACTOR"]), ("WUE (L/kWh)", c["WUE"]), ("RENEWABLE_SHARE", c["RENEWABLE_SHARE"]),
            ("GEN_HOURS", c["GEN_HOURS"]), ("HOUSE_DIST_M", c["HOUSE_DIST_M"]), ("BARRIER_DB", c["BARRIER_DB"]),
            ("LIMIT_DAY / NIGHT", f"{c['LIMIT_DAY']:g} / {c['LIMIT_NIGHT']:g} dB(A)"), ("MONTHS / LOSS_PCT", f"{c['MONTHS']} / {c['LOSS_PCT']}%"),
            ("DAYS / MAX_SITES", f"{c['DAYS']} / {c['MAX_SITES']}"), ("TAKE_PCT", f"{c['TAKE_PCT']}%")]
    keymap = {"LAT, LON": "LAT", "LIMIT_DAY / NIGHT": "LIMIT_DAY", "MONTHS / LOSS_PCT": "MONTHS", "DAYS / MAX_SITES": "DAYS",
              "WUE (L/kWh)": "WUE"}
    for name, val in rows:
        tag = "GIVEN" if keymap.get(name, name) in given else "DEFAULT"
        print(f"  {name:<20}{str(val):<22}{tag}")
    print(f"  size: {c['size_note']}")
    print("  Every DEFAULT above that is not 'commonly quoted' is an [ASSUMPTION]: PUE, LOAD_FACTOR, GEN_HOURS, HOUSE_DIST_M, TAKE_PCT, KW_PER_SERVER.")

    # ---------------- 3. shared numbers
    S("3. SHARED NUMBERS  [CALC]  (every layer below uses exactly these)")
    print(f"  peak facility power  = IT_MW x PUE            = {c['IT_MW']:g} x {c['PUE']:g} = {f['fac_peak_mw']:.1f} MW")
    print(f"  average power        = peak x LOAD_FACTOR     = {f['fac_peak_mw']:.1f} x {c['LOAD_FACTOR']:g} = {f['fac_avg_mw']:.1f} MW")
    print(f"  energy per year      = average x 8760 h       = {f['fac_avg_mw']:.1f} x 8760 = {f['annual_mwh']:,.0f} MWh")
    print(f"  water need (peak)    = IT_MW x 1000 x WUE x 24 / 3.785 / 1e6 = {c['IT_MW']:g} x 1000 x {c['WUE']:g} x 24 / 3.785 / 1e6 = {f['water_need_mgd']:.3f} MGD")
    print(f"  backup generator MW  = peak facility MW      = {f['gen_mw']:.1f} MW   [ASSUMPTION: backup sized for the whole facility]")

    # ---------------- 4. power
    S("4. POWER  -  is there spare electricity in the area?")
    if p["status"] == UNKNOWN:
        print("  NOT CHECKED:", p["error"])
    else:
        e, r = p["evidence"], p["worst_row"]
        print(f"  Source [LIVE]: {e.get('source', 'EIA')}")
        print(f"  Fetched {e.get('fetched_at', '?')} | state {e.get('state', c['STATE'])} | months used {e.get('first', '?')} .. {e.get('last', '?')} "
              f"(generation months {e.get('generation_months', '?')}, sales months {e.get('sales_months', '?')})")
        print(f"  Area share = pi x radius^2 / state area = pi x {c['RADIUS_MILES']}^2 / {e.get('area_sqmi', '?')} sq mi = {p['share']:.2%}   "
              f"[ASSUMPTION: surplus spread evenly over the state's area; area figure is a fixed table in the code]")
        print(f"  Loss assumption {c['LOSS_PCT']}% [ASSUMPTION]")
        print("\n  Worked example, weakest month " + str(p["worst_month"]) + "  [CALC]")
        if p["hours"]:
            dem = r["sales_GWh"] / (1 - c["LOSS_PCT"] / 100)
            print(f"    generation   {r['gen_GWh']:,.0f} GWh   (EIA, all fuels, all sectors)")
            print(f"    sales        {r['sales_GWh']:,.0f} GWh   (EIA retail sales)")
            print(f"    demand       = sales / (1 - loss) = {r['sales_GWh']:,.0f} / {1 - c['LOSS_PCT'] / 100:.2f} = {dem:,.0f} GWh")
            print(f"    surplus      = generation - demand = {r['gen_GWh']:,.0f} - {dem:,.0f} = {r['gen_GWh'] - dem:,.0f} GWh")
            print(f"    average kW   = surplus x 1,000,000 / {p['hours']} h = {r['state_avg_kW']:,.0f} kW (state) -> x share = {r['area_avg_kW']:,.0f} kW (area)")
        print("\n  Monthly table (GWh; kW = average power):")
        t = p["table"].copy()
        for col in t.columns:
            if col != "month":
                t[col] = t[col].round(0)
        print("    " + t.to_string(index=False).replace("\n", "\n    "))
        print(f"\n  RESULT: last-12-month average spare = {p['last12_kw']:,.0f} kW; weakest month = {p['worst_kw']:,.0f} kW")
        print(f"          your average need = {p['need_kw']:,.0f} kW  ->  weakest-month surplus / need = {p['ratio']:.2f}  => {p['status']}")
        print(f"  CAVEAT: {p['note']}. Retail sales exclude self-generation; imports/exports between states are ignored.")

    # ---------------- 5. water
    S("5. WATER  -  is there a river big enough nearby?")
    if w["status"] == UNKNOWN:
        print("  NOT CHECKED:", w["error"])
    else:
        e = w["evidence"]
        print(f"  Source [LIVE]: {e.get('source', 'USGS')}")
        print(f"  Fetched {e.get('fetched_at', '?')} | discharge series in the search box: {e.get('series_in_box', '?')} | still reporting & inside "
              f"{c['RADIUS_MILES']} mi: {e.get('active_in_radius', '?')} | analysed: {len(w['table'])}")
        print(f"  Daily data {e.get('first', '?')} .. {e.get('last', '?')}  (parameter 00060 discharge, statistic 00003 daily mean; cfs x 0.646317 = MGD)")
        print("\n  Gauges (MGD):  median = typical, p10 = dry-period (flow is below this on 10% of days), week_low = driest 7-day average")
        print("    " + w["table"].round(1).to_string(index=False).replace("\n", "\n    "))
        b = w["big_row"]
        print(f"\n  Largest river chosen by {w['chosen_by']} : {w['river']}  (site {b.get('site', '?')})  [rows are NOT added: gauges on one river repeat the same water]")
        print(f"  Need   = {w['need_mgd']:.3f} MGD [CALC, section 3]")
        print(f"  Allowed (ASSUMPTION) = p10 x TAKE_PCT = {w['p10_mgd']:.1f} x {w['take_pct']:g}% = {w['assumed_take_mgd']:.3f} MGD")
        print(f"  RESULT: need / allowed = {w['ratio']:.2f} => {w['status']}")
        print(f"  CAVEAT: {w['note']}. Groundwater, water rights, municipal capacity and reservoirs are NOT in this number.")

    # ---------------- 6. carbon
    S("6. CARBON  -  metric tons CO2e per year")
    if k["status"] == UNKNOWN:
        print("  NOT CHECKED:", k["error"])
    else:
        print(f"  Grid factor [TABLE]: {k['factor_src']} = {k['factor_kg_mwh']:.1f} kg CO2e/MWh   ({k['rel_to_us']:.2f} x the US average of {grid_factor('US'):.1f})")
        print(f"     source: {SOURCES_URL['egrid']}  (lb/MWh x 0.45359 = kg/MWh; state numbers were read from the PDF text - spot-check them)")
        print(f"  Scope 2 (electricity) [CALC] = {f['annual_mwh']:,.0f} MWh x {k['factor_kg_mwh']:.1f} kg / 1000 = {k['scope2_location_t']:,.0f} t")
        print(f"     market-based with {c['RENEWABLE_SHARE']:.0%} clean power = {k['scope2_market_t']:,.0f} t")
        print(f"  Scope 1 (diesel) [CALC] = {f['gen_mw']:.1f} MW x {c['GEN_HOURS']} h x 1000 kWh/MWh x 0.07 gal/kWh = {k['diesel_gal']:,.0f} gal;  "
              f"x {DIESEL_CO2E_KG_GAL:.3f} kg CO2e/gal / 1000 = {k['scope1_t']:,.0f} t")
        print(f"     diesel factor [TABLE]: 10.21 kg CO2/gal + CH4/N2O (GWP 28/265, IPCC AR5)  source: {SOURCES_URL['diesel']} (Apr 2022 edition)")
        print(f"     0.07 gal/kWh generator fuel use and {c['GEN_HOURS']} h/yr are [ASSUMPTION]")
        print(f"  TOTAL (location-based) = {k['scope2_location_t']:,.0f} + {k['scope1_t']:,.0f} = {k['total_location_t']:,.0f} tCO2e/yr")
        print(f"  Intensity: {k['kg_per_mwh_it']:.0f} kg per IT-MWh, {k['t_per_it_mw']:,.0f} t per IT-MW  => {k['status']} ({k['note']})")

    # ---------------- 7. noise
    S("7. NOISE  -  dB(A) at the nearest house")
    if n["status"] == UNKNOWN:
        print("  NOT CHECKED:", n["error"])
    else:
        print("  Rule [physics]: a point source loses 20 x log10(distance / reference distance) dB (~6 dB per doubling). Sources add as 10 x log10(sum 10^(L/10)).")
        print("  Source levels and unit counts are [ASSUMPTION] (fans: IT_MW/5, generators: MW/2.5, transformers: MW/75; 75-95 dB(A) 'close range' is a press-article range).")
        print(f"  {'source':<28}{'mode':<13}{'units':>6}{'dB@ref':>8}{'ref m':>7}{'to house m':>11}{'one unit':>10}{'all units':>10}")
        for x in n["lines"]:
            print(f"  {x['name']:<28}{('continuous' if x['continuous'] else 'tests/outage'):<13}{x['count']:>6}{x['level_ref']:>8.0f}{x['ref_m']:>7.0f}"
                  f"{x['dist']:>11.0f}{x['one_unit']:>10.1f}{x['group']:>10.1f}")
        print(f"  barrier benefit: {c['BARRIER_DB']:g} dB (already inside 'one unit')")
        print(f"  Combined CONTINUOUS noise at the house [CALC] = {n['level_dba']:.1f} dB(A).  Ldn (24 h noise) = L + 6.4 = {n['ldn_db']:.1f}")
        print(f"  Generators are NOT in that number (they run ~{c['GEN_HOURS']} h/yr). While they run, all {o['facility']['gen_mw']:.0f} MW together: "
              f"about {n['gen_level_dba']:.1f} dB(A) at the house, and the continuous plant adds to it.")
        print(f"  Limits: day {c['LIMIT_DAY']:g}, night {c['LIMIT_NIGHT']:g}, Ldn 55  [TABLE: EPA guidance - {SOURCES_URL['noise']}]")
        print(f"  Margins (limit - level): day {n['margin_day']:+.1f}, night {n['margin_night']:+.1f}, Ldn {n['margin_ldn']:+.1f}  => {n['status']}")
        print(f"  Distance at which the night limit is met: about {n['safe_distance_night_m']:,.0f} m (with the barrier you entered)")
        print(f"  CAVEAT: {n['note']}. Your local ordinance may use other limits; permits need an acoustic study.")

    # ---------------- 8. open items
    S("8. NOT CHECKED / WHAT TO DO NEXT")
    print("  - Water rights and permits; groundwater; municipal supply capacity  -> ask the water utility / state water agency")
    print("  - Peak grid capacity, substation and interconnection queue            -> ask the electric utility for a will-serve / capacity letter")
    print("  - Local noise ordinance, zoning, flood risk, fiber, land price        -> county planning office (site finder covers some of this)")
    nA = sum(1 for _ in ("PUE", "LOAD_FACTOR", "GEN_HOURS", "HOUSE_DIST_M", "TAKE_PCT") if _ not in given)
    print(f"  - This report relies on {nA} unconfirmed ASSUMPTION defaults (PUE, LOAD_FACTOR, GEN_HOURS, HOUSE_DIST_M, TAKE_PCT) - replace them with project facts.")
    print("=" * W)


def summary_table(o) -> "pd.DataFrame":
    """One row per layer - easy to save as CSV or to append for many sites."""
    rows = []
    for k in ("power", "water", "carbon", "noise"):
        x = o[k]
        rows.append(dict(layer=k, status=x["status"], error=x.get("error", "")))
    return pd.DataFrame(rows)


# =============================================================================================
#  PART C  -  SIMPLE (human) REPORT, DECISION, FIXES, and a brief you can hand to an AI later
# =============================================================================================
import json

# Everyday comparisons (checked online): EPA typical passenger car 4.6 t CO2/yr (22.2 mpg, 11,500 mi);
# EIA average US home 10,791 kWh/yr (2022); EPA WaterSense: average family uses more than 300 gallons/day at home.
EQUIV = dict(car_t_co2_yr=4.6, home_kwh_yr=10791.0, home_gal_day=300.0)
LN10_NIGHT_LDN_OFFSET = 10 * math.log10((15 + 9 * 10) / 24.0)          # 6.41 dB: constant 24 h noise -> Ldn = L + 6.41
LAYERS = ("power", "water", "carbon", "noise")


def approx(x: float) -> str:
    """Human-friendly number: 1,234,567 -> '1,235,000'; 12.3456 -> '12'; 0.456 -> '0.5'."""
    x = float(x)
    if not math.isfinite(x):
        return "unlimited"
    a = abs(x)
    if a >= 100000: v = round(x, -3)
    elif a >= 10000: v = round(x, -2)
    elif a >= 1000: v = round(x, -1)
    elif a >= 10: v = round(x)
    elif a >= 1: v = round(x, 1)
    else: v = round(x, 2)
    return f"{v:,.0f}" if a >= 10 or float(v).is_integer() else f"{v:,}"


# ----------------------------------------------------------------------------- facts + decision (no language here)
def analyze(o) -> dict:
    """Plain numbers every sentence and the AI brief are built from. Nothing here is printed."""
    c, f = o["cfg"], o["facility"]
    A = dict(homes_power=f["annual_mwh"] * 1000.0 / EQUIV["home_kwh_yr"],
             water_gal_day=f["water_need_mgd"] * 1e6,
             water_avg_mgd=f["water_need_mgd"] * c["LOAD_FACTOR"],
             homes_water=f["water_need_mgd"] * 1e6 / EQUIV["home_gal_day"])
    p, w, k, n = o["power"], o["water"], o["carbon"], o["noise"]
    per_it_mw_avg_kw = c["PUE"] * c["LOAD_FACTOR"] * 1000.0            # average kW of facility per IT MW
    if p["status"] != UNKNOWN:
        A["state_pct"] = (f["annual_mwh"] / (p["state_sales_12m_gwh"] * 1000.0) * 100.0) if p.get("state_sales_12m_gwh") else None
        mx = max(0.0, p["worst_kw"]) / per_it_mw_avg_kw if per_it_mw_avg_kw > 0 else float("inf")
        A["max_it_mw_power"], A["max_it_mw_power_comfortable"] = mx, mx / 2.0
        A["surplus_mw"], A["need_mw"] = p["worst_kw"] / 1000.0, p["need_kw"] / 1000.0
    if w["status"] != UNKNOWN:
        need, allowed = w["need_mgd"], w["assumed_take_mgd"]
        A["water_pct_of_dry"] = (need / w["p10_mgd"] * 100.0) if w["p10_mgd"] > 0 else float("inf")
        A["wue_max"] = (allowed * 1e6 * 3.785411784 / (c["IT_MW"] * 1000.0 * 24.0)) if c["IT_MW"] > 0 else float("inf")
        A["max_it_mw_water"] = (c["IT_MW"] * allowed / need) if need > 0 else float("inf")
    if k["status"] != UNKNOWN:
        A["cars"] = k["total_location_t"] / EQUIV["car_t_co2_yr"]
        A["t_saved_per_10pct_clean"] = 0.1 * k["scope2_location_t"]
    if n["status"] != UNKNOWN:
        cont = [x for x in n["lines"] if x["continuous"]]
        lumped = db_sum([x["level_ref"] + 10 * math.log10(x["count"]) for x in cont])
        target = min(c["LIMIT_DAY"], c["LIMIT_NIGHT"], 55.0 - LN10_NIGHT_LDN_OFFSET)
        A["noise_target_db"] = target
        A["noise_cut_needed_db"] = max(0.0, n["level_dba"] - target)
        A["noise_safe_distance_m"] = distance_for_limit(lumped, 10.0, target, c["BARRIER_DB"])
    return A


def perceived_change(inc_db: float) -> str:
    """Everyday meaning of a noise increase (standard rules of thumb: ~3 dB barely heard, ~5 dB clearly noticeable, ~10 dB seems twice as loud)."""
    if inc_db < 1: return "no real change"
    if inc_db < 3: return "barely noticeable"
    if inc_db < 5: return "noticeable"
    if inc_db < 10: return "clearly noticeable"
    if inc_db < 20: return "about twice as loud (or more)"
    return "several times louder than before"


def comparison(o) -> dict:
    """Need vs have, and before vs after, for each resource. Numbers only (printed by print_comparison)."""
    c, f, A = o["cfg"], o["facility"], analyze(o)
    p, w, k, n = o["power"], o["water"], o["carbon"], o["noise"]
    R = {}
    if p["status"] != UNKNOWN:
        spare, need = p["worst_kw"] / 1000.0, p["need_kw"] / 1000.0
        R["power"] = dict(need_mw=need, spare_mw=spare, last12_spare_mw=p["last12_kw"] / 1000.0, gap_mw=spare - need,
                          spare_left_mw=spare - need, used_pct_of_spare=(need / spare * 100.0) if spare > 0 else float("inf"))
    if w["status"] != UNKNOWN:
        need, allowed = w["need_mgd"], w["assumed_take_mgd"]
        R["water"] = dict(need_mgd=need, dry_flow_mgd=w["p10_mgd"], median_flow_mgd=w["median_mgd"], allowed_mgd=allowed,
                          gap_mgd=allowed - need, take_pct=w["take_pct"], pct_of_dry=A["water_pct_of_dry"],
                          river_left_pct=max(0.0, 100.0 - A["water_pct_of_dry"]), river=w["river"])
    if n["status"] != UNKNOWN:
        amb = c["AMBIENT_DB"]
        after = db_sum([amb, n["level_dba"]])
        r_m = A["noise_safe_distance_m"]
        R["noise"] = dict(before_db=amb, plant_db=n["level_dba"], after_db=after, increase_db=after - amb, perceived=perceived_change(after - amb),
                          target_db=A["noise_target_db"], footprint_m=r_m, footprint_acres=math.pi * r_m ** 2 / 4046.856,
                          generator_db=n["gen_level_dba"])
    if k["status"] != UNKNOWN:
        st = None
        if p["status"] != UNKNOWN and p.get("state_gen_12m_gwh") and k["factor_src"].startswith("eGRID state"):
            st = p["state_gen_12m_gwh"] * k["factor_kg_mwh"]          # GWh x kg/MWh = metric tons
        R["carbon"] = dict(adds_t=k["total_location_t"], cars=A["cars"], state_power_t=st,
                           pct_of_state_power=(k["total_location_t"] / st * 100.0) if st else None,
                           grid_vs_us=k["rel_to_us"], diesel_t=k["scope1_t"], diesel_hours=c["GEN_HOURS"])
    return R


def decide(o) -> dict:
    st = o["statuses"]
    red = [k for k in LAYERS if st[k] == RED]
    amber = [k for k in LAYERS if st[k] == AMBER]
    unk = [k for k in LAYERS if st[k] == UNKNOWN]
    if red: code = "NOT_AS_PLANNED"
    elif unk: code = "INCOMPLETE"
    elif amber: code = "CONDITIONAL"
    else: code = "FAVOURABLE"
    return dict(code=code, red=red, amber=amber, unchecked=unk)


# ----------------------------------------------------------------------------- words
NOISE_SCALE = [  # (upper dB, description) - everyday reference points (approximate)
    (35, "very quiet, like a quiet bedroom"),
    (45, "quiet, like a library"),
    (55, "like a quiet office or light rain"),
    (65, "like normal conversation"),
    (75, "like busy road traffic or a vacuum cleaner"),
    (85, "very loud, like heavy traffic or a factory"),
    (999, "dangerously loud"),
]
WORD = {GREEN: "GREEN (fine)", AMBER: "AMBER (be careful)", RED: "RED (problem)", UNKNOWN: "NOT CHECKED"}
LAYER_NAME = dict(power="Electricity", water="Water", carbon="Carbon", noise="Noise")

TXT = {
 "en": dict(
  title="DATA CENTER SITE CHECK - SIMPLE REPORT",
  place="Place: {state} ({lat:.3f}, {lon:.3f}), searched within {radius:g} miles",
  size="Planned size: {it_mw:g} MW of servers   [{note}]",
  gen="(Made {now}. This is a quick screening, not a final decision.)",
  h_answer="THE ANSWER IN ONE LINE",
  v_FAVOURABLE="Looks FAVOURABLE on all four quick checks. Next: confirm with the electric utility, the water authority and the county.",
  v_CONDITIONAL="POSSIBLE, WITH CONDITIONS. Areas that need attention: {layers} (see 'what could fix the problems' below).",
  v_NOT_AS_PLANNED="NOT workable as planned. Problem areas: {layers}. See 'what could fix the problems' below.",
  v_INCOMPLETE="INCOMPLETE. Could not be checked: {unchecked}, so there is no decision yet.{extra}",
  v_extra=" Among the parts that were checked, these show an issue: {issues}.",
  h_needs="WHAT THIS DATA CENTER WILL NEED",
  n_power="Electricity: about {avg:,.0f} MW on average ({peak:,.0f} MW at peak) = {mwh} MWh a year\n              roughly the yearly use of {homes} American homes{statepct}",
  n_statepct=", i.e. about {pct:.1f}% of everything {state} uses today",
  n_water="Water      : up to {mgd:.2f} million gallons a day (MGD) on the busiest days = {gal} gallons = daily use of about {homes} homes\n              (on an average day about {avg:.2f} MGD)",
  n_water0="Water      : none (air-cooled assumed)",
  n_carbon="Carbon     : about {t} metric tons of CO2 a year, like {cars} cars driven for a year",
  n_noise="Noise      : about {db:.0f} dB at the nearest house ({dist:g} m / {ft:,.0f} ft away), {feel}",
  h_checks="DOES THE AREA HAVE WHAT IT NEEDS?  (4 checks)",
  c_power="In its weakest month the area makes about {s:,.0f} MW more electricity than it uses (monthly average). This data center needs {n:,.0f} MW on average, so the area has {r:.1f} times what is needed.",
  c_power_def="In its weakest month ({m}) the area uses MORE electricity than it makes (shortfall about {d:,.0f} MW), so there is no spare power.",
  c_power_note="(Only total energy was compared. The real connection capacity must be asked from the electric utility.)",
  c_water="Biggest nearby river: {river}. In dry periods about {p10:,.0f} MGD flows past. The data center needs {mgd:.2f} MGD = {pct:.2f}% of that. If only {take:g}% of the dry flow could be taken ({allowed:.2f} MGD), the need is {r:.2f} times that amount.",
  c_water0="The data center is assumed air-cooled (no water), so water is not a problem.",
  c_water_note="(Legal right to take river water is a separate question. Only the flow was looked at.)",
  c_carbon="Electricity {src} gives about {f:.0f} kg of CO2 per MWh, which is {rel:.2f} times the US average. Yearly total about {t} metric tons (of which diesel generators {s1} metric tons).",
  c_carbon_note="(The color only compares the local power grid with the US average. It is not a legal limit.)",
  c_noise="Noise from the always-running machines at the nearest house ({dist:g} m / {ft:,.0f} ft) is about {db:.0f} dB. Day limit {ld:g} dB: {dayok}. Night limit {ln:g} dB: {nightok}. While generators run (about {gh} hours a year) it can reach about {gen:.0f} dB.",
  c_noise_note="(Machine noise levels are my estimates. Your local rules may differ.)",
  ok="pass", fail="fail",
  c_unknown="Could not be checked: {error}",
  h_fix="WHAT COULD FIX THE PROBLEMS",
  f_none="Nothing needs fixing right now (no AMBER or RED).",
  f_power="Electricity: this area's weakest-month surplus supports at most about {mw} MW of servers (about {mwc} MW to be comfortable). For a bigger centre choose another area or ask the utility for a dedicated supply.",
  f_water="Water: the river can supply only a data center using about {wue:.2f} liters of water per kWh at this size, or a data center of about {mw} MW at {cur:g} L/kWh. Otherwise use treated city/reclaimed water, or air cooling (which needs more electricity).",
  f_carbon="Carbon: every 10% of clean power you buy removes about {t} metric tons of CO2 a year. A cleaner grid area also helps.",
  f_noise="Noise: you need about {cut:.0f} dB less at the house (sound wall or earth berm, quieter fans), or put the machines about {dist} m ({ft} ft) away from the nearest house.",
  h_trust="HOW MUCH TO TRUST THIS",
  t_real="Real data used: {list}",
  t_real_power="electricity from EIA ({first} to {last})",
  t_real_water="river flow from USGS ({n} gauges)",
  t_real_carbon="grid emissions from EPA eGRID 2023 table",
  t_real_none="none (all four parts failed)",
  t_guess="Guesses I filled in because you did not give them: {list}",
  t_guess_none="You gave every input yourself.",
  t_machines="Always a guess: how loud the machines are and how many there are (fans, generators, transformers).",
  g_PUE="cooling needs {pct:.0f}% extra electricity (PUE {v:g})",
  g_LOAD_FACTOR="servers run at {v:.0%} of full power on average",
  g_WUE="{v:g} liters of water per kWh",
  g_GEN_HOURS="generators run {v} hours a year",
  g_HOUSE_DIST_M="nearest house {v:g} m away",
  g_AMBIENT_DB="background noise there today is {v:g} dB",
  g_TAKE_PCT="{v:g}% of the river's dry flow can be taken",
  g_LOSS_PCT="{v:g}% electricity lost in the wires",
  g_LIMIT_DAY="noise limits day {d:g} / night {n:g} dB (EPA guidance, not your local law)",
  g_RENEWABLE_SHARE="{v:.0%} clean power",
  g_BARRIER_DB="{v:g} dB sound barrier",
  h_not="NOT CHECKED AT ALL",
  not_list=["Water rights and permits, groundwater, city water capacity - ask the water utility / state water agency.",
            "Peak grid capacity, substation and waiting queue - ask the electric utility for a capacity (will-serve) letter.",
            "Local noise law, zoning, flood risk, fiber, land price - ask the county planning office."],
  h_words="WORDS USED",
  words="MW = power (1 MW is about the average use of 800 US homes). MWh = energy. MGD = million gallons per day. dB = loudness (+10 dB sounds about twice as loud).",
  equiv="Comparisons: EPA typical car 4.6 t CO2/year; EIA average US home 10,791 kWh/year (2022); EPA: family uses over 300 gallons/day.",
  nodata="(no data)",
 ),
}


def _feel(db):
    for top, text in NOISE_SCALE:
        if db <= top:
            return text
    return ""


def _src_name(label):
    """'eGRID state GA' -> friendly phrase for the sentence."""
    if label.startswith("eGRID state "):
        return f"in the {label.split()[-1]} state grid"
    if label.startswith("eGRID subregion "):
        return f"in grid region {label.split()[-1]}"
    return "on the US-average grid"


def _layers_text(keys):
    return ", ".join(LAYER_NAME[k] for k in keys)


def print_comparison(o):
    """Need-vs-have table, then a before-vs-after block, then the environmental indicators we can really compute."""
    R, c, W = comparison(o), o["cfg"], 92
    print("\nCOMPARISON: WHAT THE DATA CENTER NEEDS vs WHAT THE AREA HAS\n" + "-" * 60)
    def row(a, b="", c_="", d="", e=""): print(f"{a:<13}{b:<28}{c_:<46}{d:<12}{e}")
    row("Resource", "Data center needs", "Area has", "Gap", "Result")
    if "power" in R:
        x = R["power"]
        row("Electricity", f"{x['need_mw']:,.0f} MW average", f"{x['spare_mw']:,.0f} MW spare (weakest month)", f"{x['gap_mw']:+,.0f} MW", o["statuses"]["power"])
    else: row("Electricity", "not checked")
    if "water" in R:
        x = R["water"]
        row("Water", f"{x['need_mgd']:.2f} MGD (busiest day)", f"{x['allowed_mgd']:.1f} MGD usable ({x['take_pct']:g}% of dry flow)", f"{x['gap_mgd']:+.1f} MGD", o["statuses"]["water"])
        row("", "", f"(river {x['river']}: {x['dry_flow_mgd']:,.0f} MGD flows in dry periods)")
    else: row("Water", "not checked")
    if "noise" in R:
        x = R["noise"]
        row("Noise", f"{x['plant_db']:.0f} dB at the house", f"night limit {c['LIMIT_NIGHT']:g} dB", f"{c['LIMIT_NIGHT'] - x['plant_db']:+.0f} dB", o["statuses"]["noise"])
    else: row("Noise", "not checked")
    if "carbon" in R:
        x = R["carbon"]
        row("Carbon", f"{approx(x['adds_t'])} t CO2 per year", "no 'available amount': it adds to the air", "", o["statuses"]["carbon"])
    else: row("Carbon", "not checked")

    print("\nBEFORE vs AFTER THE DATA CENTER")
    print("-" * 60)
    if "power" in R:
        x = R["power"]
        left = f"{x['spare_left_mw']:,.0f} MW left" if x["spare_left_mw"] >= 0 else f"short by {-x['spare_left_mw']:,.0f} MW"
        used = f"uses {x['used_pct_of_spare']:.1f}% of the spare power" if math.isfinite(x["used_pct_of_spare"]) else "there is no spare power"
        print(f" Electricity : area spare {x['spare_mw']:,.0f} MW  ->  after: {left}  ({used})")
    if "water" in R:
        x = R["water"]
        print(f" Water       : dry-period river flow {x['dry_flow_mgd']:,.0f} MGD  ->  data center takes {x['pct_of_dry']:.2f}% of it; the river keeps {x['river_left_pct']:.2f}%")
    if "noise" in R:
        x = R["noise"]
        print(f" Noise       : background at the house {x['before_db']:g} dB  ->  after: {x['after_db']:.0f} dB  (+{x['increase_db']:.0f} dB, {x['perceived']})")
        print(f"               noise stays above {x['target_db']:.0f} dB out to about {x['footprint_m']:,.0f} m ({x['footprint_m'] * 3.28084:,.0f} ft) from the machines "
              f"= an area of about {x['footprint_acres']:,.0f} acres; generators add up to {x['generator_db']:.0f} dB while they run")
    if "carbon" in R:
        x = R["carbon"]
        if x["state_power_t"]:
            print(f" Carbon      : {c['STATE']} power plants emit about {approx(x['state_power_t'])} t CO2/yr  ->  this data center equals {x['pct_of_state_power']:.1f}% of that "
                  f"(+{approx(x['adds_t'])} t = {approx(x['cars'])} cars)")
        else:
            print(f" Carbon      : this data center adds about {approx(x['adds_t'])} t CO2/yr = {approx(x['cars'])} cars driven for a year")

    print("\nENVIRONMENTAL INDICATORS WE CAN CALCULATE")
    print("-" * 60)
    if "water" in R: print(f" - River stress: takes {R['water']['pct_of_dry']:.2f}% of the dry-period flow of {R['water']['river']} (an indicator only; fish/habitat limits are not applied).")
    if "noise" in R: print(f" - Noise footprint: about {R['noise']['footprint_acres']:,.0f} acres where machine noise exceeds {R['noise']['target_db']:.0f} dB (wildlife and neighbours).")
    if "carbon" in R: print(f" - Climate: about {approx(R['carbon']['adds_t'])} metric tons of CO2 a year, of which {approx(R['carbon']['diesel_t'])} t from diesel generators ({R['carbon']['diesel_hours']} h/yr).")
    print(" - NOT calculated: habitat and wildlife effects, local air pollutants (NOx/particles from generators), land use, light, heat. Those need a formal environmental review.")


def print_plain_report(o):
    """Human-readable report in plain English: no formulas. Printed only; nothing is saved."""
    L, c, f = TXT["en"], o["cfg"], o["facility"]
    A, D = analyze(o), decide(o)
    p, w, k, n = o["power"], o["water"], o["carbon"], o["noise"]
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC")
    W = 92
    def H(t): print("\n" + t + "\n" + "-" * min(W, max(len(t), 20)))

    print("=" * W + f"\n{L['title']}\n" + "=" * W)
    print(L["place"].format(state=c["STATE"], lat=c["LAT"], lon=c["LON"], radius=c["RADIUS_MILES"]))
    print(L["size"].format(it_mw=c["IT_MW"], note=c["size_note"]))
    print(L["gen"].format(now=now))

    # ---- answer
    H(L["h_answer"])
    issues = ", ".join(f"{LAYER_NAME[k2]} {WORD[o['statuses'][k2]].split(' ')[0]}" for k2 in D["red"] + D["amber"])
    extra = L["v_extra"].format(issues=issues) if (D["code"] == "INCOMPLETE" and issues) else ""
    print(L["v_" + D["code"]].format(layers=_layers_text(D["red"] if D["code"] == "NOT_AS_PLANNED" else D["amber"]),
                                     unchecked=_layers_text(D["unchecked"]), extra=extra))

    # ---- needs
    H(L["h_needs"])
    sp = L["n_statepct"].format(state=c["STATE"], pct=A["state_pct"]) if A.get("state_pct") else ""
    print(L["n_power"].format(avg=f["fac_avg_mw"], peak=f["fac_peak_mw"], mwh=approx(f["annual_mwh"]), homes=approx(A["homes_power"]), statepct=sp))
    if f["water_need_mgd"] > 0:
        print(L["n_water"].format(mgd=f["water_need_mgd"], gal=approx(A["water_gal_day"]), homes=approx(A["homes_water"]), avg=A["water_avg_mgd"]))
    else:
        print(L["n_water0"])
    if k["status"] != UNKNOWN:
        print(L["n_carbon"].format(t=approx(k["total_location_t"]), cars=approx(A["cars"])))
    if n["status"] != UNKNOWN:
        print(L["n_noise"].format(db=n["level_dba"], dist=c["HOUSE_DIST_M"], ft=c["HOUSE_DIST_M"] * 3.28084, feel=_feel(n["level_dba"])))

    # ---- four checks
    H(L["h_checks"])
    def head(i, key): return f" {i}. {LAYER_NAME[key]:<12}{WORD[o[key]['status']]}"
    print(head(1, "power"))
    if p["status"] == UNKNOWN: print("    " + L["c_unknown"].format(error=p["error"]))
    else:
        if p["worst_kw"] < 0: print("    " + L["c_power_def"].format(m=p["worst_month"], d=-p["worst_kw"] / 1000))
        else: print("    " + L["c_power"].format(s=A["surplus_mw"], n=A["need_mw"], r=p["ratio"]))
        print("    " + L["c_power_note"])
    print(head(2, "water"))
    if w["status"] == UNKNOWN: print("    " + L["c_unknown"].format(error=w["error"]))
    elif f["water_need_mgd"] == 0: print("    " + L["c_water0"])
    else:
        print("    " + L["c_water"].format(river=w["river"], p10=w["p10_mgd"], mgd=w["need_mgd"], pct=A["water_pct_of_dry"],
                                           take=w["take_pct"], allowed=w["assumed_take_mgd"], r=w["ratio"]))
        print("    " + L["c_water_note"])
    print(head(3, "carbon"))
    if k["status"] == UNKNOWN: print("    " + L["c_unknown"].format(error=k["error"]))
    else:
        print("    " + L["c_carbon"].format(src=_src_name(k["factor_src"]), f=k["factor_kg_mwh"], rel=k["rel_to_us"], t=approx(k["total_location_t"]), s1=approx(k["scope1_t"])))
        print("    " + L["c_carbon_note"])
    print(head(4, "noise"))
    if n["status"] == UNKNOWN: print("    " + L["c_unknown"].format(error=n["error"]))
    else:
        print("    " + L["c_noise"].format(dist=c["HOUSE_DIST_M"], ft=c["HOUSE_DIST_M"] * 3.28084, db=n["level_dba"], ld=c["LIMIT_DAY"], dayok=L["ok"] if n["ok_day"] else L["fail"],
                                           ln=c["LIMIT_NIGHT"], nightok=L["ok"] if n["ok_night"] else L["fail"], gh=c["GEN_HOURS"], gen=n["gen_level_dba"]))
        print("    " + L["c_noise_note"])

    print_comparison(o)

    # ---- fixes
    H(L["h_fix"])
    fixes = []
    if p["status"] in (AMBER, RED):
        fixes.append(L["f_power"].format(mw=approx(A["max_it_mw_power"]), mwc=approx(A["max_it_mw_power_comfortable"])))
    if w["status"] in (AMBER, RED):
        fixes.append(L["f_water"].format(wue=A["wue_max"], mw=approx(A["max_it_mw_water"]), cur=c["WUE"]))
    if k["status"] in (AMBER, RED):
        fixes.append(L["f_carbon"].format(t=approx(A["t_saved_per_10pct_clean"])))
    if n["status"] in (AMBER, RED):
        fixes.append(L["f_noise"].format(cut=A["noise_cut_needed_db"], dist=approx(A["noise_safe_distance_m"]), ft=approx(A["noise_safe_distance_m"] * 3.28084)))
    for x in (fixes or [L["f_none"]]):
        print(" - " + x)

    # ---- trust
    H(L["h_trust"])
    real = []
    if p["status"] != UNKNOWN: real.append(L["t_real_power"].format(first=p["evidence"].get("first", "?"), last=p["evidence"].get("last", "?")))
    if w["status"] != UNKNOWN: real.append(L["t_real_water"].format(n=len(w["table"])))
    if k["status"] != UNKNOWN: real.append(L["t_real_carbon"])
    print(" - " + L["t_real"].format(list="; ".join(real) or L["t_real_none"]))
    given = o.get("given", set())
    guesses = []
    if "IT_MW" not in given and "SERVERS" not in given: pass
    g = c
    if "PUE" not in given: guesses.append(L["g_PUE"].format(pct=(g["PUE"] - 1) * 100, v=g["PUE"]))
    if "LOAD_FACTOR" not in given: guesses.append(L["g_LOAD_FACTOR"].format(v=g["LOAD_FACTOR"]))
    if "WUE" not in given: guesses.append(L["g_WUE"].format(v=g["WUE"]))
    if "GEN_HOURS" not in given: guesses.append(L["g_GEN_HOURS"].format(v=g["GEN_HOURS"]))
    if "HOUSE_DIST_M" not in given: guesses.append(L["g_HOUSE_DIST_M"].format(v=g["HOUSE_DIST_M"]))
    if "AMBIENT_DB" not in given: guesses.append(L["g_AMBIENT_DB"].format(v=g["AMBIENT_DB"]))
    if "TAKE_PCT" not in given: guesses.append(L["g_TAKE_PCT"].format(v=g["TAKE_PCT"]))
    if "LOSS_PCT" not in given: guesses.append(L["g_LOSS_PCT"].format(v=g["LOSS_PCT"]))
    if "LIMIT_DAY" not in given and "LIMIT_NIGHT" not in given: guesses.append(L["g_LIMIT_DAY"].format(d=g["LIMIT_DAY"], n=g["LIMIT_NIGHT"]))
    if "RENEWABLE_SHARE" not in given: guesses.append(L["g_RENEWABLE_SHARE"].format(v=g["RENEWABLE_SHARE"]))
    if "BARRIER_DB" not in given: guesses.append(L["g_BARRIER_DB"].format(v=g["BARRIER_DB"]))
    print(" - " + (L["t_guess"].format(list="; ".join(guesses)) if guesses else L["t_guess_none"]))
    print(" - " + L["t_machines"])

    H(L["h_not"])
    for x in L["not_list"]:
        print(" - " + x)
    H(L["h_words"])
    print(L["words"])
    print(L["equiv"])
    print("=" * W)


# ----------------------------------------------------------------------------- brief for an AI (no AI is called here)
def _clean(x):
    """Make numbers JSON-safe: inf -> 'unlimited', nan -> None, floats rounded."""
    if isinstance(x, dict): return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, float): return "unlimited" if math.isinf(x) else None if math.isnan(x) else round(x, 3)
    return x


def ai_brief(o) -> str:
    """Compact, factual JSON + instructions. Paste it into any AI later to get a plain-language summary and advice."""
    c, f, A, D = o["cfg"], o["facility"], analyze(o), decide(o)
    p, w, k, n = o["power"], o["water"], o["carbon"], o["noise"]
    r = lambda x, d=2: None if x is None else (round(float(x), d) if math.isfinite(float(x)) else "unlimited")
    layers = {}
    layers["power"] = dict(status=p["status"]) if p["status"] == UNKNOWN else dict(
        status=p["status"], weakest_month=str(p["worst_month"]), weakest_month_spare_mw=r(p["worst_kw"] / 1000),
        last12_avg_spare_mw=r(p["last12_kw"] / 1000), need_avg_mw=r(p["need_kw"] / 1000), spare_over_need=r(p["ratio"]),
        share_of_state_use_pct=r(A.get("state_pct"), 1), max_it_mw_that_fits=r(A["max_it_mw_power"], 1),
        data="EIA monthly generation minus retail sales (state, scaled by radius area)")
    layers["water"] = dict(status=w["status"]) if w["status"] == UNKNOWN else dict(
        status=w["status"], river=w["river"], median_flow_mgd=r(w["median_mgd"], 1), dry_flow_p10_mgd=r(w["p10_mgd"], 1),
        need_mgd=r(w["need_mgd"], 3), assumed_take_pct=w["take_pct"], assumed_allowed_mgd=r(w["assumed_take_mgd"], 3),
        need_over_allowed=r(w["ratio"]), need_pct_of_dry_flow=r(A["water_pct_of_dry"], 2),
        max_wue_l_per_kwh=r(A["wue_max"], 2), max_it_mw_at_current_wue=r(A["max_it_mw_water"], 1),
        data="USGS daily discharge, largest nearby river by drainage area; NOT a water right")
    layers["carbon"] = dict(status=k["status"]) if k["status"] == UNKNOWN else dict(
        status=k["status"], grid=k["factor_src"], grid_kg_per_mwh=r(k["factor_kg_mwh"], 1), vs_us_average=r(k["rel_to_us"]),
        total_tco2e_per_year=r(k["total_location_t"], 0), electricity_tco2e=r(k["scope2_location_t"], 0),
        diesel_tco2e=r(k["scope1_t"], 0), cars_equivalent=r(A["cars"], 0), saved_per_10pct_clean_power_t=r(A["t_saved_per_10pct_clean"], 0),
        data="EPA eGRID2023 state table; EPA diesel factor")
    layers["noise"] = dict(status=n["status"]) if n["status"] == UNKNOWN else dict(
        status=n["status"], continuous_db_at_house=r(n["level_dba"], 1), distance_to_house_m=c["HOUSE_DIST_M"],
        generator_db_when_running=r(n["gen_level_dba"], 1), day_limit=c["LIMIT_DAY"], night_limit=c["LIMIT_NIGHT"],
        pass_day=bool(n["ok_day"]), pass_night=bool(n["ok_night"]), pass_ldn_55=bool(n["ok_ldn"]),
        db_reduction_needed=r(A["noise_cut_needed_db"], 1), distance_that_would_pass_m=r(A["noise_safe_distance_m"], 0),
        data="Estimated machine noise (assumptions) + distance rule")
    given = sorted(o.get("given", []))
    brief = dict(
        instructions_for_ai=("You are helping a non-expert decide about building a data center. Use ONLY the numbers in this JSON; do not invent data. "
                             "In simple everyday English: 1) say clearly whether the site looks workable, workable with conditions, "
                             "not workable, or undecided and why; 2) explain electricity, water, carbon and noise in one or two sentences each with everyday comparisons; "
                             "3) list what could fix any problem; 4) say plainly what is a guess or not checked. This is screening, not a final decision."),
        site=dict(state=c["STATE"], lat=c["LAT"], lon=c["LON"], radius_miles=c["RADIUS_MILES"]),
        data_center=dict(it_mw=r(c["IT_MW"], 3), size_note=c["size_note"], pue=c["PUE"], load_factor=c["LOAD_FACTOR"], wue_l_per_kwh=c["WUE"],
                         facility_peak_mw=r(f["fac_peak_mw"], 1), facility_avg_mw=r(f["fac_avg_mw"], 1), energy_mwh_per_year=r(f["annual_mwh"], 0),
                         water_need_mgd_peak=r(f["water_need_mgd"], 3), homes_equivalent_power=r(A["homes_power"], 0),
                         homes_equivalent_water=r(A["homes_water"], 0)),
        comparison=_clean(comparison(o)),
        verdict=dict(code=D["code"], red=D["red"], amber=D["amber"], not_checked=D["unchecked"]),
        layers=layers,
        inputs_given_by_user=given,
        inputs_defaulted_guesses=[x for x in ("PUE", "LOAD_FACTOR", "WUE", "GEN_HOURS", "HOUSE_DIST_M", "AMBIENT_DB", "TAKE_PCT", "LOSS_PCT", "LIMIT_DAY", "LIMIT_NIGHT",
                                              "RENEWABLE_SHARE", "BARRIER_DB") if x not in given],
        always_assumptions=["machine noise levels and unit counts", "generator fuel use 0.07 gal/kWh and sized for the whole facility",
                            "traffic-light thresholds are the author's, not legal limits", "surplus electricity is energy-based, not connection capacity"],
        not_checked_at_all=["water rights/permits", "groundwater", "city water capacity", "peak grid capacity and interconnection queue",
                            "local noise law and zoning", "flood risk, fiber, land price"],
    )
    return json.dumps(brief, indent=2, ensure_ascii=False)


def main(user=None, **kw):
    """Run everything and print. Returns the result dict. Nothing is written to disk."""
    o = run(user, **kw)
    print_plain_report(o)
    if OUTPUT["SHOW_PROOF"]:
        print_report(o)
    if OUTPUT["SHOW_AI_BRIEF"]:
        print("\n" + "=" * 92 + "\nBRIEF FOR AN AI (copy this block later and ask an AI to summarise it in simple words)\n" + "=" * 92)
        print(ai_brief(o))
    return o


if __name__ == "__main__":
    # Colab: edit USER_INPUT (and OUTPUT) near the top, then run this cell. Keys: env vars or a hidden prompt.
    main()
