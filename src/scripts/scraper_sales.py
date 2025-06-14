import logging
import os
import sys

import pandas as pd

import src.scripts.create_popular_skinlist as create_popular_skinlist
import src.libs.skinbaron as sb
import src.libs.utils as utils
import src.scripts.db as db

__base_path__ = "./generated_files/scraper_sales"
__cached_sales_path__ = __base_path__ + "/cached_sales.json"

def get_cached_sales() -> dict:
    logging.debug("scraper_sales.py --> get_cached_sales()")
    logging.debug("scraper_sales.py <-- get_cached_sales()")
    return utils.read_cached_json_objects(__cached_sales_path__)

def delete_cached_sales():
    logging.debug("scraper_sales.py --> delete_cached_sales()")
    global __cached_sales_path__

    if os.path.exists(__cached_sales_path__):
        logging.info("deleting cached sales for scraper")
        os.remove(__cached_sales_path__)
    else:
        print("tried delteing cached sales for scraper but file does not exist")
    logging.debug("scraper_sales.py <-- delete_cached_sales()")

def add_doppler_phase_column(df: pd.DataFrame) -> pd.DataFrame:
    if "dopplerPhase" in df.columns:
        # Fill empty cells with None, leave non-empty cells untouched
        df["dopplerPhase"] = df["dopplerPhase"].apply(lambda x: x if pd.notna(x) else None)
    else:
        # Add the column and set every cell to None
        df["dopplerPhase"] = None
        
    return df

# return none if the request times out
# return the response if the request is successful
def scrape_sales_for_item(market_hash_name: str, doppler_phase: str | None) -> dict:
    logging.debug("scraper_sales.py --> scrape_sales_for_item()")

    if "StatTrak™" in market_hash_name:
        is_statTrak = True
    else:
        is_statTrak = False
        
    if "Souvenir" in market_hash_name:
        is_souvenir = True
    else:
        is_souvenir = False

    logging.info("scraping sales for item: %s", market_hash_name)
    if doppler_phase is not None:
        logging.info("doppler_phase: %s", doppler_phase)

    response = sb.get_newest_sales_30_days(market_hash_name, is_statTrak, is_souvenir, doppler_phase)

    logging.debug("scraper_sales.py <-- scrape_sales_for_item()")

    return response

def main(use_existing_popular_skinlist: bool, use_existing_pricelist: bool):
    """
    scrapes sales for either an existing popular skinlist or a newly created one.

    Args:
        use_existing_popular_skinlist (bool): If True, this overrules use_existing_pricelist condition. 
                                                specifies if existing popular skinlist should be used or a new one should be created.
        use_existing_pricelist (bool): Matters only if use_existing_popular_skinlist is False. 
                                        specifies if existing pricelist should be used during creation of popular skinlist or new one should be created.

    Returns:
        None: just adds scraped sales to the db.
    """

    logging.debug("scraper_sales.py --> main()")

    popular_skinlist_df = create_popular_skinlist.get_popular_skinlist(use_existing_popular_skinlist=use_existing_popular_skinlist, use_existing_pricelist=use_existing_pricelist)

    if use_existing_popular_skinlist == False:
        logging.info("reading cached sales from newly created popular skinlist")
        cached_sales = get_cached_sales()
        if cached_sales == None:
            logging.info("cached sales file does not exist, can not continue")
            sys.exit(1)
    else:
        logging.info("scraping sales for all items on popular skinlist")

        logging.info("trying to read cached json objects")
        cached_sales = get_cached_sales()
        last_cached_sale_found = False
        if cached_sales:
            last_cached_sale = cached_sales[-1]

        logging.info("looping through popular skinlist")
        if cached_sales: 
            logging.info("skipping to last cached sale and continueing from there")
        for index, row in popular_skinlist_df.iterrows():
            
            name = row["name"]
            doppler_phase = row["doppler_phase"]

            if cached_sales:
                if (name != last_cached_sale["itemName"]) and (not last_cached_sale_found):
                    continue
                else:
                    if not last_cached_sale_found:
                        logging.info("found last cached sale")
                        last_cached_sale_found = True
                        continue
                
            scraped_sales = scrape_sales_for_item(name, doppler_phase)

            if scraped_sales is None:
                continue
                
            if len(scraped_sales) == 0:
                logging.info("skipping to next item because there were no sales scraped")
                continue

            logging.info("creating scraped sales dataframe from scraped sales dictionary")
            scraped_sales_df = pd.DataFrame(scraped_sales)
            logging.debug("scraped_sales_df:\n%s", scraped_sales_df.to_string())

            # select entries where row["name"] is == itemName
            # this is necessary because the name is not always the same as the itemName (e.g. not painted knifes)
            logging.info("filtering sales so itemName matches name")
            scraped_sales_df = scraped_sales_df[scraped_sales_df["itemName"] == name]
            logging.debug("scraped_sales_df:\n%s", scraped_sales_df.to_string())
            
            logging.info("caching scraped sales")
            utils.cache_json_objects(__cached_sales_path__, scraped_sales)

        logging.info("finished scraping sales for all items on popular skinlist")

        logging.info("reading final cached sales")
        cached_sales = get_cached_sales()
        if cached_sales == None:
            logging.info("cached sales file does not exist, can not continue")
            sys.exit(1)

    logging.info("recreating scraped sales dataframe from all cached sales")
    new_scraped_sales_df = pd.DataFrame(cached_sales)
    logging.debug("new_scraped_sales_df:\n%s", new_scraped_sales_df.to_string())
    
    logging.info("adding dopplerPhase column if needed else setting NaN to None")
    new_scraped_sales_df = add_doppler_phase_column(new_scraped_sales_df)
    logging.debug("new_scraped_sales_df:\n%s", new_scraped_sales_df.head(100).to_string())
    logging.debug("new_scraped_sales_df:\n%s", new_scraped_sales_df.tail(100).to_string())
    logging.debug("len(new_scraped_sales_df):\n%s", len(new_scraped_sales_df))

    try:
        logging.info("reading presisted scraped sales dataframe from db")
        old_scraped_sales_df = db.get_sales()
        logging.debug("old_scraped_sales_df:\n%s", old_scraped_sales_df.to_string())
        
        logging.info("adding dopplerPhase column if needed else setting NaN to None")
        old_scraped_sales_df = add_doppler_phase_column(old_scraped_sales_df)
        logging.debug("old_scraped_sales_df:\n%s", old_scraped_sales_df.head(100).to_string())
        logging.debug("old_scraped_sales_df:\n%s", old_scraped_sales_df.tail(100).to_string())
        logging.debug("len(old_scraped_sales_df):\n%s", len(old_scraped_sales_df))
    except:
        logging.info("an error occured while reading persisted scraped sales dataframe from db")
        logging.info("probably the table does not exist yet")
        logging.info("setting old scraped sales dataframe to None")
        old_scraped_sales_df = None

    if old_scraped_sales_df is None:
        logging.info("no persisted sales found in db")
        
        combined_df = new_scraped_sales_df
    else:
        logging.info("persisted sales found in db")

        logging.info("removing duplicates from new scraped sales dataframe")
        new_scraped_sales_df = new_scraped_sales_df[~new_scraped_sales_df.apply(tuple, axis=1).isin(old_scraped_sales_df.apply(tuple, axis=1))]
        logging.debug("new_scraped_sales_df:\n%s", new_scraped_sales_df.to_string())
        logging.debug("len(new_scraped_sales_df):\n%s", len(new_scraped_sales_df))

        logging.info("combining old and new scraped sales dataframes")
        combined_df = pd.concat([old_scraped_sales_df, new_scraped_sales_df]).reset_index(drop=True)
        logging.debug("combined_df:\n%s", combined_df.to_string())  
        logging.debug("len(combined_df):\n%s", len(combined_df))

    logging.info("sorting combined scraped sales by itemName and dateSold")
    combined_df = combined_df.sort_values(by=["itemName", "dateSold", "dopplerPhase"], ascending=[True, True, True])
    logging.debug("combined_df:\n%s", combined_df.head(100).to_string())
    logging.debug("combined_df:\n%s", combined_df.tail(100).to_string())

    logging.info("saving combined scraped sales to db")
    db.set_sales(df=combined_df)

    logging.info("deleting cached sales")
    delete_cached_sales()

    logging.debug("scraper_sales.py <-- main()")

