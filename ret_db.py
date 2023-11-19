from db_handlers import get_filtered_backtest_results
from itertools import groupby
from operator import itemgetter
import datetime
import pandas as pd


def get_trade_parameters():
    
    results = get_filtered_backtest_results()
    # Calculate the date 30 days ago
    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)

    # Filter results that are within the last 30 days
    recent_results = [
        result for result in results if result[10] >= thirty_days_ago]

    # Sort results by symbol, time frame, and datetime in descending order
    sorted_results = sorted(recent_results, key=lambda x: (
        x[1], x[2], x[10]), reverse=True)

    # Group by symbol and time frame and take the first entry from each group
    grouped_results = []
    for key, group in groupby(sorted_results, key=itemgetter(1, 2)):
        grouped_results.append(next(group))

    columns = ['id', 'symbol', 'timeframe', 'start_date', 'num_trades',
               'return_percentage', 'winrate', 'max_drawdown', 'tp_m', 'sl_m', 'created_at']

    # Create a DataFrame from the results
    df = pd.DataFrame(grouped_results, columns=columns)

    selected_columns = ['symbol', 'timeframe', 'tp_m', 'sl_m']
    data_list = df[selected_columns].to_dict(orient='records')

    return data_list
