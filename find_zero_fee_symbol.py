import json

# Load the JSON file
with open('/root/surf/mexc/mexc_contract_info.json', 'r') as file:
    data = json.load(file)

# Find symbols with 'takerFeeRate' equal to 0
zero_fee_symbols = [item['symbol'] for item in data if item.get('takerFeeRate') == 0]

# Print the results
result = "\n".join([s for s in zero_fee_symbols])
print("Symbols with zero taker fee rate:\n", result)

with open('mexc_zero_fee_symbols.txt', 'wt') as f:
    f.write(result)