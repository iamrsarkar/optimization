"""Warehouse optimization utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from data_loader import compute_order_demand
from eda_utils import compute_stock_cover


@dataclass
class TransferRecommendation:
    source: str
    destination: str
    product_category: str
    quantity: float


@dataclass
class ReorderRecommendation:
    warehouse: str
    product_category: str
    suggested_quantity: float


def analyse_inventory(
    inventory: pd.DataFrame,
    orders: pd.DataFrame,
) -> pd.DataFrame:
    """Compute enriched inventory metrics including stock cover."""
    demand = compute_order_demand(orders)
    enriched = compute_stock_cover(inventory, demand)
    return enriched


def recommend_transfers(enriched_inventory: pd.DataFrame) -> pd.DataFrame:
    """Suggest simple inventory rebalancing transfers between warehouses."""
    if enriched_inventory.empty:
        return pd.DataFrame(columns=["Source", "Destination", "Product_Category", "Quantity"])

    transfer_records: List[Dict[str, object]] = []

    grouped = enriched_inventory.groupby("Product_Category")
    for product, group in grouped:
        surplus_rows = group[group["Overstock_Flag"]]
        deficit_rows = group[group["Understock_Flag"]]
        if surplus_rows.empty or deficit_rows.empty:
            continue

        surplus_rows = surplus_rows.assign(
            Surplus=lambda df: df["Stock_Level"]
            - df[["Reorder_Level", "Orders_Count"]].fillna(0).max(axis=1)
        )
        surplus_rows["Surplus"] = surplus_rows["Surplus"].clip(lower=0)

        deficit_rows = deficit_rows.assign(
            Deficit=lambda df: df[["Reorder_Level", "Orders_Count"]].fillna(0).max(axis=1)
            - df["Stock_Level"]
        )
        deficit_rows["Deficit"] = deficit_rows["Deficit"].clip(lower=0)

        surplus_rows = surplus_rows.sort_values("Surplus", ascending=False)
        deficit_rows = deficit_rows.sort_values("Deficit", ascending=False)

        for _, deficit in deficit_rows.iterrows():
            remaining_deficit = deficit["Deficit"]
            if remaining_deficit <= 0:
                continue
            for s_idx, surplus in surplus_rows.iterrows():
                available = surplus["Surplus"]
                if available <= 0:
                    continue
                transfer_qty = min(available, remaining_deficit)
                if transfer_qty <= 0:
                    continue
                transfer_records.append(
                    {
                        "Source": surplus["Warehouse"],
                        "Destination": deficit["Warehouse"],
                        "Product_Category": product,
                        "Quantity": round(float(transfer_qty), 2),
                    }
                )
                surplus_rows.at[s_idx, "Surplus"] -= transfer_qty
                remaining_deficit -= transfer_qty
                if remaining_deficit <= 0:
                    break

    return pd.DataFrame(transfer_records)


def recommend_reorders(enriched_inventory: pd.DataFrame) -> pd.DataFrame:
    """Recommend reorder quantities for understocked items."""
    if enriched_inventory.empty:
        return pd.DataFrame(columns=["Warehouse", "Product_Category", "Suggested_Reorder"])

    reorder_df = enriched_inventory[enriched_inventory["Understock_Flag"]].copy()
    if reorder_df.empty:
        return pd.DataFrame(columns=["Warehouse", "Product_Category", "Suggested_Reorder"])

    reorder_df["Reorder_Level"] = reorder_df["Reorder_Level"].fillna(0)
    reorder_df["Orders_Count"] = reorder_df["Orders_Count"].fillna(0)
    reorder_df["Stock_Level"] = reorder_df["Stock_Level"].fillna(0)

    target_level = reorder_df[["Reorder_Level", "Orders_Count"]].copy()
    target_level["Orders_Count"] = target_level["Orders_Count"] + 5
    reorder_df["Target_Level"] = target_level.max(axis=1)
    reorder_df["Suggested_Reorder"] = reorder_df["Target_Level"] - reorder_df["Stock_Level"]
    reorder_df["Suggested_Reorder"] = reorder_df["Suggested_Reorder"].clip(lower=0)
    return reorder_df[["Warehouse", "Product_Category", "Suggested_Reorder"]]
