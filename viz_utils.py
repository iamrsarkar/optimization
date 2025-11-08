"""Reusable visualisation helpers using Plotly."""
from __future__ import annotations

from typing import List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLOR_SEQUENCE = px.colors.qualitative.Safe


def orders_over_time(master: pd.DataFrame) -> go.Figure:
    if master.empty or "Order_Date" not in master.columns:
        return px.line(title="Orders Over Time")
    df = (
        master.dropna(subset=["Order_Date"])
        .groupby(pd.Grouper(key="Order_Date", freq="W"))
        .agg(Orders=("Order_ID", "count"), Revenue=("Order_Value_INR", "sum"))
        .reset_index()
    )
    fig = px.line(
        df,
        x="Order_Date",
        y=["Orders", "Revenue"],
        title="Weekly Orders and Revenue",
        markers=True,
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_layout(legend_title="Metric")
    return fig


def on_time_by_priority(master: pd.DataFrame) -> go.Figure:
    if master.empty or "Priority" not in master.columns:
        return px.bar(title="On-Time Rate by Priority")
    df = (
        master.dropna(subset=["Priority"])
        .groupby("Priority")
        .agg(On_Time_Rate=("On_Time_Flag", "mean"), Avg_Delay=("Delivery_Delay_Days", "mean"))
        .reset_index()
    )
    fig = px.bar(
        df,
        x="Priority",
        y="On_Time_Rate",
        color="Avg_Delay",
        title="On-Time Rate by Priority",
        color_continuous_scale="RdYlGn_r",
    )
    fig.update_layout(yaxis_tickformat=".0%")
    return fig


def cost_by_category(master: pd.DataFrame) -> go.Figure:
    if master.empty or "Product_Category" not in master.columns:
        return px.bar(title="Average Cost by Product Category")
    df = (
        master.dropna(subset=["Product_Category"])
        .groupby("Product_Category")
        .agg(Avg_Cost=("Total_Delivery_Cost", "mean"))
        .reset_index()
    )
    fig = px.bar(
        df,
        x="Product_Category",
        y="Avg_Cost",
        title="Average Delivery Cost by Product Category",
        color="Avg_Cost",
        color_continuous_scale="Blues",
    )
    fig.update_layout(xaxis_title="Product Category", yaxis_title="Average Cost (INR)")
    return fig


def distance_cost_scatter(master: pd.DataFrame) -> go.Figure:
    if master.empty or "Distance_km" not in master.columns:
        return px.scatter(title="Distance vs Cost")
    fig = px.scatter(
        master,
        x="Distance_km",
        y="Total_Delivery_Cost",
        color="Priority" if "Priority" in master.columns else None,
        hover_data=["Order_ID", "Carrier", "Origin", "Destination"],
        title="Distance vs Total Delivery Cost",
        trendline="ols",
    )
    fig.update_layout(xaxis_title="Distance (km)", yaxis_title="Total Cost (INR)")
    return fig


def distance_emission_scatter(master: pd.DataFrame) -> go.Figure:
    if master.empty or "Estimated_CO2_kg" not in master.columns:
        return px.scatter(title="Distance vs Emissions")
    fig = px.scatter(
        master,
        x="Distance_km",
        y="Estimated_CO2_kg",
        color="Carrier" if "Carrier" in master.columns else None,
        hover_data=["Order_ID", "Priority"],
        title="Distance vs Estimated CO2 Emissions",
    )
    fig.update_layout(xaxis_title="Distance (km)", yaxis_title="CO2 (kg)")
    return fig


def lane_delay_heatmap(master: pd.DataFrame) -> go.Figure:
    if master.empty or "Origin" not in master.columns or "Destination" not in master.columns:
        return px.imshow([[0]], labels=dict(color="Avg Delay"), title="Lane Delay Heatmap")
    df = (
        master.groupby(["Origin", "Destination"])
        .agg(Avg_Delay=("Delivery_Delay_Days", "mean"))
        .reset_index()
    )
    pivot = df.pivot(index="Origin", columns="Destination", values="Avg_Delay").fillna(0)
    fig = px.imshow(
        pivot,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="RdBu",
        title="Average Delivery Delay by Lane (days)",
    )
    fig.update_layout(xaxis_title="Destination", yaxis_title="Origin")
    return fig


def inventory_heatmap(enriched_inventory: pd.DataFrame) -> go.Figure:
    if enriched_inventory.empty:
        return px.imshow([[0]], labels=dict(color="Stock Level"), title="Inventory Heatmap")
    pivot = (
        enriched_inventory.pivot_table(
            index="Warehouse",
            columns="Product_Category",
            values="Stock_Level",
            aggfunc="sum",
            fill_value=0,
        )
    )
    fig = px.imshow(
        pivot,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Viridis",
        title="Stock Levels by Warehouse & Category",
    )
    return fig


def storage_cost_bar(inventory: pd.DataFrame) -> go.Figure:
    if inventory.empty or "Storage_Cost_INR_per_unit" not in inventory.columns:
        return px.bar(title="Storage Cost by Warehouse")
    df = (
        inventory.groupby("Warehouse")
        .agg(Total_Storage_Cost=("Storage_Cost_INR_per_unit", "sum"))
        .reset_index()
    )
    fig = px.bar(
        df,
        x="Warehouse",
        y="Total_Storage_Cost",
        title="Storage Cost by Warehouse",
        color="Total_Storage_Cost",
        color_continuous_scale="Magma",
    )
    fig.update_layout(yaxis_title="Storage Cost (INR)")
    return fig


def cost_component_stacked(master: pd.DataFrame) -> go.Figure:
    cost_cols = [
        "Fuel_Cost_INR",
        "Labor_Cost_INR",
        "Maintenance_Cost_INR",
        "Insurance_Cost_INR",
        "Packaging_Cost_INR",
        "Technology_Fee_INR",
        "Other_Overhead_INR",
    ]
    available = [col for col in cost_cols if col in master.columns]
    if master.empty or not available:
        return px.bar(title="Cost Breakdown")
    df = master[["Order_ID"] + available].copy()
    df = df.melt(id_vars="Order_ID", value_vars=available, var_name="Cost_Component", value_name="Amount")
    fig = px.bar(
        df,
        x="Order_ID",
        y="Amount",
        color="Cost_Component",
        title="Cost Breakdown per Order",
    )
    fig.update_layout(xaxis_title="Order", yaxis_title="Amount (INR)")
    return fig


def rating_delay_scatter(feedback: pd.DataFrame, master: pd.DataFrame) -> go.Figure:
    if feedback.empty:
        return px.scatter(title="Customer Rating vs Delay")
    merged = feedback.merge(
        master[["Order_ID", "Delivery_Delay_Days", "Priority", "Carrier"]],
        on="Order_ID",
        how="left",
    )
    hover_cols: List[str] = ["Carrier"]
    if "Issue_Category" in merged.columns:
        hover_cols.append("Issue_Category")

    fig = px.scatter(
        merged,
        x="Delivery_Delay_Days",
        y="Rating",
        color="Priority",
        hover_data=hover_cols,
        title="Delivery Delay vs Customer Rating",
    )
    fig.update_layout(xaxis_title="Delay (days)", yaxis_title="Rating (1-5)")
    return fig
