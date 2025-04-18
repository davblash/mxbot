import pandas as pd
import json
import requests

url = "https://contract.mexc.com/api/v1/contract/ticker"

with open('mexc_zero_fee_symbols.txt', 'rt') as f:
    zero_fee_symbols = f.readlines()

zero_fee_symbols = [s.strip() for s in zero_fee_symbols]

# Get contract info
with open('mexc_contract_info.json', 'r') as f:
    contract_info = json.load(f)

# Get ticker data for all symbols
response = requests.get(url)
data = response.json()
assert data["success"] == True and data["code"] == 0
all_tickers = data["data"]

symbol_data = {}
for s in zero_fee_symbols:
    for item in contract_info:
        if item["symbol"] == s:
            tick = item["priceUnit"]
            break
    for item in all_tickers:
        if item["symbol"] == s:
            lastPrice = item["lastPrice"]
    symbol_data[s] = {"price": lastPrice, "tickSize": tick}

#print(symbol_data)
df = pd.DataFrame(symbol_data)
df = df.transpose()
df["tickRatio"] = df["tickSize"] / df["price"]
print(df["tickRatio"])
print(df["tickRatio"].describe())
# select rows of df where tickRatio <= 0.0001
df = df[df["tickRatio"] <= 0.0001]
#print(df.where(df["tickRatio"] <= 0.0001))
print(df)


