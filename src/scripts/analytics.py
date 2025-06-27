import pandas as pd
import logging
import typing
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

import datetime
from src.libs import utils
import src.libs.csvs as csvs
from src.scripts import link_purchases_to_offers

# 3. Time Analysis: Average Time to Sell
# Purpose: Understanding how long items take to sell helps you optimize your inventory and pricing strategy. Faster sales might indicate high demand or attractive pricing, while slower sales could point to inefficiencies or overpricing.

# How to calculate:

# Measure the difference between offer_date_created and offer_date_sold for sold items.

# Find the average duration across all sold items.

# Insights:

# Identify items that sell quickly or take a long time.

# Adjust pricing or strategies for slow-moving items.

# 5. Historical Trends: Monthly Profit Trends
# Purpose: Tracking monthly profits helps you monitor performance over time, spot trends, and detect seasonal impacts.

# How to analyze:

# Group your data by month using offer_date_sold.

# Sum profits for each month to observe growth or decline.

# Plot results to visualize trends and fluctuations.

# Insights:

# Understand whether profits are improving or declining.

# Pinpoint high-performing months and potential seasonal effects.

# 8. Item Condition & Wear Analysis
# Purpose: Examine how item wear impacts sales performance, profitability, and speed. This is especially relevant if item condition significantly influences buyer decisions.

# How to analyze:

# Segment items by wear values (e.g., low, medium, high).

# Compare metrics like profit, selling price, and time to sell for each segment.

# Insights:

# Determine whether items with higher wear values sell for less or take longer to sell.

# Adjust strategies for items based on their condition.

# 9. Profitability by Category
# Purpose: Understanding which categories (e.g., based on name) are most profitable helps you focus on the best-performing items.

# How to analyze:

# Group items by category (name).

# Calculate total profit, average profit, and selling frequency for each category.

# Rank categories to identify top performers.

# Insights:

# Highlight your most lucrative categories.

# Decide whether to focus more on specific categories or diversify.

__base_path__ = "./generated_files/analytics"

__time_to_sell_path__ = __base_path__ + "/time_to_sell.csv"
__available_offers_sorted_by_buy_date_path__ = __base_path__ + "/available_offers_sorted_by_buy_date.csv"
__available_offers_sorted_by_profit_path__ = __base_path__ + "/available_offers_sorted_by_profit.csv"
__sold_offers_sorted_by_date_sold_path__ = __base_path__ + "/sold_offers_sorted_by_date_sold.csv"
__sold_offers_sorted_by_profit_path__ = __base_path__ + "/sold_offers_sorted_by_profit.csv"
__monthly_stats_path__ = __base_path__ + "/monthly_stats.png"

def calculate_total_expense(linked_purchases_df: pd.DataFrame, state: typing.Literal["SOLD", "AVAILABLE"] | None = None, date: datetime.date | None = None) -> float:
    if state and date:
        total_expense = linked_purchases_df[(linked_purchases_df["state"] == state) & (linked_purchases_df["offer_date_sold"].dt.date > date)]["buy_price"].sum()
    elif date:
        total_expense = linked_purchases_df[linked_purchases_df["offer_date_sold"].dt.date >= date]["buy_price"].sum()
    elif state: 
        total_expense = linked_purchases_df[linked_purchases_df["state"] == state]["buy_price"].sum()
    else:
        total_expense = linked_purchases_df["buy_price"].sum()
    return round(total_expense, 2)

def calculate_total_sales_volume(linked_purchases_df: pd.DataFrame, state: typing.Literal["SOLD", "AVAILABLE"] | None = None, date: datetime.date | None = None) -> float:
    if state and date:
        sales_volume = linked_purchases_df[(linked_purchases_df["state"] == state) & (linked_purchases_df["offer_date_sold"].dt.date > date)]["selling_price"].sum()
    elif date:
        sales_volume = linked_purchases_df[linked_purchases_df["offer_date_sold"].dt.date >= date]["selling_price"].sum()
    elif state: 
        sales_volume = linked_purchases_df[linked_purchases_df["state"] == state]["selling_price"].sum()
    else:
        sales_volume = linked_purchases_df["selling_price"].sum()
    return round(sales_volume, 2)

def calculate_total_profit(linked_purchases_df: pd.DataFrame, state: typing.Literal["SOLD", "AVAILABLE"] | None = None, date: datetime.date | None = None) -> float:
    if state and date:
        total_profit_df = linked_purchases_df[(linked_purchases_df["state"] == state) & (linked_purchases_df["offer_date_sold"].dt.date > date)]["profit"].sort_values()
        total_profit = total_profit_df.sum()
    elif date:
        total_profit_df = linked_purchases_df[linked_purchases_df["offer_date_sold"].dt.date >= date]["profit"]
        total_profit = total_profit_df.sum()
    elif state: 
        total_profit_df = linked_purchases_df[linked_purchases_df["state"] == state]["profit"]
        total_profit = total_profit_df.sum()
    else:
        total_profit_df = linked_purchases_df["profit"]
        total_profit = total_profit_df.sum()
    return round(total_profit, 2)

def calculate_sales_volume_to_expense_ratio(total_expense, total_sales_volume):
    return round((total_sales_volume / total_expense) * 100, 2)

def calculate_profit_to_expense_ratio(total_expense, total_profit):
    return round((total_profit / total_expense) * 100, 2)

def calculate_profit_to_sales_volume_ratio(total_sales_volume, total_profit):
    return round((total_profit / total_sales_volume) * 100, 2)

def calculate_tradelocked_offers_ratio(linked_purchases_df: pd.DataFrame):
    available_offers_df = linked_purchases_df[linked_purchases_df["state"] == "AVAILABLE"]
    available_offers_count = len(available_offers_df)
    tradelocked_offers_df = available_offers_df[(available_offers_df["offer_date_trade_unlock"].notna()) & (available_offers_df["offer_date_trade_unlock"] > datetime.datetime.today())]
    tradelocked_offers_count = len(tradelocked_offers_df)
    return round((tradelocked_offers_count / available_offers_count) * 100, 2) 

def analyze_time_to_sell(linked_purchases_df: pd.DataFrame) -> pd.DataFrame:
    logging.debug("--> analyze_time_to_sell()")

    sold_items = linked_purchases_df[linked_purchases_df["time_to_sell"].notna()]
    analysis_df = sold_items.groupby("name").agg(
        avg_time_to_sell=("time_to_sell", "mean"),  # Calculate average time to sell
        sales_frequency=("name", "count"),  # Count occurrences (frequency)
        avg_profit=("profit", "mean")
    ).reset_index()
    analysis_df["avg_time_to_sell"] = analysis_df["avg_time_to_sell"].round(2)
    analysis_df["avg_profit"] = analysis_df["avg_profit"].round(2)
    analysis_df["total_profit"] = (analysis_df["avg_profit"] * analysis_df["sales_frequency"]).round(2)

    analysis_df["avg_time_to_sell"] = analysis_df["avg_time_to_sell"].replace(0, 0.01)
    analysis_df["efficiency"] = ((analysis_df["total_profit"] * 4) * (analysis_df["sales_frequency"] * 2)) / analysis_df["avg_time_to_sell"].round(2)

    # Optional normalization
    scaler = MinMaxScaler()
    analysis_df['efficiency'] = scaler.fit_transform(analysis_df[['efficiency']]).round(2)
    #analysis_df = analysis_df[analysis_df["sales_frequency"] > 1]

    analysis_df = analysis_df.sort_values(by=["efficiency", "total_profit"], ascending=[False, False]).reset_index(drop=True)

    logging.debug("<-- analyze_time_to_sell()")
    return analysis_df

def plot_monthly_stats(sold_offers_sorted_by_date_sold_df: pd.DataFrame):
    logging.info("--> plot_monthly_stats()")

    # Ensure offer_date_sold is in datetime format
    df = sold_offers_sorted_by_date_sold_df.copy()
    df['offer_date_sold'] = pd.to_datetime(df['offer_date_sold'], errors='coerce')
    
    # Drop rows with invalid dates
    logging.info("Drop rows with invalid dates")
    logging.debug("df len before: %s", len(df))
    df = df.dropna(subset=['offer_date_sold'])
    logging.debug("df len after: %s", len(df))
    
    # Add a column for the month (e.g., 2025-06)
    df['month'] = df['offer_date_sold'].dt.to_period('M').dt.to_timestamp()

    # Separate positive and negative profits
    df['profit'] = pd.to_numeric(df['profit'], errors='coerce')
    df = df.dropna(subset=['profit'])

    df['profit_positive'] = df['profit'].apply(lambda x: x if x > 0 else 0)
    df['profit_negative'] = df['profit'].apply(lambda x: x if x < 0 else 0)

    # Group by month and sum profits
    monthly_stats = df.groupby('month')[['profit_positive', 'profit_negative']].sum()

    # Plotting
    plt.figure(figsize=(12, 6))
    bar_width = 10  # in days, suitable for datetime x-axis

    plt.bar(
    monthly_stats.index,
    monthly_stats['profit_positive'],
    width=bar_width,
    label='Positive Profit',
    color='green',
    edgecolor='black',  # <-- outline
    align='center'
    )

    plt.bar(
        monthly_stats.index,
        monthly_stats['profit_negative'],
        width=bar_width,
        label='Negative Profit',
        color='red',
        edgecolor='black',  # <-- outline
        align='center'
    )

    # Annotate bars with values
    for idx, row in monthly_stats.iterrows():
        if row['profit_positive'] > 0:
            plt.text(idx, row['profit_positive'] + 10, f"{row['profit_positive']:.2f}",
                    ha='center', va='bottom', fontsize=9, color='black')
        if row['profit_negative'] < 0:
            plt.text(idx, row['profit_negative'] - 10, f"{row['profit_negative']:.2f}",
                    ha='center', va='top', fontsize=9, color='black')

    plt.xlabel('Month')
    plt.ylabel('Profit')
    plt.title('Monthly Sum of Positive and Negative Profits')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig(__monthly_stats_path__)
    plt.close()

def main(use_existing_linked_purchases: bool):

    if not use_existing_linked_purchases:
        link_purchases_to_offers.main()

    linked_purchases_df = csvs.read_linked_purchases()

    # FINANCIAL ANALYTICS
    logging.info("\nFINANCIAL ANALYTICS\n")
    
    total_expense = calculate_total_expense(linked_purchases_df)
    total_sales_volume = calculate_total_sales_volume(linked_purchases_df)
    total_profit = calculate_total_profit(linked_purchases_df)
    total_sales_volume_to_expense_ratio = calculate_sales_volume_to_expense_ratio(total_expense, total_sales_volume)
    total_profit_to_expense_ratio = calculate_profit_to_expense_ratio(total_expense, total_profit)
    total_profit_to_sales_volume_ratio = calculate_profit_to_sales_volume_ratio(total_sales_volume, total_profit)

    logging.info("total_expense: %s", total_expense)
    logging.info("total_sales_volume: %s", total_sales_volume)
    logging.info("total_profit: %s", total_profit)
    logging.info("total_sales_volume_to_expense_ratio: %s%%", total_sales_volume_to_expense_ratio)
    logging.info("total_profit_to_expense_ratio: %s%%", total_profit_to_expense_ratio)
    logging.info("total_profit_to_sales_volume_ratio: %s%%\n", total_profit_to_sales_volume_ratio)
    logging.info("------------------------------------------------------------------------------------------------\n")

    total_sales_expense = calculate_total_expense(linked_purchases_df, state="SOLD")
    total_fullfilled_sales_volume = calculate_total_sales_volume(linked_purchases_df, state="SOLD")
    total_fullfilled_profit = calculate_total_profit(linked_purchases_df, state="SOLD")
    fullfilled_sales_volume_to_expense_ratio = calculate_sales_volume_to_expense_ratio(total_sales_expense, total_fullfilled_sales_volume)
    fullfilled_profit_to_expense_ratio = calculate_profit_to_expense_ratio(total_sales_expense, total_fullfilled_profit)
    fullfilled_profit_to_sales_volume_ratio = calculate_profit_to_sales_volume_ratio(total_fullfilled_sales_volume, total_fullfilled_profit)

    logging.info("total_sales_expense: %s", total_sales_expense)
    logging.info("total_fullfilled_sales_volume: %s", total_fullfilled_sales_volume)
    logging.info("total_fullfilled_profit: %s", total_fullfilled_profit)
    logging.info("fullfilled_sales_volume_to_expense_ratio: %s%%", fullfilled_sales_volume_to_expense_ratio)
    logging.info("fullfilled_profit_to_expense_ratio: %s%%", fullfilled_profit_to_expense_ratio)
    logging.info("fullfilled_profit_to_sales_volume_ratio: %s%%\n", fullfilled_profit_to_sales_volume_ratio)
    logging.info("------------------------------------------------------------------------------------------------\n")

    total_available_items_expense = calculate_total_expense(linked_purchases_df, state="AVAILABLE")
    total_potential_sales_volume = calculate_total_sales_volume(linked_purchases_df, state="AVAILABLE")
    total_potential_profit = calculate_total_profit(linked_purchases_df, state="AVAILABLE")
    potential_sales_volume_to_expense_ratio = calculate_sales_volume_to_expense_ratio(total_available_items_expense, total_potential_sales_volume)
    potential_profit_to_expense_ratio = calculate_profit_to_expense_ratio(total_available_items_expense, total_potential_profit)
    potential_profit_to_sales_volume_ratio = calculate_profit_to_sales_volume_ratio(total_potential_sales_volume, total_potential_profit)

    logging.info("total_available_items_expense: %s", total_available_items_expense)
    logging.info("total_potential_sales_volume: %s", total_potential_sales_volume)
    logging.info("total_potential_profit: %s", total_potential_profit)
    logging.info("potential_sales_volume_to_expense_ratio: %s%%", potential_sales_volume_to_expense_ratio)
    logging.info("potential_profit_to_expense_ratio: %s%%", potential_profit_to_expense_ratio)
    logging.info("potential_profit_to_sales_volume_ratio: %s%%\n", potential_profit_to_sales_volume_ratio)
    logging.info("------------------------------------------------------------------------------------------------\n")

    # OFFER ANALYTICS
    logging.info("\nOFFER ANALYTICS\n")
    
    tradelocked_offers_ratio = calculate_tradelocked_offers_ratio(linked_purchases_df)
    logging.info("tradelocked_offers_ratio: %s%%\n", tradelocked_offers_ratio)
    
    logging.info("creating time to sell and total profit statistic")
    time_to_sell_df = analyze_time_to_sell(linked_purchases_df)
    csvs.save_df(time_to_sell_df, __time_to_sell_path__)
    
    logging.info("creating available offers sorted by buy date statistic")
    available_offers_df = linked_purchases_df[(linked_purchases_df["state"] == "AVAILABLE")].sort_values(by="buy_date", ascending=True).reset_index(drop=True)
    csvs.save_df(available_offers_df, __available_offers_sorted_by_buy_date_path__)

    logging.info("creating available offers sorted by profit statistic")
    available_offers_df = available_offers_df.sort_values(by="profit", ascending=False).reset_index(drop=True)
    csvs.save_df(available_offers_df, __available_offers_sorted_by_profit_path__)
    
    positive_profit = available_offers_df[available_offers_df["profit"] > 0]["profit"].sum()
    logging.info("\navailable offers positive profit: %s", positive_profit)
    negative_profit = available_offers_df[available_offers_df["profit"] < 0]["profit"].sum()
    logging.info("available offers negativeprofit: %s\n", negative_profit)
    
    logging.info("creating sold offers sorted by date sold statistic")
    sold_offers_df = linked_purchases_df[(linked_purchases_df["state"] == "SOLD")].sort_values(by="offer_date_sold", ascending=True).reset_index(drop=True)
    csvs.save_df(sold_offers_df, __sold_offers_sorted_by_date_sold_path__)

    logging.info("creating sold offers sorted by profit statistic")
    sold_offers_df = sold_offers_df.sort_values(by="profit", ascending=False).reset_index(drop=True)
    csvs.save_df(sold_offers_df, __sold_offers_sorted_by_profit_path__)

    positive_profit = sold_offers_df[sold_offers_df["profit"] > 0]["profit"].sum()
    logging.info("\nsold offers positive profit: %s", positive_profit)
    negative_profit = sold_offers_df[sold_offers_df["profit"] < 0]["profit"].sum()
    logging.info("sold offers negative profit: %s\n", negative_profit)

    sold_offers_sorted_by_date_sold_df = csvs.read_df(__sold_offers_sorted_by_date_sold_path__)
    plot_monthly_stats(sold_offers_sorted_by_date_sold_df)
