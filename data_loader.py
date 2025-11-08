"""Data loading and preparation utilities for the logistics analytics app."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

import config

try:  # pragma: no cover - Streamlit might not be available during tests
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore


LOGGER = logging.getLogger(__name__)


def _debug(message: str) -> None:
    if config.DEBUG_MODE:
        LOGGER.info(message)


PARSE_DATE_MAP: Dict[str, List[str]] = {
    "orders.csv": ["Order_Date"],
    "delivery_performance.csv": ["Promised_Delivery_Date", "Actual_Delivery_Date"],
    "warehouse_inventory.csv": ["Last_Restocked_Date"],
    "customer_feedback.csv": ["Feedback_Date"],
}


def _read_csv(file_name: str, parse_dates: List[str] | None = None) -> pd.DataFrame:
    """Read a CSV file with optional date parsing and graceful failure."""
    file_path = Path(file_name)
    if not file_path.exists():
        _debug(f"Missing file: {file_name}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(file_path)
    except Exception as exc:  # pragma: no cover - I/O error guard
        _debug(f"Failed to read {file_name}: {exc}")
        return pd.DataFrame()

    if parse_dates:
        for col in parse_dates:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _apply_standardisation(df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
    """Standardise data types for key columns."""
    if df.empty:
        return df
    if "Order_ID" in df.columns:
        df["Order_ID"] = df["Order_ID"].astype(str)
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# Decorator wrapper to support caching when Streamlit is available.
if st is not None:  # pragma: no branch - decorator assignment

    @st.cache_data(show_spinner=False)
    def load_all_data() -> Dict[str, pd.DataFrame]:
        return _load_all_data_impl()

else:  # pragma: no cover - executed during tests without Streamlit

    def load_all_data() -> Dict[str, pd.DataFrame]:
        return _load_all_data_impl()


def _load_all_data_impl() -> Dict[str, pd.DataFrame]:
    """Internal function that loads each dataset and returns a dictionary."""
    files = [
        "orders.csv",
        "delivery_performance.csv",
        "routes_distance.csv",
        "vehicle_fleet.csv",
        "warehouse_inventory.csv",
        "customer_feedback.csv",
        "cost_breakdown.csv",
    ]

    data: Dict[str, pd.DataFrame] = {}
    for file_name in files:
        df = _read_csv(file_name, PARSE_DATE_MAP.get(file_name))
        df = _apply_standardisation(df, PARSE_DATE_MAP.get(file_name, []))
        data[file_name.replace(".csv", "")] = df
    return data


def create_master_orders(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine the various datasets into a master orders dataframe."""
    orders = data.get("orders", pd.DataFrame()).copy()
    delivery = data.get("delivery_performance", pd.DataFrame()).copy()
    routes = data.get("routes_distance", pd.DataFrame()).copy()
    costs = data.get("cost_breakdown", pd.DataFrame()).copy()
    fleet = data.get("vehicle_fleet", pd.DataFrame()).copy()

    if orders.empty:
        return pd.DataFrame()

    # Ensure consistent Order_ID types
    for df in (orders, delivery, routes, costs):
        if not df.empty and "Order_ID" in df.columns:
            df["Order_ID"] = df["Order_ID"].astype(str)

    master = orders.merge(delivery, on="Order_ID", how="left", suffixes=("", "_delivery"))
    master = master.merge(routes, on="Order_ID", how="left")
    master = master.merge(costs, on="Order_ID", how="left")

    # Derived metrics
    cost_cols = [
        "Delivery_Cost_INR",
        "Fuel_Cost_INR",
        "Labor_Cost_INR",
        "Maintenance_Cost_INR",
        "Insurance_Cost_INR",
        "Packaging_Cost_INR",
        "Technology_Fee_INR",
        "Other_Overhead_INR",
        "Toll_Cost_INR",
    ]

    for col in cost_cols:
        if col in master.columns:
            master[col] = master[col].fillna(0)

    master["Total_Variable_Cost"] = (
        master.get("Fuel_Cost_INR", 0)
        + master.get("Labor_Cost_INR", 0)
        + master.get("Maintenance_Cost_INR", 0)
        + master.get("Toll_Cost_INR", 0)
        + master.get("Other_Overhead_INR", 0)
    )

    master["Total_Delivery_Cost"] = master["Delivery_Cost_INR"] + (
        master.get("Fuel_Cost_INR", 0)
        + master.get("Labor_Cost_INR", 0)
        + master.get("Maintenance_Cost_INR", 0)
        + master.get("Insurance_Cost_INR", 0)
        + master.get("Packaging_Cost_INR", 0)
        + master.get("Technology_Fee_INR", 0)
        + master.get("Other_Overhead_INR", 0)
        + master.get("Toll_Cost_INR", 0)
    )

    if "Promised_Delivery_Date" in master.columns and "Actual_Delivery_Date" in master.columns:
        master["Delivery_Delay_Days"] = (
            master["Actual_Delivery_Date"] - master["Promised_Delivery_Date"]
        ).dt.days
    else:
        master["Delivery_Delay_Days"] = np.nan

    master["On_Time_Flag"] = master["Delivery_Delay_Days"].apply(
        lambda x: np.nan if pd.isna(x) else int(x <= 0)
    )

    if "Distance_km" not in master.columns:
        master["Distance_km"] = np.nan
    else:
        master["Distance_km"] = master["Distance_km"].astype(float)

    if "Fuel_Consumed_L" in master.columns:
        master["Fuel_Consumed_L"] = master["Fuel_Consumed_L"].replace(0, np.nan)
        master["Fuel_Efficiency_km_per_L_order"] = master["Distance_km"] / master["Fuel_Consumed_L"]

    master["Cost_per_km"] = np.where(
        master["Distance_km"].gt(0),
        master["Total_Delivery_Cost"] / master["Distance_km"],
        np.nan,
    )

    # Estimate CO2 emissions using fleet averages when available
    avg_co2_per_km = None
    if not fleet.empty and "CO2_kg_per_km" in fleet.columns:
        avg_co2_per_km = fleet["CO2_kg_per_km"].replace(0, np.nan).mean()
    if pd.isna(avg_co2_per_km) or avg_co2_per_km is None:
        avg_co2_per_km = 0.65  # fallback industry average (kg/km)

    master["Estimated_CO2_kg"] = master.get("Distance_km", 0).fillna(0) * avg_co2_per_km

    return master


def compute_order_demand(orders: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order demand per warehouse and product category."""
    if orders.empty:
        return pd.DataFrame()

    agg = (
        orders.dropna(subset=["Origin", "Product_Category"])
        .groupby(["Origin", "Product_Category"])
        .agg(
            Orders_Count=("Order_ID", "count"),
            Total_Order_Value=("Order_Value_INR", "sum"),
        )
        .reset_index()
    )
    agg.rename(columns={"Origin": "Warehouse"}, inplace=True)
    return agg
