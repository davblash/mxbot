import requests
import json

def get_contract_info(symbol: str):
    """
    Retrieve contract information for a given symbol from MEXC exchange.

    :param symbol: The trading pair symbol (e.g., "BTC_USDT").
    :return: Contract information as a dictionary or None if an error occurs.
    """
    if str == "":
        url = "https://contract.mexc.com/api/v1/contract/detail"
    else:
        url = f"https://contract.mexc.com/api/v1/contract/detail?symbol={symbol}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            return data.get("data")
        else:
            print(f"Error: {data.get('message')}")
            return None
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

if __name__ == "__main__":
    symbol = "BTC_USDT"  # Example symbol
    symbol = ""
    contract_info = get_contract_info(symbol)
    if contract_info:
        print("Contract Information:")
        print(contract_info)
        # write contract_info to json file
        with open('mexc_contract_info.json', 'w') as f:
            json.dump(contract_info, f)
    else:
        print("Failed to retrieve contract information.")