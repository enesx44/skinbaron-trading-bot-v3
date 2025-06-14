from src.libs import utils
import src.scripts.scraper_sales as scraper_sales
import src.scripts.db as db
import src.scripts.create_popular_skinlist as create_popular_skinlist
import src.scripts.price_calculation as price_calculation
import pandas as pd
import datetime

import logging

__base_path__ = "./generated_files/create_bot_skinlist"
__bot_skinlist_path__ = __base_path__ + "/bot_skinlist.csv"
__bot_skinlist_metadata_path__ = __base_path__ + "/metadata.json"

__base_path_manual_data__ = "./manual_data"
__base_path_price_calc__ = __base_path_manual_data__ + "/price_calculation"
__base_path_fee_codes__ = __base_path_price_calc__ + "/fee_codes.csv"

def main(should_scrape: bool, use_existing_popular_skinlist: bool, use_existing_pricelist: bool):
    """
    scrapes sales for either an existing popular skinlist or a newly created one.

    Args:
        should_scrape (bool): If False, this overrules all other conditions and is done on existing popular skinlist
                                specifieds if scraping should be done before creating bot skinlist
        use_existing_popular_skinlist (bool): If True, this overrules use_existing_pricelist condition. 
                                                specifies if existing popular skinlist should be used or a new one should be created.
        use_existing_pricelist (bool): Matters only if use_existing_popular_skinlist is False. 
                                        specifies if existing pricelist should be used during creation of popular skinlist or new one should be created.

    Returns:
    """

    logging.debug("create_bot_skinlist.py --> main()")

    if should_scrape:
        scraper_sales.main(use_existing_popular_skinlist=use_existing_popular_skinlist, use_existing_pricelist=use_existing_pricelist)

    popular_skinlist_df = create_popular_skinlist.get_popular_skinlist(use_existing_popular_skinlist=True, use_existing_pricelist=True)
    logging.debug("popular_skinlist_df:\n%s", popular_skinlist_df.head(100).to_string())

    scraped_sales_df = db.read_df_from_db("SELECT * FROM scraped_sales")
    logging.debug("scraped_sales_df:\n%s", scraped_sales_df.head(100).to_string())
    
    bot_skinlist_df = pd.DataFrame(
        columns=["name", "buy_price", "selling_price", "min_profit", "mean_profitability", "tier"])    

    fee_codes_df = pd.read_csv(__base_path_fee_codes__, parse_dates=["expire_date"])
    logging.debug("fee_codes_df: \n%s", fee_codes_df.to_string())

    active_fee_codes_df = fee_codes_df[fee_codes_df["expire_date"] > datetime.datetime.now()]

    if not active_fee_codes_df.empty:
        logging.debug("active fee code available")
        skinbaron_percentage_win = active_fee_codes_df["commission_factor"].min()
        logging.debug("skinbaron_percentage_win: %s", skinbaron_percentage_win)
    else:
        logging.debug("no active fee code available")
        skinbaron_percentage_win = 0.15
        logging.debug("skinbaron_percentage_win: %s", skinbaron_percentage_win)

    price_calculation.init_skinbaron_percentage_win(value=skinbaron_percentage_win)        
    
    for index, row in popular_skinlist_df.iterrows():
        
        name = row["name"]
        logging.debug("name:\n%s", name)
        doppler_phase = row["doppler_phase"]
        logging.debug("doppler_phase:\n%s", doppler_phase)

        scraped_sales_for_item_df = scraped_sales_df[(scraped_sales_df["itemName"] == name) & 
                                                     ((pd.isna(scraped_sales_df["dopplerPhase"]) & pd.isna(doppler_phase)) | 
                                                      (scraped_sales_df["dopplerPhase"] == doppler_phase))]
        logging.debug("scraped_sales_for_item_df:\n%s", scraped_sales_for_item_df.tail(100).to_string())

        bot_skinlist_df = pd.concat([bot_skinlist_df, price_calculation.calculate_price_for_item(scraped_sales_for_item_df)]).reset_index(drop=True)
        logging.debug("bot_skinlist_df:\n%s", bot_skinlist_df.tail(100).to_string())

    bot_skinlist_df = bot_skinlist_df.sort_values(["mean_profitability", "tier", "min_profit"], ascending=[True, True, False]).reset_index(drop=True)
    logging.debug("bot_skinlist_df:\n%s", bot_skinlist_df.to_string())  

    logging.info("saving bot skinlist to csv")  
    bot_skinlist_df.to_csv(__bot_skinlist_path__, index=False)

    utils.cache_json_objects_always_overwrite(__bot_skinlist_metadata_path__, {"commission_factor":price_calculation.skinbaron_percentage_win})

