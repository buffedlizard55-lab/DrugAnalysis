"""
Fetch daily stock price history from stockanalysis.com's public JSON API
(a widely used financial data aggregator that sources from exchange feeds).
Caches results locally as JSON so we don't re-fetch.
This script is meant to be invoked by the agent's fetch_page tool results,
piped in as raw JSON. Kept here for documentation/reproducibility.
"""
