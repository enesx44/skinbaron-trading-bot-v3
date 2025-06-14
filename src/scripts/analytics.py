import pandas as pd
import logging
import typing

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

__base_path_linked_purchases__ = "./generated_files/link_purchases_to_offers"
__linked_purchases_path__ = __base_path_linked_purchases__ + "/linked_purchases.csv"

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
        profit=("profit", "mean")
    ).reset_index()
    analysis_df["avg_time_to_sell"] = analysis_df["avg_time_to_sell"].round(2)
    analysis_df["profit"] = analysis_df["profit"].round(2)
    analysis_df["total_profit"] = analysis_df["profit"] * analysis_df["sales_frequency"]
    analysis_df = analysis_df.sort_values(by=["total_profit", "avg_time_to_sell"], ascending=[False, True]).reset_index(drop=True)

    logging.debug("<-- analyze_time_to_sell()")
    return analysis_df

def main(use_existing_linked_purchases: bool):

    if not use_existing_linked_purchases:
        link_purchases_to_offers.main()

    linked_purchases_df = csvs.read_linked_purchases()

    # FINANCIAL ANALYTICS
    logging.info("FINANCIAL ANALYTICS")
    
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
    logging.info("------------------------------------------------------------------------------------------------")

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
    logging.info("------------------------------------------------------------------------------------------------")

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
    logging.info("------------------------------------------------------------------------------------------------")

    for n in [1, 3, 6, 12, 24]:
        total_sales_expense = calculate_total_expense(linked_purchases_df, state="SOLD", date=utils.get_date_n_months_ago(n))
        total_fullfilled_sales_volume = calculate_total_sales_volume(linked_purchases_df, state="SOLD", date=utils.get_date_n_months_ago(n))
        total_fullfilled_profit = calculate_total_profit(linked_purchases_df, state="SOLD", date=utils.get_date_n_months_ago(n))
        fullfilled_sales_volume_to_expense_ratio = calculate_sales_volume_to_expense_ratio(total_sales_expense, total_fullfilled_sales_volume)
        fullfilled_profit_to_expense_ratio = calculate_profit_to_expense_ratio(total_sales_expense, total_fullfilled_profit)
        fullfilled_profit_to_sales_volume_ratio = calculate_profit_to_sales_volume_ratio(total_fullfilled_sales_volume, total_fullfilled_profit)

        logging.info("last %s month(s):", n)
        logging.info("total_sales_expense: %s", total_sales_expense)
        logging.info("total_fullfilled_sales_volume: %s", total_fullfilled_sales_volume)
        logging.info("total_fullfilled_profit: %s", total_fullfilled_profit)
        logging.info("fullfilled_sales_volume_to_expense_ratio: %s%%", fullfilled_sales_volume_to_expense_ratio)
        logging.info("fullfilled_profit_to_expense_ratio: %s%%", fullfilled_profit_to_expense_ratio)
        logging.info("fullfilled_profit_to_sales_volume_ratio: %s%%\n", fullfilled_profit_to_sales_volume_ratio) 
        logging.info("------------------------------------------------------------------------------------------------")

    # OFFER ANALYTICS
    logging.info("OFFER ANALYTICS")
    
    time_to_sell_df = analyze_time_to_sell(linked_purchases_df)
    logging.info("offers sorted by time to sell and total profit: \n%s", time_to_sell_df.to_string())

    tradelocked_offers_ratio = calculate_tradelocked_offers_ratio(linked_purchases_df)
    logging.info("tradelocked_offers_ratio: %s%%", tradelocked_offers_ratio)
    
    available_offers_df = linked_purchases_df[(linked_purchases_df["state"] == "AVAILABLE")].sort_values(by="buy_date", ascending=True).reset_index(drop=True)
    logging.info("avialable offers sorted by buy date: \n%s", available_offers_df.to_string())
    logging.info("avialable offers sorted by profit: \n%s", available_offers_df.sort_values(by="profit", ascending=False).reset_index(drop=True).to_string())
    
    sold_offers_df = linked_purchases_df[(linked_purchases_df["state"] == "SOLD")].sort_values(by="buy_date", ascending=True).reset_index(drop=True)
    logging.info("sold offers sorted by buy date: \n%s", sold_offers_df.to_string())
    logging.info("sold offers sorted by sold date: \n%s", sold_offers_df.sort_values(by="offer_date_sold", ascending=True).reset_index(drop=True).to_string())
    logging.info("sold offers sorted by profit: \n%s", sold_offers_df.sort_values(by="profit", ascending=False).reset_index(drop=True).to_string())


