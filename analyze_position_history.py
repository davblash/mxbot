import re
import pandas as pd
from mexc_history_positions import get_history_positions
import pathlib

def get_position_ids(log_file_path):
    # Pattern to match the desired lines and extract the position ID
    pattern = r"Order filled successfully\. Position ID: (\d+)"

    # List to store extracted position IDs
    position_ids = []

    # Read the log file and extract matching lines
    with open(log_file_path, "r") as log_file:
        for line in log_file:
            match = re.search(pattern, line)
            if match:
                position_ids.append(match.group(1))

    # Print the extracted position IDs
    #print("Extracted Position IDs:", position_ids)
    position_ids = [int(x) for x in position_ids]
    return position_ids

def extract_position_history(position_ids, symbol):
    # List to store position history for the given symbol
    position_history = []

    # Fetch position history for each position ID
    found = {id: False for id in position_ids}
    n_found = 0
    page_size = 100
    page_num = 1
    while n_found < len(position_ids):
        response = get_history_positions(symbol, API_KEY, SECRET_KEY)
        if response["success"]:
            if response["code"] == 0:
                data = response["data"]
                for item in data:
                    position_id = item["positionId"]
                    if position_id in position_ids:
                        if not found[position_id]:
                            position_history.append(item)
                            found[position_id] = True
                            n_found += 1
                page_num += 1
            else:
                break
        else:
            break
    
    df = pd.DataFrame(position_history)
    # Drop unnecessary columns
    df.drop(columns=["openType", "state", "holdVol", "frozenVol", "closeVol", \
                     "holdAvgPrice", "openAvgPriceFullyScale", "newOpenAvgPrice", "newCloseAvgPrice", \
                     "holdAvgPriceFullyScale", "deductFeeList", "liquidatePrice", "im", "holdFee", "autoAddIm"], inplace=True)

    # Convert createTime field to datetime
    df["createTime"] = pd.to_datetime(df["createTime"], unit="ms")
    df["updateTime"] = pd.to_datetime(df["updateTime"], unit="ms")

    # Rename columns
    df.rename(columns={"positionType": "direction"}, inplace=True)

    # Map direction values to human-readable strings
    df["direction"] = df["direction"].map({1: "Long", 2: "Short"})

    df.set_index("positionId", inplace=True)
    df.sort_values(by="createTime", inplace=True)

    return df

if __name__ == "__main__":
    API_KEY = 'mx0vgldfeNOhoYdin6'
    SECRET_KEY = '6c6bef17d51341d98f6296f51eca3a98'

    log_file_path = "log/log_2025-03-26-134122.log"
    position_ids = get_position_ids(log_file_path)
    
    symbol = 'ADA_USDT'
    position_history = extract_position_history(position_ids, symbol)

    # Save position history to a CSV file
    pathlib.Path('history').mkdir(parents=True, exist_ok=True)
    filename = pathlib.Path(log_file_path).stem
    #position_history.to_csv('history/position_history.csv')
    position_history.to_csv(f'history/{filename}.csv')
    print(position_history)
