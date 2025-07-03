import gc
from io import StringIO
import logging
import datetime
import math
import os
import sys

import pandas as pd
import numpy as np

import src.scripts.create_pricelist as create_pricelist
import src.scripts.scraper_sales as scraper_sales
import src.libs.utils as utils

logging.debug("----> create_popular_skinlist.py")

# config variables

# 80 / 20 rule
__cutoff__ = 0.8

# we get the sales from 30 days ago
# but we only include the last 15 days
__days_to_include_for_popularity__ = 30 // 2

# max sales api gives per item is 100 but since we only use 15 days we divide it by 2
__max_sales_per_item__ = 100 // 2

# we only include items that have at least 10 sales in the last 15 days
__sales_count_threshold_in_last_X_days__ = __max_sales_per_item__ // 6

__base_path__ = "./generated_files/create_popular_skinlist"
os.makedirs(__base_path__, exist_ok=True)

__cached_sales_path__ = __base_path__ + "/cached_sales.json"
__popular_skinlist_path__ = __base_path__ + "/popular_skinlist.csv"

__base_path_scraper__ = "./generated_files/scraper_sales"
os.makedirs(__base_path_scraper__, exist_ok=True)

__cached_sales_path_scraper__ = __base_path_scraper__ + "/cached_sales.json"

def get_cached_sales() -> dict:
    logging.debug("create_popular_skinlist.py --> get_cached_sales()")
    logging.debug("create_popular_skinlist.py <-- get_cached_sales()")
    return utils.read_cached_json_objects(__cached_sales_path__)

def delete_cached_sales():
    logging.debug("create_popular_skinlist.py --> delete_cached_sales()")
    global __cached_sales_path__

    if os.path.exists(__cached_sales_path__):
        logging.info("deleting cached sales for popular skinlist")
        os.remove(__cached_sales_path__)
    else:
        print("tried delteing cached sales for popular skinlist but file does not exist")
    logging.debug("create_popular_skinlist.py <-- delete_cached_sales()")

def read_popular_skinlist() -> pd.DataFrame:
    logging.info("reading popular_skinlist.csv")
    popular_skinlist_df = pd.read_csv(__popular_skinlist_path__)
    
    logging.info("replacing NaN values with None")
    popular_skinlist_df = popular_skinlist_df.fillna(np.nan).replace([np.nan], [None])
    logging.debug("popular_skinlist_df:\n%s", popular_skinlist_df.head().to_string())

    return popular_skinlist_df

def get_popular_skinlist(use_existing_popular_skinlist: bool, use_existing_pricelist: bool) -> pd.DataFrame:
    """
    Gets a popular skinlist based on the specified conditions.

    Args:
        use_existing_popular_skinlist (bool): If True, this overrules use_existing_pricelist condition. 
                                                specifies if existing popular skinlist should be used or a new one should be created.
        use_existing_pricelist (bool): Matters only if use_existing_popular_skinlist is False. 
                                        specifies if existing pricelist should be used during creation of popular skinlist or new one should be created.

    Returns:
        [pd.DataFrame]: the resulting popular skinlist.
    """
    logging.debug("create_popular_skinlist.py --> get_popular_skinlist()")

    if use_existing_popular_skinlist:
        popular_skinlist_df = read_popular_skinlist()
    else:
        popular_skinlist_df = main(use_existing_pricelist=use_existing_pricelist)
    
    logging.debug("create_popular_skinlist.py <-- get_popular_skinlist()")
    return popular_skinlist_df

def main(use_existing_pricelist: bool) -> pd.DataFrame:
    logging.debug("create_popular_skinlist.py --> main()")

    pricelist_df = create_pricelist.get_pricelist(use_existing_pricelist=use_existing_pricelist)

    logging.info("scraping sales for all items on pricelist")

    x_days_ago_date = (datetime.datetime.now() - datetime.timedelta(days=__days_to_include_for_popularity__)).date()

    logging.info("trying to read cached json objects")
    cached_sales = get_cached_sales()
    last_cached_sale_found = False
    if cached_sales:
        last_cached_sale = cached_sales[-1]

    logging.info("looping through pricelist")
    if cached_sales: 
        logging.info("skipping to last cached sale and continueing from there")
    for index, row in pricelist_df.iterrows():

        marketHashName = row["marketHashName"]

        if cached_sales:
            if (marketHashName != last_cached_sale["itemName"]) and (not last_cached_sale_found):
                continue
            else:
                if not last_cached_sale_found:
                    logging.info("found last cached sale")
                    last_cached_sale_found = True
                    continue
                
        logging.info("Processing item %d/%d: %s", index, len(pricelist_df), marketHashName)

        scraped_sales = scraper_sales.scrape_sales_for_item(marketHashName, row["dopplerClassName"])

        if scraped_sales is None:
            logging.info("skipping to next item because scraped_sales is None")
            continue
            
        if len(scraped_sales) == 0:
            logging.info("skipping to next item because there were no sales scraped")
            continue

        logging.info("creating scraped sales dataframe from scraped sales dictionary")
        scraped_sales_df = pd.DataFrame(scraped_sales)
        logging.debug("scraped_sales_df:\n%s", scraped_sales_df.head().to_string())

        # select entries where marketHashName is == itemName
        # this is necessary because the marketHashName is not always the same as the itemName (e.g. not painted knifes)
        logging.info("filtering sales so itemName matches marketHashName")
        scraped_sales_df = scraped_sales_df[scraped_sales_df["itemName"] == marketHashName]
        logging.debug("scraped_sales_df:\n%s", scraped_sales_df.head().to_string())

        logging.info("transforming dateSold column to datetime")
        scraped_sales_df["dateSold"] = pd.to_datetime(scraped_sales_df["dateSold"], format="ISO8601").dt.date
        logging.debug("scraped_sales_df:\n%s", scraped_sales_df.head().to_string())

        logging.info("filtering scraped sales from last x days")
        scraped_sales_df = scraped_sales_df[scraped_sales_df['dateSold'] >= x_days_ago_date]
        logging.debug("scraped_sales_df:\n%s", scraped_sales_df.head().to_string())

        logging.info("checking if sales threshold is met")
        if len(scraped_sales_df) > __sales_count_threshold_in_last_X_days__: 
            logging.info("sales threshold is met")         
            logging.info("caching scraped sales")
            utils.cache_json_objects(__cached_sales_path__, scraped_sales)
        
    del scraped_sales
    gc.collect()

    logging.info("finished scraping sales for all items from pricelist")

    cached_sales = get_cached_sales()
    if cached_sales == None:
        logging.info("cached sales file does not exist, can not continue")
        sys.exit(1)        

    buf = StringIO()     
    
    logging.info("recreating scraped sales dataframe from all cached sales")
    scraped_sales_df = pd.DataFrame(cached_sales)
    logging.debug("scraped_sales_df:\n%s", scraped_sales_df.head().to_string())
    scraped_sales_df.info(buf=buf)
    logging.debug("info:\n%s", buf.getvalue())
    utils.clear_buf(buf=buf)

    logging.info("adding dopplerPhase column if not present")
    if not "dopplerPhase" in scraped_sales_df.columns:
        scraped_sales_df["dopplerPhase"] = pd.Series()
    
    logging.info("replacing NaN values with empty String (necessary for grouping (NaN values in dopplerPhase column))")
    scraped_sales_df = scraped_sales_df.fillna("")
    logging.debug("scraped_sales_df:\n%s", scraped_sales_df.head().to_string())

    logging.info("grouping scraped sales by itemName and dopplerPhase to get the sales count for each item")
    popular_skinlist_df = scraped_sales_df.groupby(['itemName', 'dopplerPhase']).size().reset_index(name="sales_in_last_x_days")

    del scraped_sales_df
    gc.collect()

    logging.debug("popular_skinlist_df:\n%s", popular_skinlist_df.head().to_string())
    popular_skinlist_df.info(buf=buf)
    logging.debug("info:\n%s", buf.getvalue())
    utils.clear_buf(buf=buf)
    
    logging.info("sorting popular skinlist dataframe by sales count in descending order")
    popular_skinlist_df = popular_skinlist_df.sort_values(by="sales_in_last_x_days", ascending=False).reset_index(drop=True)
    logging.debug("popular_skinlist_df:\n%s", popular_skinlist_df.head(100).to_string())
    
    logging.info("keep only the top 80%% of popular items by recent sales")
    popular_skinlist_df = popular_skinlist_df.head(math.ceil(len(popular_skinlist_df) * __cutoff__))
    logging.debug("popular_skinlist_df:\n%s", popular_skinlist_df.tail(100).to_string())
    popular_skinlist_df.info(buf=buf)
    logging.debug("info:\n%s", buf.getvalue())
    utils.clear_buf(buf=buf)
    
    del buf
    gc.collect()

    logging.info("renaming columns of popular skinlist dataframe")
    popular_skinlist_df = popular_skinlist_df.rename(columns={"itemName": "name", "dopplerPhase": "doppler_phase"})
    logging.debug("popular_skinlist_df:\n%s", popular_skinlist_df.head(100).to_string())
    
    logging.info("saving popular_skinlist dataframe to csv")
    popular_skinlist_df.to_csv(__popular_skinlist_path__, index=False)
    
    logging.info("saving cached sales for scraper before deletion")
    utils.cache_json_objects(__cached_sales_path_scraper__, get_cached_sales())

    logging.info("deleting cached sales")
    delete_cached_sales()

    logging.debug("create_popular_skinlist.py <-- main()")
    return popular_skinlist_df