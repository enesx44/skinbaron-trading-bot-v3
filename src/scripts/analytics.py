import pandas as pd
import logging
import typing
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

import datetime
import src.libs.csvs as csvs
from src.scripts import link_purchases_to_offers

# 8. Item Condition & Wear Analysis
# Purpose: Examine how item wear impacts sales performance, profitability, and speed. This is especially relevant if item condition significantly influences buyer decisions.

# How to analyze:

# Segment items by wear values (e.g., low, medium, high).

# Compare metrics like profit, selling price, and time to sell for each segment.

# Insights:

# Determine whether items with higher wear values sell for less or take longer to sell.

# Adjust strategies for items based on their condition.

__base_path__ = "./generated_files/analytics"

__time_to_sell_path__ = __base_path__ + "/time_to_sell.csv"
__available_offers_sorted_by_buy_date_path__ = __base_path__ + "/available_offers_sorted_by_buy_date.csv"
__available_offers_sorted_by_profit_path__ = __base_path__ + "/available_offers_sorted_by_profit.csv"
__sold_offers_sorted_by_date_sold_path__ = __base_path__ + "/sold_offers_sorted_by_date_sold.csv"
__sold_offers_sorted_by_profit_path__ = __base_path__ + "/sold_offers_sorted_by_profit.csv"
__monthly_stats_path__ = __base_path__ + "/monthly_stats.png"
__detailed_month_stats_path__ = __base_path__ + "/detailed_month.png"
__available_offers_length_of_stay_path__ = __base_path__ + "/available_offers_length_of_stay.png"

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

    analysis_df["avg_time_to_sell"] = analysis_df["avg_time_to_sell"].replace(0, 1)
    analysis_df["efficiency"] = ((analysis_df["total_profit"] ** 5) * (analysis_df["sales_frequency"] ** 2)) / (analysis_df["avg_time_to_sell"] ** 2).round(5)

    # Optional normalization
    scaler = MinMaxScaler()
    analysis_df['efficiency'] = scaler.fit_transform(analysis_df[['efficiency']]).round(5)
    #analysis_df = analysis_df[analysis_df["sales_frequency"] > 1]

    analysis_df = analysis_df.sort_values(by=["efficiency", "total_profit"], ascending=[False, False]).reset_index(drop=True)

    logging.debug("<-- analyze_time_to_sell()")
    return analysis_df


def plot_month_detailed(sold_offers_sorted_by_date_sold_df: pd.DataFrame, month_str: str = None):
    """
    Plots daily profits for a given month. Defaults to current month if month_str is None.
    
    :param sold_offers_sorted_by_date_sold_df: DataFrame with columns 'offer_date_sold' and 'profit'
    :param month_str: optional string in format 'YYYY-MM', e.g., '2025-07'
    """
    if month_str:
        logging.info("--> plot_month_detailed() for %s", month_str)
        try:
            month_start = pd.to_datetime(month_str + "-01")
        except Exception as e:
            logging.error("Invalid month string '%s': %s", month_str, e)
            return
    else:
        today = pd.Timestamp.today()
        month_start = today.replace(day=1)
        logging.info("--> plot_month_detailed() for current month %s", month_start.strftime("%Y-%m"))

    next_month_start = month_start + pd.offsets.MonthBegin(1)

    df = sold_offers_sorted_by_date_sold_df.copy()
    df['offer_date_sold'] = pd.to_datetime(df['offer_date_sold'], errors='coerce')
    df = df.dropna(subset=['offer_date_sold'])
    logging.debug("df shape after dropping invalid dates: %s", df.shape)

    # --- Filter only the target month ---
    df = df[(df['offer_date_sold'] >= month_start) & (df['offer_date_sold'] < next_month_start)]
    logging.debug("df shape after filtering for month: %s", df.shape)
    if df.empty:
        logging.warning("No sales for month %s.", month_start.strftime("%Y-%m"))
        return

    # --- Profit ---
    df['profit'] = pd.to_numeric(df['profit'], errors='coerce')
    df = df.dropna(subset=['profit'])
    df['profit_positive'] = df['profit'].apply(lambda x: x if x > 0 else 0)
    df['profit_negative'] = df['profit'].apply(lambda x: x if x < 0 else 0)

    # --- Group by day ---
    df['day'] = df['offer_date_sold'].dt.to_period('D').dt.to_timestamp()
    daily_stats = df.groupby('day')[['profit_positive', 'profit_negative']].sum()
    logging.debug("Daily stats:\n%s", daily_stats)

    # --- Plot ---
    plt.figure(figsize=(12, 6))
    bar_width = 0.8

    plt.bar(
        daily_stats.index,
        daily_stats['profit_positive'],
        width=bar_width,
        label='Positive Profit',
        color='green',
        edgecolor='black'
    )
    plt.bar(
        daily_stats.index,
        daily_stats['profit_negative'],
        width=bar_width,
        label='Negative Profit',
        color='red',
        edgecolor='black'
    )

    # Annotate bars
    for idx, row in daily_stats.iterrows():
        if row['profit_positive'] > 0:
            plt.text(idx, row['profit_positive'] + 0.5, f"{row['profit_positive']:.2f}",
                     ha='center', va='bottom', fontsize=8)
        if row['profit_negative'] < 0:
            plt.text(idx, row['profit_negative'] - 0.5, f"{row['profit_negative']:.2f}",
                     ha='center', va='top', fontsize=8)

    plt.xlabel('Day')
    plt.ylabel('Profit')
    plt.title(f'Daily Profits for {month_start.strftime("%B %Y")}')
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(__detailed_month_stats_path__)
    plt.close()
    logging.info("Daily profits plot saved to: %s", __detailed_month_stats_path__)



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

    # --- Add forecast for current month (positive & negative separately) ---
    today = pd.Timestamp.today()
    current_month_start = today.replace(day=1).to_period('M').to_timestamp()
    days_in_month = (current_month_start + pd.offsets.MonthEnd(1)).day
    elapsed_days = today.day - 1

    monthly_stats['forecast_positive'] = None
    monthly_stats['forecast_negative'] = None

    if current_month_start in monthly_stats.index and elapsed_days > 0:
        # Positive forecast
        current_positive = monthly_stats.loc[current_month_start, 'profit_positive']
        forecast_positive = (current_positive / elapsed_days) * days_in_month
        monthly_stats.loc[current_month_start, 'forecast_positive'] = forecast_positive

        # Negative forecast
        current_negative = monthly_stats.loc[current_month_start, 'profit_negative']
        forecast_negative = (current_negative / elapsed_days) * days_in_month
        monthly_stats.loc[current_month_start, 'forecast_negative'] = forecast_negative

    # Plotting
    plt.figure(figsize=(12, 6))
    bar_width = 10  # in days, suitable for datetime x-axis

    # Actual positive and negative profits
    plt.bar(
        monthly_stats.index,
        monthly_stats['profit_positive'],
        width=bar_width,
        label='Positive Profit',
        color='green',
        edgecolor='black',
        align='center'
    )

    plt.bar(
        monthly_stats.index,
        monthly_stats['profit_negative'],
        width=bar_width,
        label='Negative Profit',
        color='red',
        edgecolor='black',
        align='center'
    )

    # --- Plot forecasts ---
    forecast_positive_data = monthly_stats['forecast_positive'].dropna()
    forecast_negative_data = monthly_stats['forecast_negative'].dropna()

    if not forecast_positive_data.empty:
        plt.bar(
            forecast_positive_data.index,
            forecast_positive_data - monthly_stats.loc[forecast_positive_data.index, 'profit_positive'],
            bottom=monthly_stats.loc[forecast_positive_data.index, 'profit_positive'],
            width=bar_width,
            label='Forecast Positive',
            color='blue',
            alpha=0.4,
            edgecolor='black',
            align='center'
        )

    if not forecast_negative_data.empty:
        plt.bar(
            forecast_negative_data.index,
            forecast_negative_data - monthly_stats.loc[forecast_negative_data.index, 'profit_negative'],
            bottom=monthly_stats.loc[forecast_negative_data.index, 'profit_negative'],
            width=bar_width,
            label='Forecast Negative',
            color='purple',
            alpha=0.4,
            edgecolor='black',
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
        if not pd.isna(row['forecast_positive']):
            plt.text(idx, row['forecast_positive'] + 10, f"{row['forecast_positive']:.2f}",
                     ha='center', va='bottom', fontsize=9, color='blue')
        if not pd.isna(row['forecast_negative']):
            plt.text(idx, row['forecast_negative'] - 10, f"{row['forecast_negative']:.2f}",
                     ha='center', va='top', fontsize=9, color='purple')

    plt.xlabel('Month')
    plt.ylabel('Profit')
    plt.title('Monthly Positive and Negative Profits (with Separate Forecasts)')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig(__monthly_stats_path__)
    plt.close()



def plot_available_offers_length_of_stay(
    available_offers_df: pd.DataFrame,
    bucket_edges: typing.Sequence[int] | None = None,
    reference_date: datetime.datetime | None = None,
    output_path: str = __available_offers_length_of_stay_path__,
):
    """
    Plot a pie chart of how long available offers have been listed.

    bucket_edges is an ordered collection of upper bounds (in days) that defines
    the buckets. The boundaries are (0, bucket_edges[0]], (bucket_edges[0],
    bucket_edges[1]], ... with the last bucket being (bucket_edges[-1], inf].
    By default this yields 1-14, 15-30, 31-60 and 61+ day buckets.
    """
    logging.info("--> plot_available_offers_length_of_stay()")

    if available_offers_df.empty:
        logging.warning("No available offers provided for length-of-stay plot.")
        return

    df = available_offers_df.copy()
    df["offer_date_created"] = pd.to_datetime(df.get("offer_date_created"), errors="coerce")
    df["buy_date"] = pd.to_datetime(df.get("buy_date"), errors="coerce")
    df["listing_date"] = df["offer_date_created"].combine_first(df["buy_date"])
    df = df.dropna(subset=["listing_date"])
    if df.empty:
        logging.warning("No listing dates available to compute length of stay.")
        return

    today = reference_date or pd.Timestamp.today().normalize()
    df["days_active"] = (today - df["listing_date"].dt.normalize()).dt.days
    df = df[df["days_active"] >= 0]
    if df.empty:
        logging.warning("All available offers have future listing dates.")
        return
    edges = [0] + (sorted(bucket_edges) if bucket_edges else [14, 30, 60]) + [float("inf")]
    labels = []
    lower_bound = edges[0]
    for upper_bound in edges[1:]:
        if upper_bound == float("inf"):
            labels.append(f"{int(lower_bound) + 1}+ days")
        else:
            labels.append(f"{int(lower_bound) + 1}-{int(upper_bound)} days")
        lower_bound = upper_bound
    buckets = pd.cut(df["days_active"], bins=edges, labels=labels, right=True, include_lowest=True)
    counts = buckets.value_counts().reindex(labels, fill_value=0)
    if counts.sum() == 0:
        logging.warning("No data to plot after bucketing length of stay.")
        return
    plt.figure(figsize=(8, 8))
    plt.pie(
        counts.values,
        labels=counts.index,
        autopct="%1.1f%%",
        startangle=140,
        colors=plt.cm.Set3.colors,
    )
    plt.title("Available Offers by Length of Stay")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logging.info("Length-of-stay pie chart saved to: %s", output_path)


def export_eur_reports(linked_purchases_df: pd.DataFrame):
    print("start export eur report")
    linked_purchases_df["offer_date_sold"] = pd.to_datetime(linked_purchases_df["offer_date_sold"], errors='coerce')
    linked_purchases_df["buy_date"] = pd.to_datetime(linked_purchases_df["buy_date"], errors='coerce')

    sold_df = linked_purchases_df[linked_purchases_df["state"] == "SOLD"].copy()

    sold_df["net_revenue"] = sold_df["selling_price"] * (1 - sold_df["commission_factor"])
    sold_df["month"] = sold_df["offer_date_sold"].dt.to_period("M").dt.to_timestamp()

    # Include buy_date and buy_price here
    eur_detailed_cols = [
        "buy_date",
        "buy_price",
        "offer_date_sold",
        "selling_price",
        "commission_factor",
        "net_revenue",
        "profit",
        "month"
    ]
    eur_detailed = sold_df[eur_detailed_cols].copy()

    # ROUNDING numeric columns to 2 decimals
    eur_detailed[["buy_price", "selling_price", "commission_factor", "net_revenue", "profit"]] = eur_detailed[
        ["buy_price", "selling_price", "commission_factor", "net_revenue", "profit"]
    ].round(2)

    eur_detailed.rename(columns={"offer_date_sold": "date_sold"}, inplace=True)

    # Save detailed report with buy info
    eur_detailed.to_csv(__base_path__ + "/EÜR_detailed.csv", index=False)
    print(f"eur report saved to {__base_path__ + '/EÜR_detailed.csv'}")

    # Monthly summary (without buy_date/buy_price because it's aggregate)
    monthly_summary = eur_detailed.groupby("month").agg(
        total_buy_price=pd.NamedAgg(column="buy_price", aggfunc="sum"),
        total_selling_price=pd.NamedAgg(column="selling_price", aggfunc="sum"),
        total_net_revenue=pd.NamedAgg(column="net_revenue", aggfunc="sum"),
        total_profit=pd.NamedAgg(column="profit", aggfunc="sum"),
        count_sales=pd.NamedAgg(column="date_sold", aggfunc="count"),
    ).reset_index()

    monthly_summary[["total_buy_price", "total_selling_price", "total_net_revenue", "total_profit"]] = monthly_summary[
        ["total_buy_price", "total_selling_price", "total_net_revenue", "total_profit"]
    ].round(2)

    monthly_summary.to_csv(__base_path__ + "/EÜR_monthly_summary.csv", index=False)
    print(f"monthly summary saved to {__base_path__ + '/EÜR_monthly_summary.csv'}")

    return eur_detailed, monthly_summary

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
    plot_month_detailed(sold_offers_sorted_by_date_sold_df)
    plot_available_offers_length_of_stay(available_offers_df)


    # FINANZAMT ANALYTICS
    logging.info("creating EÜR (income/expense) CSV")

    export_eur_reports(linked_purchases_df)
