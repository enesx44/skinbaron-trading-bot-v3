import pandas as pd
import numpy as np
import math
import datetime
import logging
import sys
import matplotlib.pyplot as plt
import os
import glob

# === CONFIG ===
MAX_TOTAL_COMMISSIONS = 0.20
DEFAULT_skinbaron_percentage_win = 0.15
USE_LAST_X_DAYS = 15
MIN_SALES_IN_LAST_X_DAYS = USE_LAST_X_DAYS

FEE_CODES_CSV = "./manual_data/price_calculation/fee_codes.csv"

__base_path__ = "./generated_files/price_calculation"
os.makedirs(__base_path__, exist_ok=True)

PLOT_DIR = __base_path__ + "/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

SLOPE_STATS_PATH = __base_path__ + "/slope_stats.csv"  
SLOPE_STATS_DISTRIBUTION_PATH = __base_path__ + "/slope_stats_distribution.png"  

# === GLOBAL STATE ===
fee_code = None
skinbaron_percentage_win = DEFAULT_skinbaron_percentage_win
our_percentage_win = MAX_TOTAL_COMMISSIONS - skinbaron_percentage_win
slope_stats = []

# === INIT ===
def init_fee_code():
    global fee_code, skinbaron_percentage_win, our_percentage_win

    try:
        df = pd.read_csv(FEE_CODES_CSV, parse_dates=["expire_date"])
    except Exception as e:
        logging.warning("Failed to read fee code CSV, using defaults: %s", e)
        fee_code = "NONE"
        return

    active = df[df["expire_date"] > datetime.datetime.now()]
    if not active.empty:
        best = active.sort_values(["commission_factor", "expire_date"], ascending=[True, False]).iloc[0]
        fee_code = best["name"]
        skinbaron_percentage_win = best["commission_factor"]
    else:
        fee_code = "NONE"
        skinbaron_percentage_win = DEFAULT_skinbaron_percentage_win

    our_percentage_win = round(MAX_TOTAL_COMMISSIONS - skinbaron_percentage_win, 2)

# === UTILS ===
def clear_plots():
    # Clear all previous plots before plotting new ones
    for file in glob.glob(os.path.join(PLOT_DIR, "*.png")):
        os.remove(file)

def has_wear(name: str) -> bool:
    wear_levels = ["(Factory New)", "(Minimal Wear)", "(Field-Tested)", "(Well-Worn)", "(Battle-Scarred)"]
    return any(level in name for level in wear_levels)

def jitter_duplicate_dates(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for date in df['x'].unique():
        same_dates = result[result['x'] == date]
        if len(same_dates) > 1:
            for idx, (i, _) in enumerate(same_dates.iterrows()):
                result.at[i, 'x'] += datetime.timedelta(seconds=idx * 5)
    return result.sort_values(by='x').reset_index(drop=True)

def classify_trend(slope: float) -> str:
    if slope > 1:
        return "UP"
    elif slope > 0.5:
        return "SLIGHT_UP"
    elif slope < -1:
        return "DOWN"
    elif slope < -0.5:
        return "SLIGHT_DOWN"
    return "STABLE"

def calc_bounds(mean: float, std: float, has_ext: bool) -> tuple[float, float]:
    upper = mean + (1.3 * std if has_ext else 2 * std)
    lower = mean - 2 * std
    return upper, lower

def remove_outliers(df: pd.DataFrame, mean: float, std: float, factor: float) -> pd.DataFrame:
    return df[(df['y'] <= mean + factor * std) & (df['y'] >= mean - factor * std)]

def visualize_and_save_slope_stats_csv():

    global slope_stats

    if not slope_stats:
        logging.warning("No slope stats to save.")
        return
    df_stats = pd.DataFrame(slope_stats)
    df_stats["slope"] = df_stats["slope"].round(4)

    plt.figure(figsize=(10, 6))
    plt.hist(
        df_stats["slope"],
        bins=50,  # Increase bins for better distribution
        color='skyblue',
        edgecolor='black'
    )
    plt.yscale('log')  # Optional: make skewed distributions readable

    plt.title("Histogram of Slope Values")
    plt.xlabel("Slope (rounded to 2 decimals)")
    plt.ylabel("Frequency (log scale)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(SLOPE_STATS_DISTRIBUTION_PATH)
    plt.close()

    df_stats = df_stats.sort_values("slope", ascending=False)
    df_stats.to_csv(SLOPE_STATS_PATH, index=False)
    logging.info(f"Saved slope stats CSV: {SLOPE_STATS_PATH}")
    slope_stats.clear()

def plot_price_history(
    df: pd.DataFrame,
    name: str,
    doppler: str | None = None,
    buy_price: float | None = None,
    selling_price: float | None = None,
    mean: float | None = None,
    upper: float | None = None,
    lower: float | None = None,
):
    global slope_stats
    try:
        df = df.copy()
        df = df.sort_values("x")

        now = datetime.datetime.now()
        start_365 = now - datetime.timedelta(days=365)
        cutoff_date = now - datetime.timedelta(days=USE_LAST_X_DAYS)

        # Filter to last 365 days max
        df = df[df["x"] >= start_365]
        if df.empty:
            logging.warning(f"No sales in the last 365 days to plot for {name}")
            return

        min_date = df["x"].min()
        max_date = df["x"].max()
        days_span = (max_date - min_date).days or 1  # avoid zero division

        x_numeric = (df["x"] - min_date).dt.total_seconds() / (24 * 3600)  # days since first sale
        y = df["y"].values
        slope, intercept = np.polyfit(x_numeric, y, 1) 

        # Separate outliers (points outside [lower, upper]) if bounds provided
        if lower is not None and upper is not None:
            # Identify outliers within 3x distance from bounds
            outliers_mask = ((df["y"] < lower) & (df["y"] >= lower - 2 * (upper - lower))) | \
                            ((df["y"] > upper) & (df["y"] <= upper + 2 * (upper - lower)))
            inliers = df[(df["y"] >= lower) & (df["y"] <= upper)]
            outliers = df[outliers_mask]
        else:
            inliers = df
            outliers = pd.DataFrame(columns=df.columns)


        plt.figure(figsize=(20, 10))
        # Plot inliers
        plt.scatter(inliers["x"], inliers["y"], s=20, alpha=0.6, label=f"Sales (last {days_span} days)")

        # Plot outliers in different color
        if not outliers.empty:
            plt.scatter(outliers["x"], outliers["y"], s=30, color="orange", alpha=0.9, label="Outliers")

        # Trend line
        plt.plot(df["x"], slope * x_numeric + intercept, color="red", linestyle="--", label=f"Trend (slope={slope:.5f}€ per day)")

        plt.xlim(min_date, max_date)

        # Vertical cutoff line for last X days
        if min_date <= cutoff_date <= max_date:
            plt.axvline(cutoff_date, color="purple", linestyle="--", label=f"Cutoff ({USE_LAST_X_DAYS}d ago)")

        # Horizontal lines for prices/stats if provided
        if mean is not None:
            plt.axhline(mean, color="blue", linestyle=":", label=f"Mean Price ({mean:.2f} €)")
        if buy_price is not None:
            plt.axhline(buy_price, color="green", linestyle="--", label=f"Buy Price ({buy_price:.2f} €)")
        if selling_price is not None:
            plt.axhline(selling_price, color="magenta", linestyle="-.", label=f"Selling Price ({selling_price:.2f} €)")
        if upper is not None:
            plt.axhline(upper, color="gray", linestyle="--", alpha=0.7, label=f"Upper Bound ({upper:.2f} €)")
        if lower is not None:
            plt.axhline(lower, color="gray", linestyle="--", alpha=0.7, label=f"Lower Bound ({lower:.2f} €)")


        plt.title(f"Price History: {name}" + (f" ({doppler})" if doppler else ""))
        plt.xlabel("Date Sold")
        plt.ylabel("Price (€)")
        plt.xticks(rotation=30)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_name = name.replace(" ", "_").replace("/", "-").replace("|", "")
        slope_stats.append({"name": safe_name, "slope": slope})

        filename = os.path.join(PLOT_DIR, f"{safe_name}.png")
        plt.savefig(filename)
        plt.close()
        logging.info(f"Saved plot: {filename}")

    except Exception as e:
        logging.warning(f"Failed to plot for {name}: {e}")

# === MAIN LOGIC ===
def calculate_price_for_item(sales_df: pd.DataFrame, should_plot: bool) -> pd.DataFrame | None:
    if sales_df['itemName'].nunique() != 1:
        logging.error("Multiple itemNames in input!")
        sys.exit(1)

    name = sales_df["itemName"].iloc[0]
    doppler = sales_df["dopplerPhase"].iloc[0] if "dopplerPhase" in sales_df.columns else None
    logging.info("Analyzing: %s | dopplerPhase: %s", name, doppler)

    dates = pd.to_datetime(sales_df["dateSold"], errors="coerce")
    prices = sales_df["price"]
    logging.debug("Raw sales data contains %d entries.", len(sales_df))

    if len(dates) < 10:
        logging.warning("Too few sales for item: %s", name)
        return None

    df = pd.DataFrame({"x": dates, "y": prices}).dropna()
    logging.debug("Data after dropping NaNs: %d entries.", len(df))
    df = jitter_duplicate_dates(df)
    logging.debug("Data after jittering: \n%s", df.to_string())

    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=USE_LAST_X_DAYS)
    min_cutoff = now - datetime.timedelta(days=USE_LAST_X_DAYS * 2)
    recent = df[df["x"] >= cutoff]
    logging.debug("Recent sales found: %d", len(recent))
    logging.debug("Recent sales: \n%s", recent.to_string())

    multiplier = next(
        (m for threshold, m in [
            (2, 0.8), (4, 0.86), (7, 0.91), (11, 0.95)
        ] if len(recent) < threshold),
        1
    )

    logging.debug("Applied multiplier: %.2f based on %d recent sales", multiplier, len(recent))

    if len(recent) < MIN_SALES_IN_LAST_X_DAYS:
        top_up_needed = MIN_SALES_IN_LAST_X_DAYS - len(recent)
        older = df[df["x"] < cutoff].tail(top_up_needed)
        logging.debug("older sales: \n%s", older.to_string())
        logging.debug("Topping up with %d older sales", len(older))
        if len(df[df["x"] >= min_cutoff]) < MIN_SALES_IN_LAST_X_DAYS:
            logging.warning("Not enough sales even after top-up for: %s", name)
            return None
        recent = pd.concat([recent, older]).sort_values("x").reset_index(drop=True)

    mean = recent["y"].mean()
    std = recent["y"].std()
    logging.debug("Initial mean: %.2f | std: %.2f", mean, std)

    has_ext = has_wear(name)
    logging.debug("has_wear result for '%s': %s", name, has_ext)

    upper, lower = calc_bounds(mean, std, has_ext)
    logging.debug("First outlier bounds: upper=%.2f, lower=%.2f", upper, lower)

    no_first_outliers = recent[(recent['y'] >= lower) & (recent['y'] <= upper)]
    logging.debug("Remaining sales after 1st outlier removal: %d", len(no_first_outliers))
    logging.debug("Data after removing 1st outliers: \n%s", no_first_outliers.to_string())
    if len(no_first_outliers) < 10:
        logging.info("Too few sales after removing 1st outliers.")
        return None

    mean = no_first_outliers["y"].mean()
    std = no_first_outliers["y"].std()
    logging.debug("1st Refined mean: %.2f | std: %.2f", mean, std)

    factor = 1.5
    final_df = remove_outliers(no_first_outliers, mean, std, factor=factor)
    logging.debug("Remaining sales after 2nd outlier removal: %d", len(final_df))
    logging.debug("Data after removing 2nd outliers: \n%s", final_df.to_string())
    if len(final_df) < 10:
        logging.info("Too few sales after removing 2nd outliers.")
        return None
    
    mean = final_df["y"].mean()
    std = final_df["y"].std()
    logging.debug("2nd Refined mean: %.2f | std: %.2f", mean, std)

    factor = 2.5
    final_df = remove_outliers(final_df, mean, std, factor=factor)
    logging.debug("Remaining sales after 3rd outlier removal: %d", len(final_df))
    logging.debug("Data after removing 3rd outliers: \n%s", final_df.to_string())
    if len(final_df) < 10:
        logging.info("Too few sales after removing 3rd outliers.")
        return None
    
    upper_sale_bound_for_graphic = round(mean + (std * factor), 2)
    lower_sale_bound_for_graphic = round(mean - (std * factor), 2)
    
    mean = final_df["y"].mean()
    std = final_df["y"].std()
    logging.debug("3rd Refined mean: %.2f | std: %.2f", mean, std)

    x_idxs = [i for i in range(len(df)) if df.iloc[i]['x'] in final_df["x"].values and df.iloc[i]['y'] in final_df["y"].values]
    slope, intercept = np.polyfit(x_idxs, final_df["y"], 1)
    trend = classify_trend(slope)
    logging.info("Trend: %s (slope=%.2f)", trend, slope)  

    upper_sale_bound = round(mean + std, 2)
    lower_sale_bound = round(mean - std, 2)
    my_share = upper_sale_bound * (1 - skinbaron_percentage_win)
    my_share_after_removing_costs = my_share - lower_sale_bound
    my_desired_profit = my_share * our_percentage_win
    is_profitable = my_share_after_removing_costs > my_desired_profit
    logging.debug("Profit analysis: upper_sale_bound=%.2f, lower_sale_bound=%.2f, my_share=%.2f, my_share_after_removing_costs=%.2f, my_desired_profit=%.2f, is_profitable=%s", upper_sale_bound, lower_sale_bound, my_share, my_share_after_removing_costs, my_desired_profit, is_profitable)

    is_new = any(y in name for y in map(str, range(2020, 2026)))
    logging.debug("Is new item: %s", is_new)

    if is_profitable and slope > -1 and not is_new:
        logging.info("Item is profitable and stable.")
        upper_sales = final_df[final_df["y"] >= mean]
        avg_upper = upper_sales["y"].mean() if not upper_sales.empty else mean + std * 0.75
        selling_price = min(round(mean + std * 0.75, 2), round(avg_upper - 0.01, 2))
        sell_volume = selling_price * (1 - skinbaron_percentage_win)
        min_profit = max(sell_volume * our_percentage_win, 0.3)
        buy_price = sell_volume - min_profit
        logging.debug("Profitable path: sell=%.2f, buy=%.2f, profit=%.2f", selling_price, buy_price, min_profit)

        if buy_price <= 0.01:
            logging.warning("Too small / negative buy price, skipping: %s", name)
            return None
        
        buy_price *= multiplier
        logging.debug("Buy price after sales count multiplier: %.2f", buy_price)
        
        if buy_price <= 0.01:
            logging.warning("Too small / negative buy price, skipping: %s", name)
            return None
    
        if slope < -0.5: buy_price *= 0.8
        elif slope < -0.25: buy_price *= 0.88
        elif slope < -0.1: buy_price *= 0.95
        elif slope > 0.1: buy_price /= 0.95
        elif slope > 0.25: buy_price /= 0.88
        elif slope > 0.5: buy_price /= 0.8
        elif slope > 1: buy_price /= 0.7
        logging.debug("Buy price after slope multiplier: %.2f", buy_price)

        if buy_price <= 0.01:
            logging.warning("Too small / negative buy price, skipping: %s", name)
            return None        
    else:
        logging.info("Low quality or risky item, target lowball buy offers.")
        selling_price = max(mean - 0.01, final_df["y"].mean() - 0.01)
        sell_volume = selling_price * (1 - skinbaron_percentage_win)
        min_profit = max(sell_volume * (our_percentage_win * 0.25), 0.1)
        buy_price = sell_volume - min_profit
        logging.debug("Lowball path: sell=%.2f, buy=%.2f, profit=%.2f", selling_price, buy_price, min_profit)

        if buy_price <= 0.01:
            logging.warning("Too small / negative buy price, skipping: %s", name)
            return None

        buy_price *= multiplier
        logging.debug("Buy price after sales count multiplier: %.2f", buy_price)

        if buy_price <= 0.01:
            logging.warning("Too small / negative buy price, skipping: %s", name)
            return None        
        
        if slope < -0.5: buy_price *= 0.8
        elif slope < -0.25: buy_price *= 0.88
        elif slope < -0.1: buy_price *= 0.95
        elif slope > 0.1: buy_price /= 0.97
        elif slope > 0.25: buy_price /= 0.93
        elif slope > 0.5: buy_price /= 0.88
        elif slope > 1: buy_price /= 0.82
        logging.debug("Buy price after slope multiplier: %.2f", buy_price)

        if buy_price <= 0.01:
            logging.warning("Too small / negative buy price, skipping: %s", name)
            return None

    tier = next((t for p, t in [
        (0.1, 7), (0.2, 6), (0.5, 5), (1, 4), (3, 3), (10, 2)
    ] if min_profit < p), 1)

    buy_price = math.floor(buy_price * 100) / 100
    selling_price = math.floor(selling_price * 100) / 100
    min_profit = round(selling_price * (1 - skinbaron_percentage_win) - buy_price, 2)
    logging.debug("end result: sell=%.2f, buy=%.2f, profit=%.2f", selling_price, buy_price, min_profit)

    result = pd.DataFrame([{
        "name": name,
        "buy_price": buy_price,
        "selling_price": selling_price,
        "min_profit": min_profit,
        "mean_profitability": not (is_profitable and slope > -1 and not is_new),
        "tier": tier
    }])

    logging.info("Final result for %s: buy_price=%.2f, sell_price=%.2f, min_profit=%.2f, tier=%d",
                 name, buy_price, selling_price, min_profit, tier)
    
    if min_profit <= 0.08:
        logging.warning("Too small / negative min_profit, skipping: %s", name)
        return None

    if should_plot:
        logging.debug("Plotting price history for %s", name)
        plot_price_history(
            df=df,
            name=name,
            doppler=doppler,
            buy_price=buy_price,
            selling_price=selling_price,
            mean=mean,
            upper=upper_sale_bound_for_graphic,
            lower=lower_sale_bound_for_graphic
        )

    return result
