import logging
from datetime import *
import pandas as pd
import numpy as np
from src.libs import csvs, skinbaron as sb
import time

from src.enums.enums import ApiKey
from src.scripts import analytics, bot_skinlist_checker, link_purchases_to_offers

__api_key__ = ApiKey.API_KEY.value

__base_path__ = "./generated_files/bot"
__buy_history_path__ = __base_path__ + "/BuyHistory.csv"

__base_path_create_bot_skinlist__ = "./generated_files/create_bot_skinlist"
__bot_skinlist_path__ = __base_path_create_bot_skinlist__ + "/bot_skinlist.csv"

__forbidden_ids_list__ = []
__forbidden_ids_temp__ = []

__item_limit__ = 5
__very_good_item_limit__ = 10
__very_good_offer_percentage__ = 0.8
__slow_down_balance__ = 250

def add_count_to_items_from_inventory(item_counts: list, inventory_df: pd.DataFrame):
    logging.debug("--> add_count_to_items_from_inventory()")
    """ Counts Items in item_dictionary and writes count into item_counts """
    if inventory_df.empty:
        return item_counts

    for index, row in inventory_df.iterrows():
        time.sleep(0.05)
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
        time.sleep(0.05)
        logging.info("Processing item %d/%d", index, len(available_offers_df))
        for entry in item_counts:
            if (row["name"] == entry[0]):
                entry[1] += 1
    return item_counts
    
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

            error_messages_sold = [
                "some offer(s) already in another shopping cart and/or sold",
                "some offer(s) are already sold"
            ]

            if "cannot buy from self" in general_errors_list:

                logging.debug("Tried to buy from self")
                logging.debug("adding sale id to forbidden ids")
                __forbidden_ids_list__.append(best_offer_df["id"])
                logging.debug("forbidden_ids_list: %s", str(__forbidden_ids_list__))
            if any(error in general_errors_list for error in error_messages_sold):                

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

    bot_skinlist_checker.main(recalc_prices_if_no_update=True)
    
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
    inventory_df = sb.get_inventory()
    logging.info("inventory_df: \n%s", inventory_df.to_string())

    logging.info("add counts to items from inventory")
    item_counts = add_count_to_items_from_inventory(item_counts, inventory_df)
    logging.debug("\n".join(str(e) for e in item_counts))  
    del inventory_df

    logging.info("read / create linked purchases dataframe")
    if not use_existing_linked_purchases:
        link_purchases_to_offers.main()

    time.sleep(1)

    analytics.main(use_existing_linked_purchases=True)

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
        time.sleep(0.05)
        bot_skinlist_df.loc[bot_skinlist_df["name"] == entry[0], "Anzahl"] = entry[1]
    logging.debug("bot_skinlist_df:\n%s", bot_skinlist_df.to_string())
    
    logging.info("entering endless loop")

    while True:
        time.sleep(0.05)
        try:    
            logging.info("**************************************************")      

            logging.debug("clear forbidden ids temp")
            __forbidden_ids_temp__ = []

            logging.info("bot_skinlist_df:\n%s", bot_skinlist_df.to_string())

            balance = sb.get_balance()["balance"]
            bot_skinlist_df_eff = bot_skinlist_df.loc[bot_skinlist_df["buy_price"] <= balance]

            logging.info("skinlist display")
            logging.info("bot_skinlist_df_eff:\n%s", bot_skinlist_df_eff.to_string())

            for index, row in bot_skinlist_df_eff.iterrows():
                time.sleep(0.05)

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
                    time.sleep(0.05)
                    
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

    
