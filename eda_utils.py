"""Exploratory data analysis helpers."""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd

import config


def apply_global_filters(
    df: pd.DataFrame,
    date_range: Tuple[pd.Timestamp | None, pd.Timestamp | None],
    priorities: Iterable[str] | None = None,
    products: Iterable[str] | None = None,
    origins: Iterable[str] | None = None,
    destinations: Iterable[str] | None = None,
    segments: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Filter the master dataframe based on user selections."""
    if df.empty:
        return df

    filtered = df.copy()

    start_date, end_date = date_range
    if start_date is not None:
        filtered = filtered[filtered["Order_Date"] >= start_date]
    if end_date is not None:
        filtered = filtered[filtered["Order_Date"] <= end_date]

    def _apply_list_filter(frame: pd.DataFrame, column: str, values: Iterable[str] | None) -> pd.DataFrame:
        if values:
            return frame[frame[column].isin(values)]
        return frame

    if "Priority" in filtered.columns:
        filtered = _apply_list_filter(filtered, "Priority", priorities)
    if "Product_Category" in filtered.columns:
        filtered = _apply_list_filter(filtered, "Product_Category", products)
    if "Origin" in filtered.columns:
        filtered = _apply_list_filter(filtered, "Origin", origins)
    if "Destination" in filtered.columns:
        filtered = _apply_list_filter(filtered, "Destination", destinations)
    if "Customer_Segment" in filtered.columns:
        filtered = _apply_list_filter(filtered, "Customer_Segment", segments)

    return filtered


def calculate_overall_kpis(master: pd.DataFrame) -> Dict[str, float]:
    """Compute top-level KPIs for the overview page."""
    if master.empty:
        return {
            "total_orders": 0,
            "total_revenue": 0.0,
            "on_time_rate": np.nan,
            "avg_delay": np.nan,
            "avg_cost_per_order": np.nan,
            "total_emissions": 0.0,
        }

    total_orders = len(master)
    total_revenue = float(master.get("Order_Value_INR", pd.Series(dtype=float)).sum())
    on_time_series = master.get("On_Time_Flag", pd.Series(dtype=float)).dropna()
    on_time_rate = float(on_time_series.mean()) if not on_time_series.empty else np.nan
    avg_delay = float(master.get("Delivery_Delay_Days", pd.Series(dtype=float)).mean())
    avg_cost_per_order = float(master.get("Total_Delivery_Cost", pd.Series(dtype=float)).mean())
    total_emissions = float(master.get("Estimated_CO2_kg", pd.Series(dtype=float)).sum())

    return {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "on_time_rate": on_time_rate,
        "avg_delay": avg_delay,
        "avg_cost_per_order": avg_cost_per_order,
        "total_emissions": total_emissions,
    }


def summarise_on_time_by_group(master: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Summarise on-time performance by the specified column."""
    if master.empty or group_col not in master.columns:
        return pd.DataFrame()

    summary = (
        master.dropna(subset=[group_col])
        .groupby(group_col)
        .agg(
            Orders=("Order_ID", "count"),
            On_Time_Rate=("On_Time_Flag", "mean"),
            Avg_Delay=("Delivery_Delay_Days", "mean"),
        )
        .reset_index()
    )

    return summary


def compute_cost_breakdown(master: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Aggregate cost components by a grouping column."""
    cost_cols = [
        "Fuel_Cost_INR",
        "Labor_Cost_INR",
        "Maintenance_Cost_INR",
        "Insurance_Cost_INR",
        "Packaging_Cost_INR",
        "Technology_Fee_INR",
        "Other_Overhead_INR",
    ]

    available_cols = [col for col in cost_cols if col in master.columns]
    if master.empty or not available_cols or group_col not in master.columns:
        return pd.DataFrame()

    grouped = (
        master.dropna(subset=[group_col])
        .groupby(group_col)[available_cols]
        .sum()
        .reset_index()
    )
    return grouped


def compute_stock_cover(inventory: pd.DataFrame, demand: pd.DataFrame) -> pd.DataFrame:
    """Calculate stock cover and indicators for warehouse inventory."""
    if inventory.empty:
        return pd.DataFrame()

    merged = inventory.merge(demand, on=["Warehouse", "Product_Category"], how="left")
    merged["Orders_Count"] = merged["Orders_Count"].fillna(0)

    # Estimate daily demand using orders over last 30 days if available
    merged["Estimated_Daily_Demand"] = merged["Orders_Count"] / 30
    merged["Stock_Cover_Days"] = merged.apply(
        lambda row: row["Stock_Level"] / row["Estimated_Daily_Demand"]
        if row["Estimated_Daily_Demand"] > 0
        else np.inf,
        axis=1,
    )

    merged["Understock_Flag"] = (
        (merged["Stock_Level"] < merged["Reorder_Level"])
        | (merged["Stock_Cover_Days"] < config.MIN_STOCK_COVER_DAYS)
    )
    merged["Overstock_Flag"] = merged["Stock_Cover_Days"] > (config.MIN_STOCK_COVER_DAYS * 4)
    return merged
