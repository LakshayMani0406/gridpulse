"""Interactive gridpulse dashboard (Streamlit).

Run:  streamlit run -m gridpulse.dashboard   # or: streamlit run src/gridpulse/dashboard.py

Reads the DuckDB warehouse, computes AEF / production-MEF / consumption-MEF, and
shows: a US map of BAs colored by factor, a siting explorer (pick a load size,
see the carbon-ranked BAs), and the actual-vs-optimal siting-gap headline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis import HOURS_PER_YEAR, siting_index
from .config import load_config
from .emissions import aef_by_ba, assemble_hourly, mef_by_ba
from .regions import REGIONS
from .storage import Warehouse


def _load_factors():
    cfg = load_config()
    wh = Warehouse(cfg)
    fuel = wh.read("fuel_mix")
    demand = wh.read("demand")
    if fuel.empty:
        return None
    fuel_long = fuel[["period", "ba", "fueltype", "mwh"]]
    demand_long = demand[["period", "ba", "mwh"]] if not demand.empty else pd.DataFrame()
    asm = assemble_hourly(fuel_long, demand_long)
    aef = aef_by_ba(asm)
    mef = mef_by_ba(asm, driver="demand", n_boot=200)
    siting = siting_index(mef, aef, load_mw=100.0)
    # attach coordinates
    siting["lat"] = siting["ba"].map(lambda b: REGIONS[b].lat if b in REGIONS else np.nan)
    siting["lon"] = siting["ba"].map(lambda b: REGIONS[b].lon if b in REGIONS else np.nan)
    siting["name"] = siting["ba"].map(lambda b: REGIONS[b].name if b in REGIONS else b)
    return siting


def main() -> None:  # pragma: no cover - UI entry point
    import streamlit as st
    import plotly.express as px

    st.set_page_config(page_title="gridpulse", layout="wide")
    st.title("gridpulse — marginal grid carbon for data-center siting")
    st.caption("A new data center is an increment of load: its carbon is set by the "
               "**marginal** emission factor, not the average. The two can invert the ranking.")

    siting = st.cache_data(_load_factors)()
    if siting is None or siting.empty:
        st.warning("Warehouse is empty. Run `gridpulse backfill` first.")
        return

    load_mw = st.sidebar.slider("New data-center load (MW)", 10, 2000, 250, step=10)
    factor = st.sidebar.selectbox("Color map by", ["mef_kg_per_mwh", "aef_kg_per_mwh"])

    tab_map, tab_rank, tab_gap = st.tabs(["Map", "Siting explorer", "Average vs marginal"])

    with tab_map:
        fig = px.scatter_geo(
            siting, lat="lat", lon="lon", color=factor, size=[12] * len(siting),
            hover_name="name", scope="usa", color_continuous_scale="RdYlGn_r",
            labels={factor: "kg CO2/MWh"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_rank:
        d = siting.copy()
        d["annual_ktCO2"] = load_mw * HOURS_PER_YEAR * d["mef_kg_per_mwh"] / 1e6
        d = d.sort_values("mef_kg_per_mwh")
        st.subheader(f"Siting a {load_mw} MW facility — ranked by marginal carbon")
        st.dataframe(
            d[["ba", "name", "mef_kg_per_mwh", "aef_kg_per_mwh", "rank_shift", "annual_ktCO2"]]
            .rename(columns={"annual_ktCO2": "annual ktCO2/yr"}),
            use_container_width=True,
        )
        best, worst = d.iloc[0], d.iloc[-1]
        st.metric("Penalty of worst vs best site",
                  f"{(worst['annual_ktCO2'] - best['annual_ktCO2']):,.0f} ktCO2/yr",
                  help=f"{best['ba']} vs {worst['ba']}")

    with tab_gap:
        fig2 = px.scatter(
            siting, x="aef_kg_per_mwh", y="mef_kg_per_mwh", text="ba",
            labels={"aef_kg_per_mwh": "Average (AEF)", "mef_kg_per_mwh": "Marginal (MEF)"},
        )
        lim = float(max(siting["aef_kg_per_mwh"].max(), siting["mef_kg_per_mwh"].max()) * 1.05)
        fig2.add_shape(type="line", x0=0, y0=0, x1=lim, y1=lim, line=dict(dash="dash"))
        fig2.update_traces(textposition="top center")
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Points above the line are dirtier on the margin than on average — "
                   "regions a naive average-based analysis would wrongly call clean.")


if __name__ == "__main__":  # pragma: no cover
    main()
