import pandas as pd
import logging
import datetime
import sys
import numpy as np
import math

skinbaron_percentage_win = 0.15
our_percentage_win = 0.15

use_last_x_days = 15
min_sales_in_last_x_days = use_last_x_days

def checkIfHasWear(name: str) -> bool:
    if name.find("(Factory New)") != -1:
        return True
    elif name.find("(Minimal Wear)") != -1:
        return True
    elif name.find("(Field-Tested)") != -1:
        return True
    elif name.find("(Well-Worn)") != -1:
        return True
    elif name.find("(Battle-Scarred)") != -1:
        return True
    else:
        return False
    
def init_skinbaron_percentage_win(value: float):
    logging.debug("--> init_skinbaron_percentage_win()")
    global skinbaron_percentage_win

    skinbaron_percentage_win = value

def calculate_price_for_item(sales_df: pd.DataFrame) -> pd.DataFrame | None: 
    logging.debug("--> calculate_price_for_item()")
    logging.debug("skinbaron_percentage_win: %s", skinbaron_percentage_win)
    
    logging.debug("sales_df: \n%s", sales_df.to_string())
    
    unique_names = sales_df["itemName"].unique()
    logging.debug("unique_names: \n%s", len(unique_names))

    # Check if all values in 'itemName' are the same
    if sales_df['itemName'].nunique() == 1:
        logging.info("All rows in itemName have the same value. good.")
    else:
        logging.error("itemName contains different values")
        sys.exit(1)

    if 'dopplerPhase' in sales_df.columns:
        # Check if all values in 'dopplerPhase' are null
        if sales_df['dopplerPhase'].isnull().all():
            logging.info("All rows in dopplerPhase are None. That means no dopplerPhase.")
        else:
            # If not all are null, check if all values are the same
            if sales_df['dopplerPhase'].nunique(dropna=True) == 1:
                logging.info("All rows in dopplerPhase have the same value. Good.")
            else:
                logging.error("dopplerPhase contains different values.")
    else:
        logging.info("The 'dopplerPhase' column does not exist in the DataFrame.")


    name = sales_df["itemName"].iloc[0]
    dopplerPhase = sales_df["dopplerPhase"].iloc[0]

    # extract dates from scraped sales for current item
    x_dates = pd.to_datetime(sales_df["dateSold"], format="%Y-%m-%d", yearfirst=True, exact=False)

    logging.debug("x_dates: \n%s", str(x_dates))

    # EXTRACT PRICES FROM SALES HISTORY
    y_prices = sales_df["price"]

    logging.debug("y_prices: \n%s", str(y_prices))

    # MERGE DATES AND PRICES INTO 1 DF
    if isinstance(x_dates, datetime.datetime) or len(x_dates) < 10:
        logging.warning("TOO FEW SALES FOR ITEM : name: %s, dopplerPhase: %s", name, dopplerPhase)
        return None
    else:
        df_date_price = pd.DataFrame(data={"x": x_dates, "y": y_prices})

    # SORT BY ASCENDING DATE
    df_date_price = df_date_price.sort_values(by="x", ascending=True)
    df_date_price = df_date_price.reset_index(drop=True)

    # ADD JITTERING TO SAME DATES SO THEY DONT OVERLAP
    unique_dates = df_date_price["x"].unique()
    for date in unique_dates:

        all_rows_for_date = df_date_price.loc[df_date_price["x"] == date]

        if len(all_rows_for_date) > 1:

            k = 0

            for h, row in all_rows_for_date.iterrows():
                time_change = datetime.timedelta(seconds=k*5)
                new_time = row["x"] + time_change
                all_rows_for_date.at[h, "x"] = new_time
                k += 1

        df_date_price.loc[df_date_price["x"] == date] = all_rows_for_date
    df_date_price = df_date_price.sort_values(by="x", ascending=True)
    df_date_price = df_date_price.reset_index(drop=True)

    final_df = pd.DataFrame(
        data={"x": df_date_price["x"], "y": df_date_price["y"]})
    final_df = final_df.sort_values(by="x", ascending=True)
    final_df = final_df.reset_index(drop=True)

    # LAST 15 DAYS
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=use_last_x_days)
    min_date = today - datetime.timedelta(days=use_last_x_days * 2)

    last_15_days_df = final_df.loc[final_df["x"] >= cutoff_date]
    logging.debug("last_15_days_df: \n%s",
                    last_15_days_df.to_string())

    sales_count_multiplier = 1

    if len(last_15_days_df) < 4:
        sales_count_multiplier = 0.7
        logging.debug("sales_count_multiplier: %s", str(sales_count_multiplier))
    elif len(last_15_days_df) < 7:
        sales_count_multiplier = 0.78
        logging.debug("sales_count_multiplier: %s", str(sales_count_multiplier))
    elif len(last_15_days_df) < 10:
        sales_count_multiplier = 0.85
        logging.debug("sales_count_multiplier: %s", str(sales_count_multiplier))
    elif len(last_15_days_df) < 15:
        sales_count_multiplier = 0.9
        logging.debug("sales_count_multiplier: %s", str(sales_count_multiplier))
    elif len(last_15_days_df) < 30:
        sales_count_multiplier = 0.95
        logging.debug("sales_count_multiplier: %s", str(sales_count_multiplier))
    else:
        logging.debug("sales_count_multiplier: %s", str(sales_count_multiplier))

    # Check if there are at least 15 sales in the last 15 days
    if len(last_15_days_df) < min_sales_in_last_x_days:
        # Calculate the number of additional sales needed
        additional_sales_needed = min_sales_in_last_x_days - \
            len(last_15_days_df)

        if not len(final_df[final_df['x'] >= min_date]) >= min_sales_in_last_x_days:
            logging.warning(
                "LESS THAN MIN_SALES: %s, SALES FOR ITEM: %s, AFTER MIN_DATE: %s", str(min_sales_in_last_x_days), name, str(min_date))
            return None

        # Get the older sales to top up
        older_sales_df = final_df[final_df['x'] <
                                    cutoff_date].tail(additional_sales_needed)

        # Append the older sales to the last 15 days sales
        last_15_days_final_df = pd.concat(
            [last_15_days_df, older_sales_df]).sort_values(by="x", ascending=True).reset_index(drop=True)
    else:
        last_15_days_final_df = last_15_days_df
    logging.debug("last_15_days_final_df: \n%s",
                    last_15_days_final_df.to_string())

    if not last_15_days_final_df.empty:

        mean_graph = last_15_days_final_df["y"].to_numpy().mean()
        logging.debug("mean_graph: %s", str(mean_graph))
        std_graph = last_15_days_final_df["y"].to_numpy().std()
        logging.debug("std_graph: %s", str(std_graph))

        # OUTLIERS
        hasExterior = checkIfHasWear(name)

        if hasExterior:
            logging.debug("HAS EXT")
            upper_bound = mean_graph + 1.3 * std_graph
            lower_bound = mean_graph - 2 * std_graph
        else:
            upper_bound = mean_graph + 2 * std_graph
            lower_bound = mean_graph - 2 * std_graph
        logging.debug("upper_bound: %s", str(upper_bound))
        logging.debug("lower_bound: %s", str(lower_bound))

        last_15_days_final_first_outliers_df = last_15_days_final_df[~((
            last_15_days_final_df['y'] <= upper_bound) & (last_15_days_final_df['y'] >= lower_bound))].sort_values(by="x", ascending=True).reset_index(drop=True)
        logging.debug("last_15_days_final_first_outliers_df: \n%s",
                        last_15_days_final_first_outliers_df.to_string())

        logging.info("found %s outliers on first time",
                        str(len(last_15_days_final_first_outliers_df)))

        last_15_days_final_df = last_15_days_final_df[(
            last_15_days_final_df['y'] <= upper_bound) & (last_15_days_final_df['y'] >= lower_bound)].sort_values(by="x", ascending=True).reset_index(drop=True)
        logging.debug("last_15_days_final_df: \n%s",
                        last_15_days_final_df.to_string())

        if len(last_15_days_final_df) < 10:
            logging.debug(
                "AFTER REMOVING OUTLIERS LESS THAN 10 SALES LEFT... SKIPPING TO NEXT ITEM.")
            return None

        density = len(last_15_days_final_df)
        if density > 640:
            markersize = 2
        elif density > 320:
            markersize = 3
        elif density > 160:
            markersize = 4
        elif density > 80:
            markersize = 5
        elif density > 40:
            markersize = 6
        elif density > 20:
            markersize = 8
        elif density > 10:
            markersize = 10
        elif density > 0:
            markersize = 12

        mean = last_15_days_final_df["y"].to_numpy().mean()
        logging.debug("mean: %s", str(mean))
        std = last_15_days_final_df["y"].to_numpy().std()
        logging.debug("std: %s", str(std))

        last_15_days_final_second_outliers_df = last_15_days_final_df[~((
            last_15_days_final_df['y'] <= mean + std * 2) & (last_15_days_final_df['y'] >= mean - std * 2))].sort_values(by="x", ascending=True).reset_index(drop=True)
        logging.debug("last_15_days_final_second_outliers_df: \n%s",
                        last_15_days_final_second_outliers_df.to_string())

        logging.info("found %s outliers on second time",
                        str(len(last_15_days_final_second_outliers_df)))

        logging.debug("len before 2nd outliers: %s",
                        str(len(last_15_days_final_df)))
        last_15_days_final_df = last_15_days_final_df[(
            last_15_days_final_df['y'] <= mean + std * 2) & (last_15_days_final_df['y'] >= mean - std * 2)].sort_values(by="x", ascending=True).reset_index(drop=True)
        logging.debug("last_15_days_final_df: \n%s",
                        last_15_days_final_df.to_string())
        logging.debug("len after 2nd outliers: %s",
                        str(len(last_15_days_final_df)))

        mean = last_15_days_final_df["y"].to_numpy().mean()
        logging.debug("mean: %s", str(mean))
        std = last_15_days_final_df["y"].to_numpy().std()
        logging.debug("std: %s", str(std))

        i_list = []
        # Plot original data points
        for i in range(len(final_df)):
            if final_df["x"].iloc[i] in last_15_days_final_df["x"].values and final_df["y"].iloc[i] in last_15_days_final_df["y"].values:
                i_list.append(i)
        i_list = np.array(i_list)
        pd.set_option("display.float_format", lambda x: "%.2f" % x)
        print(i_list)
        slope, intercept = np.polyfit(
            i_list, last_15_days_final_df['y'], 1)
        print(slope, intercept)
        if slope < -1:
            logging.info(
                "SALES ON A DOWNWARD TREND: %s", str(slope))
        elif slope < -0.5:
            logging.info(
                "SALES ON A SLIGHT DOWNWARD TREND: %s", str(slope))
        elif slope > 1:
            logging.info("SALES ON A UPWARD TREND: %s", str(slope))
        elif slope > 0.5:
            logging.info("SALES ON A SLIGHT UPWARD TREND: %s", str(slope))
        elif slope > -0.5 and slope < 0.5:
            logging.info("SALES ON A STAGNANT TREND: %s", str(slope))

        # CALCULATE BUYING AND OPTIMAL SELLING PRICE
        a = round(mean + std, 2)
        b = round(mean - std, 2)
        c = a * (1-skinbaron_percentage_win)
        d = c - b
        e = c * our_percentage_win
        f = d > max(e, 0.25)

        if "2020" in name or "2021" in name or "2022" in name or "2023" in name or "2024" in name or "2025" in name:
            isNew = True
        else:
            isNew = False

        logging.debug("a: %s", str(a))
        logging.debug("b: %s", str(b))
        logging.debug("c: %s", str(c))
        logging.debug("d: %s", str(d))
        logging.debug("e: %s", str(e))

        if f and slope > -1 and not isNew:
            if round(last_15_days_final_df.loc[last_15_days_final_df["y"] >= mean]["y"].mean() - 0.03, 2) < round(mean + std * .75, 2):
                logging.warning("CHECK %s", name)
            selling_price = min(round(mean + std * .75, 2),
                                round(last_15_days_final_df.tail(min_sales_in_last_x_days).loc[last_15_days_final_df.tail(min_sales_in_last_x_days)["y"] > mean]["y"].mean() - 0.01, 2))

            sales_volume = selling_price * (1-skinbaron_percentage_win)
            min_profit = max(sales_volume * our_percentage_win, 0.3)

            buy_price = sales_volume - min_profit

            if slope < -0.75:
                buy_price *= 0.7
            elif slope < -0.5:
                buy_price *= 0.8
            elif slope < -0.25:
                buy_price *= 0.9

            buy_price = buy_price * sales_count_multiplier
        else:
            logging.info(
                "%s IS ASS BUT CAN HOPE FOR VERY LOW OFFERS", name)
            selling_price = max(mean - 0.01, round(
                last_15_days_final_df["y"].tail(min_sales_in_last_x_days).mean(), 2) - 0.01)

            sales_volume = selling_price * (1-skinbaron_percentage_win)
            min_profit = max(sales_volume * (our_percentage_win*0.25), 0.1)
            buy_price = sales_volume - min_profit

            if slope < -2:
                buy_price *= 0.6
            elif slope < -1.5:
                buy_price *= 0.7
            elif slope < -1.25:
                buy_price *= 0.8
            elif slope < -1:
                buy_price *= 0.9
            elif slope < -0.5:
                buy_price *= 0.95

            buy_price = buy_price * sales_count_multiplier

        logging.info("buy_price: %s", str(buy_price))
        logging.info("selling_price: %s", str(selling_price))

        logging.info(
            "selling_price: %s, sales_volume: %s, min_profit: %s, buy_price: %s", str(selling_price), str(sales_volume), str(min_profit), str(buy_price))

        if buy_price < 0:
            logging.warning(
                "%s has negative buy price, skipping to next item.", name)
            return None

        logging.info(
            "min_profit: %s", str(min_profit))

        if min_profit < 0.1:
            logging.error(
                "%s IS F", name)
            tier = 7
        elif min_profit < 0.2:
            logging.info(
                "%s IS D", name)
            tier = 6
        elif min_profit < 0.5:
            logging.info(
                "%s IS C", name)
            tier = 5
        elif min_profit < 1:
            logging.info(
                "%s IS B", name)
            tier = 4
        elif min_profit < 3:
            logging.info(
                "%s IS A", name)
            tier = 3
        elif min_profit < 10:
            logging.info(
                "%s IS S", name)
            tier = 2
        else:
            logging.info(
                "%s IS S+", name)
            tier = 1

        buy_price = math.floor(buy_price * 100) / 100
        selling_price = math.floor(selling_price * 100) / 100
        min_profit = round(selling_price * (1-skinbaron_percentage_win) - buy_price, 2)

        df = pd.DataFrame([[name, buy_price, selling_price, min_profit, not (f and slope > -1 and not isNew), tier]], 
                          columns=["name", "buy_price", "selling_price", "min_profit", "mean_profitability", "tier"])
        return df
