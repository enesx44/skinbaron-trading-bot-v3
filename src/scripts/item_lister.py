from src.libs import csvs, skinbaron as sb
import pandas as pd
import logging
import json
import numpy as np
from datetime import datetime

__base_path_create_bot_skinlist__ = "./generated_files/create_bot_skinlist"
__bot_skinlist_path__ = __base_path_create_bot_skinlist__ + "/bot_skinlist.csv"

__base_path_bot__ = "./generated_files/bot"
__buy_history_path__ = __base_path_bot__ + "/BuyHistory.csv"

__base_path_manual_data__ = "./manual_data"
__base_path_price_calc__ = __base_path_manual_data__ + "/price_calculation"
__base_path_fee_codes__ = __base_path_price_calc__ + "/fee_codes.csv"

should_list = True

def get_best_fee_code(fee_codes_df: pd.DataFrame): 
    logging.debug("--> get_best_fee_code()")   
    
    logging.info("finding active fee codes")
    active_df = fee_codes_df[fee_codes_df["expire_date"] > datetime.now()]
    logging.debug("active_df:\n%s", active_df)

    logging.info("filtering best fee code")
    if not active_df.empty:        
        best_fee_code = active_df.sort_values(["commission_factor", "expire_date"], ascending=[True, False]).iloc[0]["name"]
        logging.debug("best_fee_code: %s", best_fee_code)
    else:
        best_fee_code = None
        logging.debug("best_fee_code: %s", best_fee_code)

    return best_fee_code

def main():
    logging.info("reading fee codes csv as dataframe")
    fee_codes_df = pd.read_csv(__base_path_fee_codes__, parse_dates=["expire_date"])
    logging.debug("fee_codes_df:\n%s", fee_codes_df)

    promotion_code = get_best_fee_code(fee_codes_df)

    inventory_df = sb.get_inventory()
    logging.debug("inventory_df: \n%s", inventory_df.to_string())

    skinlist_df = csvs.read_df(__bot_skinlist_path__)
    logging.debug("skinlist_df: \n%s", skinlist_df.to_string())

    history_df = csvs.read_df(__buy_history_path__)
    logging.debug("history_df: \n%s", history_df.to_string())

    items = []

    for i, row in inventory_df.iterrows():

        trade_locked_hours = row.get("tradeLockHoursLeft", None)

        if trade_locked_hours is not None and not pd.isna(trade_locked_hours):
            continue

        localizedName = row["localizedName"]

        search_name = localizedName

        try:
            localizedExteriorName = row["localizedExteriorName"]

            if isinstance(localizedExteriorName, str):
                search_name = localizedName + " (" + localizedExteriorName + ")"
        except:
            pass

        try:
            statTrakString = row["statTrakString"]

            if isinstance(statTrakString, str):
                statTrakString = str.replace(statTrakString, " ", "")
                search_name = statTrakString + " " + search_name
        except:
            pass

        try:
            souvenirString = row["souvenirString"]

            if isinstance(souvenirString, str):
                search_name = souvenirString + " " + search_name
        except:
            pass

        logging.debug("search_name: %s", search_name)

        entrys = history_df.loc[history_df["name"]
                                == search_name]["selling_price"]
        logging.debug("entries: %s", entrys.to_string())

        if not entrys.empty:

            # find price from buy history
            last_entry = entrys.tail(1)
            logging.debug("last_entry: %s", last_entry.to_string())

            entry_index = last_entry.index.values[0]
            logging.debug("index: %s", str(entry_index))

            price = last_entry.values[0]
            logging.debug("price: %s", str(price))

            history_df = history_df.drop(entry_index)

            if np.isnan(price):
                print("no price for this item in history")
                continue

            # find price from bot skinlist
            price_skinlist = skinlist_df.loc[skinlist_df["name"]
                                            == search_name, "selling_price"]
            try:
                price_skinlist = price_skinlist.values[0]
                logging.debug("price_skinlist: %s", str(price_skinlist))

                if price_skinlist > price:
                    logging.debug("%s is more expensive in skinlist", search_name)

                final_price = max(price, price_skinlist)
                logging.debug("final_price: %s", str(final_price))

            except IndexError:
                logging.error("%s not found in skinlist", search_name)
                final_price = price
                logging.debug("final_price: %s", str(final_price))

            items.append({"assetId": row["id"], "price": final_price,
                        "name": row["localizedName"]})


    logging.debug("items: %s", str(json.dumps(items, indent=4)))

    chunk_size = 50
    chunks = [items[i:i + chunk_size]
            for i in range(0, len(items), chunk_size)]

    for chunk in chunks:
        logging.debug("chunk: %s", str(json.dumps(chunk, indent=4)))
        if should_list:
            sb.list_items(items=chunk, promotion_code=promotion_code)
