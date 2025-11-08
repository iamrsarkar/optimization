# NexGen Logistics Analytics & Optimization App

## Case Study Overview
NexGen Logistics operates a multi-city warehousing and transportation network serving enterprise, SMB and individual customers across India and connected hubs in Singapore, Dubai, Hong Kong and Bangkok. The company manages more than 200 monthly orders across diverse product categories and relies on a mixed fleet and external carrier partners to deliver on varying service priorities.

## Problem Focus
This project delivers a unified Streamlit application that addresses:

1. **Smart Route Planner** – Analyse current lanes, carriers and orders with respect to cost, delays and emissions, apply user-defined objective weights, and rank routes to prioritise operational improvements.
2. **Warehouse Optimization Tool** – Evaluate warehouse inventory health, measure stock coverage versus demand, and recommend both transfer rebalancing actions and reorder quantities to minimise stock-outs and excess holding cost.

## Project Structure
```
.
├── app.py                    # Streamlit entry point with UI, navigation, KPIs and visualisations
├── config.py                 # Global constants (warehouses, priorities, defaults)
├── data_loader.py            # CSV ingestion, cleaning and master order preparation
├── eda_utils.py              # Global filtering and KPI helper functions
├── route_planner.py          # Route scoring, ranking and lane summarisation logic
├── warehouse_optimizer.py    # Inventory analytics, transfer and reorder heuristics
├── viz_utils.py              # Plotly-based reusable chart builders
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
└── innovation_brief.md       # Executive innovation brief
```

## Installation
1. Ensure Python 3.9+ is available.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the App
Launch the Streamlit interface:
```bash
streamlit run app.py
```

## App Navigation & Features
- **Global Filters (Sidebar):** Date range, priority, product category, origin, destination and customer segment filters cascade across all tabs and analytics.
- **Overview & KPIs:** Displays demand, revenue, delivery reliability, average delay, emissions and interactive charts (weekly trends, on-time rate, cost per category) plus carrier-level service performance.
- **Route Analytics & Smart Planner:** Presents lane heatmaps, distance-cost/emission scatter plots and a weighted route scoring engine. Users adjust cost/time/emission weights, recompute rankings, inspect best vs worst routes, view lane summaries and download recommendations.
- **Warehouse Optimization:** Highlights inventory heatmaps, storage cost bars, enriched stock coverage tables, and produces suggested transfer and reorder plans that can be exported as CSV files.
- **Cost & Sustainability Insights:** Provides stacked cost breakdowns, emissions summaries by origin and a ranked list of high-cost/high-emission lanes for targeted action.
- **Customer Experience:** Correlates delivery delays with customer ratings, tracks sentiment themes from feedback text and summarises satisfaction by issue category.

## Key Assumptions
- **CO₂ Estimation:** When specific vehicle assignments are unavailable, emissions per order are estimated using the average `CO2_kg_per_km` across the fleet (fallback of 0.65 kg/km if not provided).
- **Demand Estimation:** Warehouse demand leverages filtered order history; stock cover assumes a 30-day lookback and flags stock cover below 7 days as under-stock.
- **Transfer & Reorder Heuristics:** Transfers move surplus inventory (stock well above reorder level or demand) to understocked warehouses. Reorder quantities target the greater of the reorder level or recent demand plus a 5-unit buffer.

## Data Gaps & Handling
- Missing CSV files or unmatched joins are handled gracefully, producing empty data frames with clear on-screen messaging.
- All date fields are parsed with coercion; invalid dates become NaT and are ignored in time-based analyses.
- Normalisation for route scoring uses min-max scaling with safe defaults when variance is zero.

## Extensibility
Future enhancements could include integrating real-time telematics, machine learning-based delay prediction, mixed-integer optimisation for routing and replenishment, and automated alerting workflows.
