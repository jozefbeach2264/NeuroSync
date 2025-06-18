import requests

# --- Configuration ---
base_url = "https://fapi.asterdex.com/fapi/v1/indexPriceKlines"
params = {
    "pair": "ETHUSDT",
    "interval": "1m",
    "startTime": 1718505600000,  # Replace with actual timestamp in ms
    "endTime": 1718505660000,    # Replace with actual timestamp in ms
    "limit": 1
}

# --- API Call ---
response = requests.get(base_url, params=params)

# --- Output ---
if response.status_code == 200:
    print("✅ Data:", response.json())
else:
    print("❌ Error:", response.status_code, response.text)