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

    price_calculation.init_fee_code()   
    price_calculation.clear_plots()     
    
    for index, row in popular_skinlist_df.iterrows():
        name = row["name"]
        logging.info("Processing item %d/%d: %s", index, len(popular_skinlist_df), name)
        
        logging.debug("name:\n%s", name)
        doppler_phase = row["doppler_phase"]
        logging.debug("doppler_phase:\n%s", doppler_phase)

        scraped_sales_for_item_df = scraped_sales_df[(scraped_sales_df["itemName"] == name) & 
                                                     ((pd.isna(scraped_sales_df["dopplerPhase"]) & pd.isna(doppler_phase)) | 
                                                      (scraped_sales_df["dopplerPhase"] == doppler_phase))]
        logging.debug("scraped_sales_for_item_df:\n%s", scraped_sales_for_item_df.tail(100).to_string())

        bot_skinlist_df = pd.concat([bot_skinlist_df, price_calculation.calculate_price_for_item(scraped_sales_for_item_df, True)]).reset_index(drop=True)
        logging.debug("bot_skinlist_df:\n%s", bot_skinlist_df.tail(5).to_string())

    price_calculation.save_slope_stats_csv()

    bot_skinlist_df = bot_skinlist_df.sort_values(["mean_profitability", "tier", "min_profit"], ascending=[True, True, False]).reset_index(drop=True)
    logging.debug("bot_skinlist_df:\n%s", bot_skinlist_df.to_string())  

    logging.info("saving bot skinlist to csv")  
    bot_skinlist_df.to_csv(__bot_skinlist_path__, index=False)

    utils.cache_json_objects_always_overwrite(__bot_skinlist_metadata_path__, {"fee_code_name":price_calculation.fee_code_name, "commission_factor":price_calculation.skinbaron_percentage_win, "our_percentage_win":price_calculation.our_percentage_win})

