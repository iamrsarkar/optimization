"""Streamlit app for NexGen Logistics analytics and optimization."""
from __future__ import annotations

import io
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import config
from data_loader import create_master_orders, load_all_data
from eda_utils import apply_global_filters, calculate_overall_kpis, summarise_on_time_by_group
from route_planner import RouteWeights, best_and_worst_routes, compute_route_scores, summarise_lane_performance
from warehouse_optimizer import analyse_inventory, recommend_reorders, recommend_transfers
import viz_utils


st.set_page_config(page_title="NexGen Logistics Control Tower", layout="wide")
st.title("NexGen Logistics Control Tower")
st.caption("End-to-end visibility for routing, warehouse, cost and customer experience.")


def _get_date_bounds(master: pd.DataFrame) -> tuple[date, date]:
    if master.empty or "Order_Date" not in master.columns:
        today = date.today()
        return today.replace(day=1), today
    min_date = master["Order_Date"].min()
    max_date = master["Order_Date"].max()
    if pd.isna(min_date) or pd.isna(max_date):
        today = date.today()
        return today.replace(day=1), today
    return min_date.date(), max_date.date()


def _convert_date_input(value: tuple[date, date]) -> tuple[pd.Timestamp, pd.Timestamp]:
    start, end = value
    return pd.to_datetime(start), pd.to_datetime(end)


def _download_button(label: str, df: pd.DataFrame, file_name: str) -> None:
    if df.empty:
        st.info("No data available for download.")
        return
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(label=label, data=csv_buffer.getvalue(), file_name=file_name, mime="text/csv")


@st.cache_data(show_spinner=False)
def _load_data() -> dict[str, pd.DataFrame]:
    return load_all_data()


def main() -> None:
    data = _load_data()
    master = create_master_orders(data)

    if master.empty:
        st.error("Master dataset could not be created. Please ensure CSV files are available.")
        return

    st.sidebar.header("Global Filters")
    min_date, max_date = _get_date_bounds(master)
    date_selection = st.sidebar.date_input("Order Date Range", (min_date, max_date))
    if isinstance(date_selection, tuple) and len(date_selection) == 2:
        start_ts, end_ts = _convert_date_input(date_selection)
    else:
        start_ts, end_ts = pd.to_datetime(min_date), pd.to_datetime(max_date)

    priorities = st.sidebar.multiselect("Priority", options=sorted(master["Priority"].dropna().unique()), default=None)
    products = st.sidebar.multiselect(
        "Product Category", options=sorted(master["Product_Category"].dropna().unique()), default=None
    )
    origins = st.sidebar.multiselect("Origin Warehouse", options=sorted(master["Origin"].dropna().unique()), default=None)
    destinations = st.sidebar.multiselect(
        "Destination", options=sorted(master["Destination"].dropna().unique()), default=None
    )
    segments = st.sidebar.multiselect(
        "Customer Segment", options=sorted(master["Customer_Segment"].dropna().unique()), default=None
    )

    filtered_master = apply_global_filters(
        master,
        (start_ts, end_ts),
        priorities=priorities,
        products=products,
        origins=origins,
        destinations=destinations,
        segments=segments,
    )

    st.sidebar.markdown("---")
    _download_button("Download Filtered Master Data", filtered_master, "filtered_master_orders.csv")

    overview_tab, route_tab, warehouse_tab, cost_tab, cx_tab = st.tabs(
        [
            "Overview & KPIs",
            "Route Analytics & Smart Planner",
            "Warehouse Optimization",
            "Cost & Sustainability Insights",
            "Customer Experience",
        ]
    )

    with overview_tab:
        st.subheader("Key Performance Indicators")
        kpis = calculate_overall_kpis(filtered_master)
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Orders", f"{kpis['total_orders']:,}")
        col2.metric("Total Revenue (INR)", f"{kpis['total_revenue']:,.0f}")
        on_time_display = "N/A" if np.isnan(kpis["on_time_rate"]) else f"{kpis['on_time_rate']:.0%}"
        col3.metric("On-Time Delivery Rate", on_time_display)
        col4.metric("Avg Delay (days)", f"{kpis['avg_delay']:.2f}" if not np.isnan(kpis["avg_delay"]) else "N/A")
        col5.metric("Total CO₂ (kg)", f"{kpis['total_emissions']:,.0f}")

        st.plotly_chart(viz_utils.orders_over_time(filtered_master), use_container_width=True)

        kpi_cols = st.columns(2)
        kpi_cols[0].plotly_chart(viz_utils.on_time_by_priority(filtered_master), use_container_width=True)
        kpi_cols[1].plotly_chart(viz_utils.cost_by_category(filtered_master), use_container_width=True)

        st.markdown("### On-Time Performance by Carrier")
        carrier_perf = summarise_on_time_by_group(filtered_master, "Carrier")
        if carrier_perf.empty:
            st.info("No carrier performance data available for the selected filters.")
        else:
            st.dataframe(carrier_perf)

    with route_tab:
        st.subheader("Route Performance Analytics")
        st.plotly_chart(viz_utils.lane_delay_heatmap(filtered_master), use_container_width=True)

        scatter_cols = st.columns(2)
        scatter_cols[0].plotly_chart(viz_utils.distance_cost_scatter(filtered_master), use_container_width=True)
        scatter_cols[1].plotly_chart(viz_utils.distance_emission_scatter(filtered_master), use_container_width=True)

        st.markdown("---")
        st.subheader("Smart Route Planner")
        st.write("Adjust weights to prioritise cost, speed or sustainability. Recompute to refresh rankings.")

        cw = st.slider("Cost Weight", 0.0, 1.0, float(config.DEFAULT_ROUTE_WEIGHT[0]), 0.05)
        tw = st.slider("Delay Weight", 0.0, 1.0, float(config.DEFAULT_ROUTE_WEIGHT[1]), 0.05)
        ew = st.slider("Emission Weight", 0.0, 1.0, float(config.DEFAULT_ROUTE_WEIGHT[2]), 0.05)
        total_weight = cw + tw + ew
        if total_weight == 0:
            st.warning("At least one weight must be greater than zero.")
        else:
            normalized_weights = RouteWeights(cw / total_weight, tw / total_weight, ew / total_weight)
            recompute = st.button("Recompute Route Scores")
            weight_tuple = normalized_weights.as_tuple()
            filter_signature = hash(
                (
                    tuple(filtered_master["Order_ID"]) if not filtered_master.empty else (),
                    weight_tuple,
                )
            )
            if (
                recompute
                or "route_scores" not in st.session_state
                or st.session_state.get("route_score_signature") != filter_signature
            ):
                try:
                    scored_routes = compute_route_scores(filtered_master, normalized_weights)
                except ValueError as err:
                    st.error(str(err))
                    scored_routes = pd.DataFrame()
                st.session_state["route_scores"] = scored_routes
                st.session_state["route_score_signature"] = filter_signature
            scored_routes = st.session_state.get("route_scores", pd.DataFrame())

            if scored_routes.empty:
                st.info("No route scores available for the selected filters.")
            else:
                st.success("Route scores refreshed with current weights.")
                extremes = best_and_worst_routes(scored_routes, top_n=10)
                col_best, col_worst = st.columns(2)
                col_best.markdown("#### Best Routes")
                col_best.dataframe(extremes["best"])
                col_worst.markdown("#### Worst Routes")
                col_worst.dataframe(extremes["worst"])

                lane_summary = summarise_lane_performance(filtered_master)
                st.markdown("### Lane Summary (Origin-Destination-Carrier)")
                st.dataframe(lane_summary)

                _download_button("Download Route Recommendations", scored_routes, "route_recommendations.csv")

    with warehouse_tab:
        st.subheader("Inventory Health")
        inventory = data.get("warehouse_inventory", pd.DataFrame())
        orders_df = filtered_master[[
            "Order_ID",
            "Origin",
            "Product_Category",
            "Order_Value_INR",
        ]].copy() if not filtered_master.empty else pd.DataFrame()
        if not products:
            filtered_inventory = inventory.copy()
        else:
            filtered_inventory = inventory[inventory["Product_Category"].isin(products)]

        enriched_inventory = analyse_inventory(filtered_inventory, orders_df)
        if enriched_inventory.empty:
            st.info("No inventory data available.")
        else:
            st.plotly_chart(viz_utils.inventory_heatmap(enriched_inventory), use_container_width=True)
            st.plotly_chart(viz_utils.storage_cost_bar(filtered_inventory), use_container_width=True)

            st.markdown("### Inventory Details")
            st.dataframe(enriched_inventory)

            transfer_plan = recommend_transfers(enriched_inventory)
            reorder_plan = recommend_reorders(enriched_inventory)

            plan_cols = st.columns(2)
            with plan_cols[0]:
                st.markdown("#### Suggested Transfer Plan")
                if transfer_plan.empty:
                    st.info("No transfer recommendations based on current data.")
                else:
                    st.dataframe(transfer_plan)
                    _download_button("Download Transfer Plan", transfer_plan, "transfer_plan.csv")

            with plan_cols[1]:
                st.markdown("#### Reorder Recommendations")
                if reorder_plan.empty:
                    st.info("No reorder recommendations.")
                else:
                    st.dataframe(reorder_plan)
                    _download_button("Download Reorder Plan", reorder_plan, "reorder_plan.csv")

    with cost_tab:
        st.subheader("Cost and Sustainability Insights")
        st.plotly_chart(viz_utils.cost_component_stacked(filtered_master), use_container_width=True)

        if "Estimated_CO2_kg" in filtered_master.columns and not filtered_master.empty:
            emissions_by_origin = (
                filtered_master.groupby("Origin")
                .agg(Total_CO2=("Estimated_CO2_kg", "sum"), Avg_CO2_per_km=("Estimated_CO2_kg", "mean"))
                .reset_index()
            )
            st.markdown("### Emissions by Origin Warehouse")
            st.dataframe(emissions_by_origin)

        high_cost_lanes = (
            filtered_master.groupby(["Origin", "Destination"])
            .agg(Avg_Cost=("Total_Delivery_Cost", "mean"), Avg_CO2=("Estimated_CO2_kg", "mean"))
            .reset_index()
            .sort_values("Avg_Cost", ascending=False)
            .head(10)
        )
        st.markdown("### High-Cost / High-Emission Lanes")
        if high_cost_lanes.empty:
            st.info("No lane cost data available.")
        else:
            st.dataframe(high_cost_lanes)

    with cx_tab:
        st.subheader("Customer Experience Insights")
        feedback = data.get("customer_feedback", pd.DataFrame())
        if feedback.empty:
            st.info("No customer feedback data available.")
        else:
            if "Feedback_Date" in feedback.columns:
                st.markdown("Average Rating Over Time")
                feedback_time = (
                    feedback.dropna(subset=["Feedback_Date"])
                    .groupby(pd.Grouper(key="Feedback_Date", freq="W"))
                    .agg(Avg_Rating=("Rating", "mean"))
                    .reset_index()
                )
                st.line_chart(feedback_time.set_index("Feedback_Date"))

            st.plotly_chart(viz_utils.rating_delay_scatter(feedback, filtered_master), use_container_width=True)

            if "Feedback_Text" in feedback.columns:
                words = (
                    feedback["Feedback_Text"].dropna().str.lower().str.replace(r"[^a-zA-Z0-9 ]", "", regex=True).str.split()
                )
                word_counts = {}
                for word_list in words:
                    for word in word_list:
                        if len(word) <= 3:
                            continue
                        word_counts[word] = word_counts.get(word, 0) + 1
                if word_counts:
                    top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:20]
                    top_words_df = pd.DataFrame(top_words, columns=["Word", "Frequency"])
                    st.markdown("### Frequent Feedback Themes")
                    st.bar_chart(top_words_df.set_index("Word"))

            rating_by_issue = (
                feedback.groupby("Issue_Category")
                .agg(Avg_Rating=("Rating", "mean"), Feedback_Count=("Feedback_ID", "count"))
                .reset_index()
                .sort_values("Avg_Rating")
            )
            st.markdown("### Rating by Issue Category")
            st.dataframe(rating_by_issue)


if __name__ == "__main__":
    main()
