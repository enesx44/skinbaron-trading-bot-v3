import logging
from datetime import *
import os
import pandas as pd
import numpy as np
from src.libs import csvs, skinbaron as sb, utils
from src.scripts import create_bot_skinlist
import time

from src.enums.enums import ApiKey
from src.scripts import link_purchases_to_offers

__base_path__ = "./generated_files/bot"
__buy_history_path__ = __base_path__ + "/BuyHistory.csv"

__base_path_create_bot_skinlist__ = "./generated_files/create_bot_skinlist"
__bot_skinlist_path__ = __base_path_create_bot_skinlist__ + "/bot_skinlist.csv"
__bot_skinlist_metadata_path__ = __base_path_create_bot_skinlist__ + "/metadata.json"

__base_path_manual_data__ = "./manual_data"
__base_path_price_calc__ = __base_path_manual_data__ + "/price_calculation"
__base_path_fee_codes__ = __base_path_price_calc__ + "/fee_codes.csv"

__api_key__ = ApiKey.API_KEY.value

__forbidden_ids_list__ = []
__forbidden_ids_temp__ = []

__item_limit__ = 4
__very_good_item_limit__ = 8
__very_good_offer_percentage__ = 0.75
__slow_down_balance__ = 500

def get_inventory() -> pd.DataFrame:
    logging.debug("--> get_inventory()")
    
    last_page_df = None  # Initialize to track the last page data

    inventory_df = pd.DataFrame()
    page = 1

    while True:
        try:
            # Fetch the current page
            df = sb.get_inventory_page(str(page))

            # Check if the response contains data
            if df.empty:
                logging.debug(f"No more data found on page {page}. Stopping.")
                break       
             
            # Check if the response contains duplicate data
            if last_page_df is not None and df.equals(last_page_df):
                logging.debug(f"Duplicate data found on page {page}. Stopping.")
                break

            # Update last_page_df for comparison
            last_page_df = df.copy()    

            # Merge the data into the final dictionary
            inventory_df = pd.concat([inventory_df, df], ignore_index=True)
            logging.debug(f"Page {page} processed. Total items: {len(inventory_df)}")

            # Increment the page counter
            page += 1
        except TimeoutError:
            logging.error("Timeout occurred while fetching page %d", page)
            raise
        except Exception as e:
            logging.error(f"Unexpected error occurred: {str(e)}")
            raise

    return inventory_df

def add_count_to_items_from_inventory(item_counts: list, inventory_df: pd.DataFrame):
    logging.debug("--> add_count_to_items_from_inventory()")
    """ Counts Items in item_dictionary and writes count into item_counts """
    if inventory_df.empty:
        return item_counts

    for index, row in inventory_df.iterrows():
        logging.info("Processing item %d/%d", index, len(inventory_df))
        for entry in item_counts:

            name = row["localizedName"]
            exterior = row["localizedExteriorName"]

            if not pd.isna(exterior):
                name = name + " (" + exterior + ")"

            if (name == entry[0]):
                entry[1] += 1
    return item_counts

def add_count_to_items_from_active_offers(item_counts: list, available_offers_df: pd.DataFrame):
    logging.debug("--> add_count_to_items_from_active_offers()")
    """ Counts Items in available_offers_df and writes count into item_counts """

    if available_offers_df.empty: 
        return item_counts

    for index, row in available_offers_df.iterrows():
        logging.info("Processing item %d/%d", index, len(available_offers_df))
        for entry in item_counts:
            if (row["name"] == entry[0]):
                entry[1] += 1
    return item_counts

def check_expired(date: datetime, check_date: datetime):
    logging.debug("--> check_expired()")
    return date < check_date

def check_file_older_than(path: str, days: int):
    logging.debug("--> check_file_older_than()")
    if not os.path.exists(path):
        raise FileNotFoundError
    
    mod_date = datetime.fromtimestamp(os.path.getmtime(path))
    check_date = utils.get_datetime_n_days_ago(days)

    is_expired = check_expired(mod_date, check_date)

    if is_expired:
        logging.debug("file older than %s days", str(days))
    else:
        logging.debug("file not older than %s days", str(days))

    return is_expired

def check_better_active_fee_code_available():
    logging.debug("--> check_for_better_fee_code()")

    bot_skinlist_metadata = utils.read_cached_json_objects(__bot_skinlist_metadata_path__)
    logging.debug("bot_skinlist_metadata: %s", bot_skinlist_metadata)

    bot_skinlist_commission_factor = bot_skinlist_metadata["commission_factor"]
    logging.debug("bot_skinlist_commission_factor: %s", bot_skinlist_commission_factor)

    fee_codes_df = pd.read_csv(__base_path_fee_codes__, parse_dates=["expire_date"])
    logging.debug("fee_codes_df: \n%s", fee_codes_df.to_string())
    
    active_fee_codes_df = fee_codes_df[fee_codes_df["expire_date"] > datetime.now()]

    better_fee_codes_df = active_fee_codes_df[active_fee_codes_df["commission_factor"] < bot_skinlist_commission_factor]

    if better_fee_codes_df.empty:
        logging.debug("no better fee code available")
        return False
    else:
        logging.debug("better fee code available")
        return True

def check_fee_code_expired():
    logging.debug("--> check_fee_code_expired()")

    bot_skinlist_metadata = utils.read_cached_json_objects(__bot_skinlist_metadata_path__)
    logging.debug("bot_skinlist_metadata: %s", bot_skinlist_metadata)

    fee_code_name = bot_skinlist_metadata["fee_code_name"]
    logging.debug("fee_code_name: %s", fee_code_name)

    bot_skinlist_commission_factor = bot_skinlist_metadata["commission_factor"]
    logging.debug("bot_skinlist_commission_factor: %s", bot_skinlist_commission_factor)

    fee_codes_df = pd.read_csv(__base_path_fee_codes__, parse_dates=["expire_date"])
    logging.debug("fee_codes_df: \n%s", fee_codes_df.to_string())

    if fee_codes_df.empty and (bot_skinlist_commission_factor == 0.15):
        logging.debug("no fee code applied")
        return False

    if fee_codes_df.empty and (bot_skinlist_commission_factor < 0.15):
        logging.debug("fee code expired")
        return True
    
    active_fee_codes_df = fee_codes_df[fee_codes_df["expire_date"] > datetime.now()]
    logging.debug("active_fee_codes_df: \n%s", active_fee_codes_df.to_string())
    active_fee_codes_df = active_fee_codes_df[active_fee_codes_df["name"] == fee_code_name]
    logging.debug("active_fee_codes_df: \n%s", active_fee_codes_df.to_string())

    if active_fee_codes_df.empty:
        logging.debug("fee code expired")
        return True
    else:
        logging.debug("fee code not expired")
        return False
    
def is_affordable(balance, price):
    return balance > price

def handle_buy_response(buy_response: dict, best_offer_df: pd.DataFrame):

    global __forbidden_ids_list__
    global __forbidden_ids_temp__

    if "total" in buy_response:
        logging.debug("ITEM WAS BOUGHT")
        logging.debug("%s\n", buy_response)
        return buy_response
    else:
        logging.debug("ITEM COULD NOT BE BOUGHT")
        logging.error("%s\n", buy_response)

        if "generalErrors" in buy_response:
            general_errors_list = buy_response["generalErrors"]

            if "cannot buy from self" in general_errors_list:

                logging.debug("Tried to buy from self")
                logging.debug("adding sale id to forbidden ids")
                __forbidden_ids_list__.append(best_offer_df["id"])
                logging.debug("forbidden_ids_list: %s", str(__forbidden_ids_list__))
            if "some offer(s) already in another shopping cart and/or sold" in general_errors_list:                

                logging.debug("Tried to buy sold item")
                logging.debug("adding sale id to forbidden ids")
                __forbidden_ids_temp__.append(best_offer_df["id"])
                logging.debug("forbidden_ids_temp: %s", str(__forbidden_ids_temp__))
    return None


def log_buy(best_offer: dict, buy_history_df: pd.DataFrame, name: str, selling_price: float, is_very_good_offer: bool):
    logging.debug("--> log_buy(...)")

    """ Log buy into csv file """
    buy_history_df.loc[len(buy_history_df.index)] = [name,
                                               best_offer["price"], selling_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), is_very_good_offer]
    buy_history_df.to_csv(__buy_history_path__, index=False)

def main(use_existing_linked_purchases: bool):    
    logging.debug("bot.py --> main()")

    global __forbidden_ids_list__
    global __forbidden_ids_temp__

    if check_file_older_than(__bot_skinlist_path__, days=64):
        create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=False, use_existing_pricelist=False)

    if check_file_older_than(__bot_skinlist_path__, days=16):
        create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=False, use_existing_pricelist=True)

    if check_better_active_fee_code_available() or check_fee_code_expired() or check_file_older_than(__bot_skinlist_path__, days=4):
        create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=True, use_existing_pricelist=True)
    
    logging.debug("read buy history from csv file")
    buy_history_df = pd.read_csv(__buy_history_path__)
    logging.debug("buy_history_df: \n%s", buy_history_df.to_string())
    
    logging.debug("read skinlist from csv file")
    bot_skinlist_df = pd.read_csv(__bot_skinlist_path__)
    logging.debug("bot_skinlist_df:\n%s", bot_skinlist_df.to_string())
    
    logging.debug("add anzahl column to skinlist")
    column_count = len(bot_skinlist_df.columns)
    bot_skinlist_df.insert(loc=column_count, column="Anzahl",
              value=np.zeros(bot_skinlist_df.shape[0], int), allow_duplicates=True)
    logging.debug("\n%s", bot_skinlist_df.to_string())
    
    logging.debug("create [item name, count] mapping")
    items = bot_skinlist_df["name"]
    counts = np.zeros(bot_skinlist_df.shape[0], int)
    item_counts = [list(tuple) for tuple in (zip(items, counts))]
    logging.debug("\n".join(str(e) for e in item_counts))
    
    logging.info("get inventory")
    inventory_df = get_inventory()
    logging.info("inventory_df: \n%s", inventory_df.to_string())

    logging.info("add counts to items from inventory")
    item_counts = add_count_to_items_from_inventory(item_counts, inventory_df)
    logging.debug("\n".join(str(e) for e in item_counts))  
    del inventory_df

    logging.info("read / create linked purchases dataframe")
    if not use_existing_linked_purchases:
        link_purchases_to_offers.main()

    linked_purchases_df = csvs.read_linked_purchases()
    logging.info("filter only available offers")
    available_offers_df = linked_purchases_df[linked_purchases_df["state"] == "AVAILABLE"].reset_index(drop=True)
    del linked_purchases_df
    
    logging.info("add counts to items from active offers")
    item_counts = add_count_to_items_from_active_offers(item_counts, available_offers_df)
    logging.debug("\n".join(str(e) for e in item_counts))
    del available_offers_df
    
    logging.info("add counts to anzahl column in bot_skinlist_df")
    for entry in item_counts:
        bot_skinlist_df.loc[bot_skinlist_df["name"] == entry[0], "Anzahl"] = entry[1]
    logging.debug("bot_skinlist_df:\n%s", bot_skinlist_df.to_string())
    
    logging.info("entering endless loop")

    while True:
        try:    
            logging.info("**************************************************")      

            # if check_file_older_than(__bot_skinlist_path__, days=64):
            #     create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=False, use_existing_pricelist=False)

            # if check_file_older_than(__bot_skinlist_path__, days=16):
            #     create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=False, use_existing_pricelist=True)

            # if check_better_active_fee_code_available() or check_fee_code_expired() or check_file_older_than(__bot_skinlist_path__, days=4):
            #     create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=True, use_existing_pricelist=True)

            logging.debug("clear forbidden ids temp")
            __forbidden_ids_temp__ = []

            logging.info("bot_skinlist_df:\n%s", bot_skinlist_df.to_string())

            balance = sb.get_balance()["balance"]
            bot_skinlist_df_eff = bot_skinlist_df.loc[bot_skinlist_df["buy_price"] <= balance]

            logging.info("skinlist display")
            logging.info("bot_skinlist_df_eff:\n%s", bot_skinlist_df_eff.to_string())

            for index, row in bot_skinlist_df_eff.iterrows():

                logging.info("--------------------------------------------------")

                name = row["name"]

                logging.info("Processing item %d/%d: %s", index, len(bot_skinlist_df_eff), name)

                good_offers = sb.search(search_item=name, min=0, max=row["buy_price"])
                good_offers_df = pd.DataFrame(good_offers, columns=["id", "price", "img", "market_name", "sbinspect", "inspect", "stickers", "wear", "appid"])
                good_offers_df = good_offers_df[~good_offers_df['id'].isin(__forbidden_ids_list__)]
                good_offers_df = good_offers_df[~good_offers_df['id'].isin(__forbidden_ids_temp__)]
                logging.debug("good_offers_df:\n%s", good_offers_df.to_string())

                if good_offers_df.empty:
                    logging.info("found no good offers, skipping to next item...")
                    continue

                logging.info("found good offers")

                logging.info("checking for very good offers")
                very_good_offers_df = good_offers_df.loc[good_offers_df["price"]
                                                        <= row["buy_price"] * __very_good_offer_percentage__]
                logging.debug("very_good_offers_df: \n%s", very_good_offers_df.to_string())

                if (balance <= __slow_down_balance__) and very_good_offers_df.empty:
                    logging.info(
                        "balance < " + str(__slow_down_balance__) + "€ and no very good offers: skipping to next item...")
                    continue
                
                item_count = row["Anzahl"]

                if item_count > __item_limit__ and (very_good_offers_df.empty or item_count > __very_good_item_limit__):
                    logging.info("conditions were not met, item count exceeds limit, skipping to next item...") 
                    continue             
                
                logging.info("conditions were met, item count doesn't exceed the limit, continueing...")

                while not good_offers_df.empty:
                    
                    logging.debug("while not good_offers_df.empty")
                    logging.debug("good_offers_df:\n%s", good_offers_df.to_string())

                    if item_count > __item_limit__ and (very_good_offers_df.empty or item_count > __very_good_item_limit__):
                        logging.info("conditions were not met, item count exceeds limit, skipping to next item...") 
                        break   

                    logging.info("conditions met, continueing with buying good offers...")

                    logging.info("looking for best offer in good offers")
                    best_offer_df = good_offers_df.loc[good_offers_df["price"].idxmin()]
                    logging.info("best offer:\n%s", best_offer_df.to_string())

                    logging.info("checking affordability...")
                    price = best_offer_df["price"]

                    if not is_affordable(balance, price):
                        logging.info("conditions were not met, not enough funds: skipping to next item...")
                        break

                    logging.info("buying best offer")
                    buy_response = sb.buy_offer(best_offer_df)
                    buy_response = handle_buy_response(buy_response, best_offer_df=best_offer_df)

                    if buy_response:
                        logging.info("BOUGHT OFFER")

                        item_count += 1
                        bot_skinlist_df.at[index, "Anzahl"] = item_count

                        logging.debug("UPDATED ITEM COUNT: IN SKINLIST - %s, IN LOOP - %s",
                                    str(bot_skinlist_df.at[index, "Anzahl"]), str(item_count))

                        log_buy(best_offer_df, buy_history_df, name,
                                row["selling_price"], bool(not very_good_offers_df.empty))
                    else:
                        logging.info("OFFER COULD NOT BE BOUGHT")

                    time.sleep(5)

                    # Refresh offers
                    good_offers = sb.search(search_item=name, min=0, max=row["buy_price"])
                    good_offers_df = pd.DataFrame(good_offers, columns=["id", "price", "img", "market_name", "sbinspect", "inspect", "stickers", "wear", "appid"])
                    logging.debug("__forbidden_ids_list__: %s", __forbidden_ids_list__)
                    logging.debug("good_offers_df:\n%s", good_offers_df.to_string())
                    good_offers_df = good_offers_df[~good_offers_df['id'].isin(__forbidden_ids_list__)]
                    logging.debug("filtering offers with id in forbidden ids list")
                    logging.debug("good_offers_df:\n%s", good_offers_df.to_string())

                    logging.debug("__forbidden_ids_temp__: %s", __forbidden_ids_temp__)
                    logging.debug("good_offers_df:\n%s", good_offers_df.to_string())
                    good_offers_df = good_offers_df[~good_offers_df['id'].isin(__forbidden_ids_temp__)]
                    logging.debug("filtering offers with id in forbidden ids list")
                    logging.debug("good_offers_df:\n%s", good_offers_df.to_string())

                    logging.info("checking for very good offers")
                    very_good_offers_df = good_offers_df.loc[good_offers_df["price"]
                                                            <= row["buy_price"] * __very_good_offer_percentage__]
                    logging.debug("very_good_offers_df: \n%s", very_good_offers_df.to_string())

                    # Guard clause for balance check
                    balance = sb.get_balance()["balance"]
                    if balance <= __slow_down_balance__ and very_good_offers_df.empty:
                        logging.info(f"BALANCE < {__slow_down_balance__}€ AND NO VERY GOOD OFFERS: SKIPPING TO NEXT ITEM...")
                        break

        except Exception as error:
            logging.warning(
                "error:\n%s\n\n occured in while loop... restarting...", str(error))
            continue

    