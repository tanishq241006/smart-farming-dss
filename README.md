# Smart Farming Decision Support System

## MVP status

After sign-in, farmers enter their state, district, crop, farm size, water access, and soil type. The district list updates immediately when the state changes. The dashboard saves this profile locally, starts with the farmer's crop and area selected, and highlights the highest reported modal price in the home district when the selected data contains a match. Otherwise, it shows the top market in the active filters. This is a price comparison only: transport, quality, arrivals, and crop suitability still need to be considered. The dashboard also offers filters by crop, state, district, and variety; comparison exports; local current weather; and a five-day forecast. A bundled 14 October 2026 daily snapshot is compared with the default 15 October snapshot to show matched market price movement. Weather uses Open-Meteo. The live price panel uses the public Mandi API below without a key and checks for reports every five minutes; the service updates its reports on its own schedule, so this is not an intraday trading feed. Accounts and farm profiles are stored locally in `app_users.sqlite3`; passwords are stored as salted PBKDF2 hashes. The dashboard uses the bundled `CROP DATA.csv` file for its historical market comparisons; CSV upload is not available in the interface.

The default file has 19,014 records for 15 October 2026. A supplied 14 October snapshot is included as a separate comparison file; matching market/crop/variety/grade records are used to show daily price movement. Two days of prices are still not enough to train or validate a forecast. The dashboard reports this limitation instead of presenting an untrained model as a prediction.

The supplied research paper, [Agentic AI-driven autonomous decision support system for smart agriculture](https://doi.org/10.1038/s41598-026-39472-w), is useful as a design reference for combining soil measurements, crop context, weather, and explanations. Its described crop and fertilizer models require measured NPK and pH data plus domain validation. Those models are not trained or reproduced here; soil type alone is not enough to make crop or fertilizer recommendations safely.

This local account flow is for a classroom/demo MVP. Before hosting the app publicly, replace it with a reviewed authentication service and configure production secrets and access controls.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## Live data setup

Weather works without a key and uses the selected district and state to locate a forecast. The live price source is the [Mandi API](https://mandi-api.onrender.com/v1/prices?state=Maharashtra&commodity=Onion), which does not require a user-provided API key. The app uses its `/states`, `/commodities`, and `/markets` endpoints for live filters, `/prices` for market/variety/date-filtered records, and `/prices/history` for state averages or a selected mandi trend. The API documents five supported states and a limit of 100 requests per 15 minutes; lookup lists are cached for six hours, prices for five minutes, and history for 15 minutes. Its current Maharashtra commodity list omits Onion even though `/prices` returns Onion records, so the crop selector also includes the local dataset's crop names. Use **Refresh now** to clear the live source cache. Weather is cached for 15 minutes.

## Data expected

CSV columns: `State`, `District`, `Market`, `Commodity`, `Arrival_Date`, and `Modal_x0020_Price` (or `Modal Price`). Minimum and maximum price columns are used when present.

## Next development steps

1. Collect multiple dates for the same crop and market; record the source and download date.
2. Validate duplicates, missing values, date ranges, price units, and market/crop name consistency.
3. Add a simple baseline forecast and compare it with a time-aware holdout split before selecting a model.
4. Add recommendation features only after assembling verified product labels and crop/pest restrictions. Keep label and safety checks rule-based and get agronomy review; machine learning should not invent pesticide use or dosage advice.
