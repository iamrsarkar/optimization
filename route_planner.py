"""Smart route planner logic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


def _normalize_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    min_val = series.min()
    max_val = series.max()
    if pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - min_val) / (max_val - min_val)


@dataclass
class RouteWeights:
    cost_weight: float
    time_weight: float
    emission_weight: float

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.cost_weight, self.time_weight, self.emission_weight)


def compute_route_scores(master: pd.DataFrame, weights: RouteWeights) -> pd.DataFrame:
    """Compute a composite route score using user-defined weights."""
    if master.empty:
        return pd.DataFrame()

    required_cols = {
        "Order_ID",
        "Total_Delivery_Cost",
        "Delivery_Delay_Days",
        "Estimated_CO2_kg",
    }

    missing_cols = required_cols - set(master.columns)
    if missing_cols:
        raise ValueError(f"Missing columns for route scoring: {missing_cols}")

    optional_cols = [col for col in ["Origin", "Destination", "Carrier", "Priority"] if col in master.columns]
    scoring_df = master[list(required_cols) + optional_cols].copy()

    scoring_df["Cost_norm"] = _normalize_series(scoring_df["Total_Delivery_Cost"].fillna(0))
    scoring_df["Delay_norm"] = _normalize_series(scoring_df["Delivery_Delay_Days"].fillna(0))
    scoring_df["Emission_norm"] = _normalize_series(scoring_df["Estimated_CO2_kg"].fillna(0))

    cw, tw, ew = weights.as_tuple()
    scoring_df["Route_Score"] = (
        cw * scoring_df["Cost_norm"]
        + tw * scoring_df["Delay_norm"]
        + ew * scoring_df["Emission_norm"]
    )

    scoring_df.sort_values("Route_Score", inplace=True)
    return scoring_df


def summarise_lane_performance(master: pd.DataFrame) -> pd.DataFrame:
    """Generate origin-destination-carrier summary metrics."""
    if master.empty:
        return pd.DataFrame()

    summary = (
        master.groupby(["Origin", "Destination", "Carrier"], dropna=False)
        .agg(
            Orders=("Order_ID", "count"),
            Avg_Cost=("Total_Delivery_Cost", "mean"),
            Avg_Delay=("Delivery_Delay_Days", "mean"),
            Avg_Emission=("Estimated_CO2_kg", "mean"),
            On_Time_Rate=("On_Time_Flag", "mean"),
        )
        .reset_index()
    )
    return summary


def best_and_worst_routes(scored: pd.DataFrame, top_n: int = 10) -> Dict[str, pd.DataFrame]:
    """Return top/bottom routes based on scores."""
    if scored.empty:
        return {"best": pd.DataFrame(), "worst": pd.DataFrame()}

    best = scored.head(top_n)
    worst = scored.tail(top_n).sort_values("Route_Score", ascending=False)
    return {"best": best, "worst": worst}
