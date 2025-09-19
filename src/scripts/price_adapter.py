import os
from src.libs import utils
from src.libs import csvs
from datetime import datetime
import time
import logging
from src.scripts import link_purchases_to_offers, price_calculation
from src.scripts import scraper_sales
import pandas as pd
from src.libs import skinbaron as sb

__base_path__ = "./generated_files/price_adapter"
os.makedirs(__base_path__, exist_ok=True)
__cached_df_path__ = __base_path__ + "/cache.csv"
__recom_prices_cache_path__ = __base_path__ + "/recom_prices.json"
__last_price_adapt_path__ = __base_path__ + "/last_price_adapt.csv"

__base_path_create_bot_skinlist__ = "./generated_files/create_bot_skinlist"
os.makedirs(__base_path_create_bot_skinlist__, exist_ok=True)
__bot_skinlist_path__ = __base_path_create_bot_skinlist__ + "/bot_skinlist.csv"

__our_win_percentage_min__ = 0.05

__should_adapt__ = True

def create_item(sale_id: str, price: float) -> dict:
    return { "saleid": sale_id, "price": price }

def add_recommended_price_column(linked_purchases_df: pd.DataFrame, use_current_bot_skinlist: bool) -> pd.DataFrame:
    logging.info("Extracting unique names from linked_purchases_df")
    unique_names = linked_purchases_df["name"].unique()
    logging.debug("Unique names count: %s", len(unique_names))

    # Load cached data
    cached_recommended_prices = utils.read_cached_json_objects(__recom_prices_cache_path__)
    if cached_recommended_prices is None:
        cached_recommended_prices = {}

    # Determine which items still need to be processed
    already_processed = set(cached_recommended_prices.keys())
    remaining_names = [name for name in unique_names if name not in already_processed]

    logging.info("Resuming from cache. Skipping %d already processed items", len(already_processed))

    # Start from cached data
    recommended_prices = cached_recommended_prices.copy()

    if use_current_bot_skinlist:
        bot_skinlist_df = csvs.read_df(__bot_skinlist_path__)

    logging.info("initialize fee code")
    price_calculation.init_fee_code()

    logging.info("Looping through unique names")
    for index, name in enumerate(remaining_names, start=1):  # Add index for tracking progress
        logging.info("Processing item %d/%d: %s", index, len(remaining_names), name)  # Progress logging

        if use_current_bot_skinlist:

            # find row for name in bot_skinlist
            row_in_bot_skinlist = bot_skinlist_df[bot_skinlist_df["name"] == name]
            logging.debug("row_in_bot_skinlist: \n%s", row_in_bot_skinlist.to_string())

            if row_in_bot_skinlist.empty:
                logging.debug("couldn't find recom price in bot skinlist, continueing with scraping...")
            else:
                logging.debug("found recom price info in bot skinlist, saving and continueing with next item...")
                recommended_prices[name] = float(row_in_bot_skinlist.iloc[0]["selling_price"])
                utils.cache_json_objects_always_overwrite(__recom_prices_cache_path__, recommended_prices)
                continue

        
        logging.info("Scraping sales for %s", name)
        sales_data = scraper_sales.scrape_sales_for_item(market_hash_name=name, doppler_phase=None)

        if not sales_data:
            logging.info("Skipping %s as no sales data was retrieved", name)
            continue
        
        sales_df = pd.DataFrame(sales_data)
        logging.debug("Sales DataFrame:\n%s", sales_df.to_string())

        logging.info("Filtering sales for the same item name")
        sales_df = sales_df[sales_df["itemName"] == name]

        if sales_df.empty:
            logging.info("Skipping %s as no matching sales found", name)
            continue

        logging.info("Adding doppler phase column for price calculation")
        sales_df = scraper_sales.add_doppler_phase_column(sales_df)

        logging.info("Calculating recommended price")
        price_data_df = price_calculation.calculate_price_for_item(sales_df, False)

        if price_data_df is None or price_data_df.empty:
            logging.info("Skipping %s as no price data was available", name)
            continue
        else:            
            logging.debug("Price DataFrame:\n%s", price_data_df.to_string())

        recommended_prices[name] = float(price_data_df.iloc[0]["selling_price"])
        utils.cache_json_objects_always_overwrite(__recom_prices_cache_path__, recommended_prices)

    logging.info("Adding recommended prices to linked_purchases_df")
    linked_purchases_df["recommended_price"] = linked_purchases_df["name"].map(recommended_prices)

    return linked_purchases_df

def create_cache_df(use_existing_linked_purchases: bool, use_current_bot_skinlist: bool) -> pd.DataFrame:
    if not use_existing_linked_purchases:
        link_purchases_to_offers.main()

    linked_purchases_df = csvs.read_linked_purchases()

    linked_purchases_df = linked_purchases_df[linked_purchases_df["state"] == "AVAILABLE"].sort_values(by="buy_date", ascending=True).reset_index(drop=True)
    logging.debug("linked_purchases: \n%s", linked_purchases_df.to_string())

    linked_purchases_df = add_recommended_price_column(linked_purchases_df=linked_purchases_df, use_current_bot_skinlist=use_current_bot_skinlist)
    logging.debug("linked_purchases: \n%s", linked_purchases_df.to_string())
    linked_purchases_df.to_csv(__cached_df_path__, index=False)
    delete_recom_prices_cache()
    return linked_purchases_df

def get_lowest_price_on_sb(search_item: str, current_max: float, min: float = None) -> float:
    original_max = current_max
    retry_count = 0  # Track how many times the API is called

    search_result = sb.search(search_item=search_item, min=min, max=current_max, tradelocked=False)

    if search_result is not None:
        search_df = pd.DataFrame(search_result)

        while search_df.empty:
            current_max *= 1.2  # Instead of adding, multiply for faster scaling
            retry_count += 1  # Track retries

            if retry_count > 10 or current_max >= max(original_max * 10, 2):  # Stop condition
                return None

            search_result = sb.search(search_item=search_item, min=min, max=current_max, tradelocked=False)

            if search_result is not None:
                search_df = pd.DataFrame(search_result)

        return search_df["price"].min() - 0.01
    else:
        return None


def chunk_list(items: list, chunk_size: int = 50) -> list:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

def edit_prices(items: list):
    chunked_items = chunk_list(items, 50)
    
    for chunk in chunked_items:
        sb.edit_price_multi(item_chunk=chunk)

def delete_cached_df():
    logging.debug("price_adapter.py --> delete_cached_df()")
    global __cached_df_path__

    if os.path.exists(__cached_df_path__):
        logging.info("deleting cache")
        os.remove(__cached_df_path__)
    else:
        print("tried delteing cache but file does not exist")
    logging.debug("price_adapter.py <-- delete_cached_df()")

def delete_recom_prices_cache():
    logging.debug("price_adapter.py --> delete_recom_prices_cache()")
    global __recom_prices_cache_path__

    if os.path.exists(__recom_prices_cache_path__):
        logging.info("deleting cache")
        os.remove(__recom_prices_cache_path__)
    else:
        print("tried delteing cache but file does not exist")
    logging.debug("price_adapter.py <-- delete_recom_prices_cache()")

def check_price_adapt_needed(use_existing_linked_purchases: bool, use_current_bot_skinlist: bool):
    logging.debug("--> check_price_adapt_needed()")

    today = datetime.today().date()
    logging.debug("today: %s", today)

    logging.info("reading last price adaptation csv")
    try:
        last_adapt_df = csvs.read_df(__last_price_adapt_path__, parse_dates_columns=["last_price_adapt"])
        last_adapt_date = last_adapt_df["last_price_adapt"].iloc[0].date()
    except FileNotFoundError:
        logging.warning("last_price_adapt.csv not found, assuming no previous adaptations")
        last_adapt_date = datetime(1970, 1, 1).date()

    logging.debug("last_adapt_date: %s", last_adapt_date)

    days_since_last_adapt = (today - last_adapt_date).days
    logging.debug("days_since_last_adapt: %d", days_since_last_adapt)

    if days_since_last_adapt >= 4:
        logging.info("1 week passed since last price adaptation, running main()")

        main(
            use_existing_linked_purchases=use_existing_linked_purchases,
            use_current_bot_skinlist=use_current_bot_skinlist
        )

        logging.info("updating last_price_adapt.csv")
        new_df = pd.DataFrame({"last_price_adapt": [today.strftime("%Y-%m-%d")]})
        csvs.save_df(new_df, __last_price_adapt_path__)

        logging.info("creating linked purchases dataframe")
        link_purchases_to_offers.main()

        time.sleep(1)
    else:
        logging.info("price adaptation not needed yet")

    logging.debug("<-- check_price_adapt_needed()")

def main(use_existing_linked_purchases: bool, use_current_bot_skinlist: bool):

    try:  
        logging.info("reading cached_df")      
        cache_df = pd.read_csv(__cached_df_path__, parse_dates=["buy_date", "offer_date_created", "offer_date_trade_unlock", "offer_date_sold"])
    except:
        logging.info("reading cached_df didnt work setting to none")   
        cache_df = None

    if cache_df is None:
        logging.info("creating cache_df to fill linked_purchases_df_with_recom_price")  
        linked_purchases_df_with_recom_price = create_cache_df(use_existing_linked_purchases=use_existing_linked_purchases, use_current_bot_skinlist=use_current_bot_skinlist)
    else:
        logging.info("setting linked_purchases_df_with_recom_price to be cache")  
        linked_purchases_df_with_recom_price = cache_df

    items_to_adapt = []

    borderline_offers_changes_df = pd.DataFrame(columns=["name", "old_price", "new_price", "price_change"])
    tolerateable_offers_changes_df = pd.DataFrame(columns=["name", "old_price", "new_price", "price_change"])
    acceptable_offers_changes_df = pd.DataFrame(columns=["name", "old_price", "new_price", "price_change"])

    # -------------------------------------------------------------------------------------

    # if recom price
    # recom price
    # else
    # lowest price on skinbaron - 0.01

    logging.info("filtering offers that are older than 6 months")
    borderline_offers_df = linked_purchases_df_with_recom_price[linked_purchases_df_with_recom_price["buy_date"].dt.date < utils.get_date_n_months_ago(6)].reset_index(drop=True)
    logging.debug("borderline_offers_df: \n%s", borderline_offers_df.to_string())

    for index, row in borderline_offers_df.iterrows():

        name = row["name"]
        
        logging.info("Processing item %d/%d: %s", index, len(borderline_offers_df), name)

        sale_id = row["sale_id"]
        logging.debug("sale_id: %s", sale_id)

        if pd.isna(sale_id) or str(sale_id).strip().lower() in ("", "nan", "none"):
            logging.debug("sale_id is effectively missing, skipping..")
            continue

        current_price = row["selling_price"]
        logging.debug("current_price: %s", current_price)

        recommended_price = row["recommended_price"]
        logging.debug("recommended_price: %s", recommended_price)

        min_price = row["min_selling_price"]
        logging.debug("min_price: %s", min_price)  # Calculate how many weeks the offer is beyond 6 months ago

        # Calculate how many weeks the offer is beyond 6 months ago
        buy_date = row["buy_date"].date()
        six_months_ago = utils.get_date_n_months_ago(6)
        weeks_past_six_months = max(0, (six_months_ago - buy_date).days // 7)
        logging.debug("weeks_past_six_months: %d", weeks_past_six_months)

        if not pd.isna(recommended_price):
            logging.debug("recommended_price exists")
            discount_factor = max(0, 1 - 0.005 * weeks_past_six_months)  # 0.5% per week
            logging.debug("discount_factor (recommended): %.4f", discount_factor)
            price_to_set = recommended_price * discount_factor
        else:
            logging.debug("recommended_price doesn't exist")
            discount_factor = max(0, 1 - 0.01 * weeks_past_six_months)  # 1% per week
            logging.debug("discount_factor (min price): %.4f", discount_factor)
            price_to_set = min_price * discount_factor
        
        price_to_set = round(price_to_set, 2)
        logging.debug("price_to_set: %s", price_to_set)

        if current_price == price_to_set:
            logging.warning("best price already set")
            logging.info("------------------------------------------------------")
            continue

        items_to_adapt.append(create_item(sale_id=sale_id, price=price_to_set))

        new_row = pd.DataFrame([{"name":name, "old_price":current_price, "new_price":price_to_set, "price_change":price_to_set-current_price}])

        borderline_offers_changes_df = pd.concat([borderline_offers_changes_df, new_row], ignore_index=True)
        logging.info("------------------------------------------------------")
    
    # -------------------------------------------------------------------------------------

    # if recom price
    # max ( recom price, min price)
    # else
    # lowest price on skinbaron above min price if exists else min price 

    logging.info("filtering offers that are between 3 - 6 month(s) old")
    tolerateable_offers_df = linked_purchases_df_with_recom_price[(linked_purchases_df_with_recom_price["buy_date"].dt.date >= utils.get_date_n_months_ago(6)) & 
                                                 (linked_purchases_df_with_recom_price["buy_date"].dt.date <= utils.get_date_n_months_ago(3))].reset_index(drop=True)
    logging.debug("tolerateable_offers_df: \n%s", tolerateable_offers_df.to_string())

    for index, row in tolerateable_offers_df.iterrows():

        name = row["name"]

        logging.info("Processing item %d/%d: %s", index, len(tolerateable_offers_df), name)

        sale_id = row["sale_id"]
        logging.debug("sale_id: %s", sale_id)

        if pd.isna(sale_id) or str(sale_id).strip().lower() in ("", "nan", "none"):
            logging.debug("sale_id is effectively missing, skipping..")
            continue

        current_price = row["selling_price"]
        logging.debug("current_price: %s", current_price)

        recommended_price = row["recommended_price"]
        logging.debug("recommended_price: %s", recommended_price)

        min_price = row["min_selling_price"]
        logging.debug("min_price: %s", min_price)

        if not pd.isna(recommended_price):
            price_to_set = max(recommended_price, min_price)

        else:
            lowest_price_on_sb = get_lowest_price_on_sb(search_item=name, current_max=(min_price + 0.01) * 1.2, min=min_price + 0.01)

            if not lowest_price_on_sb:
                price_to_set = min_price
            else:
                logging.debug("lowest_price_on_sb: %s", lowest_price_on_sb)

                price_to_set = lowest_price_on_sb
        
        price_to_set = round(price_to_set, 2)
        logging.debug("price_to_set: %s", price_to_set)

        if current_price == price_to_set:
            logging.warning("best price already set")
            logging.info("------------------------------------------------------")
            continue
        
        new_row = pd.DataFrame([{"name":name, "old_price":current_price, "new_price":price_to_set, "price_change":price_to_set-current_price}])

        tolerateable_offers_changes_df = pd.concat([tolerateable_offers_changes_df, new_row], ignore_index=True)

        items_to_adapt.append(create_item(sale_id=sale_id, price=price_to_set))
        logging.info("------------------------------------------------------")

    # -------------------------------------------------------------------------------------
    
    # if recom price
    # recom price if enough profit margin
    # else
    # lowest price on skinbaron above enough profit margin

    logging.info("filtering offers that are less than 3 months old")
    acceptable_offers_df = linked_purchases_df_with_recom_price[linked_purchases_df_with_recom_price["buy_date"].dt.date > utils.get_date_n_months_ago(3)].reset_index(drop=True)
    logging.debug("acceptable_offers_df: \n%s", acceptable_offers_df.to_string())

    for index, row in acceptable_offers_df.iterrows():

        name = row["name"]

        logging.info("Processing item %d/%d: %s", index, len(acceptable_offers_df), name)

        sale_id = row["sale_id"]
        logging.debug("sale_id: %s", sale_id)

        if pd.isna(sale_id) or str(sale_id).strip().lower() in ("", "nan", "none"):
            logging.debug("sale_id is effectively missing, skipping..")
            continue

        current_price = row["selling_price"]
        logging.debug("current_price: %s", current_price)

        recommended_price = row["recommended_price"]
        logging.debug("recommended_price: %s", recommended_price)

        min_price = row["min_selling_price"]
        logging.debug("min_price: %s", min_price)

        commission_factor = row["commission_factor"]
        logging.debug("commission_factor: %s", commission_factor)

        desired_min_selling_price = min_price / (1 - __our_win_percentage_min__)

        if not pd.isna(recommended_price):

            if recommended_price > desired_min_selling_price:
                price_to_set = recommended_price
            else:
                logging.warning("couldnt adapt acceptable offer %s with sale_id: %s", name, sale_id)
                logging.info("not enough profit margin")
                continue
            
        else:
            lowest_price_on_sb = get_lowest_price_on_sb(search_item=name, current_max=(desired_min_selling_price + 0.01) * 1.2, min=desired_min_selling_price + 0.01)

            if not lowest_price_on_sb:
                logging.warning("couldnt adapt acceptable offer %s with sale_id: %s", name, sale_id)
                logging.info("couldnt find lowest price on sb with enough profit margin")
                continue

            logging.debug("lowest_price_on_sb: %s", lowest_price_on_sb)

            price_to_set = lowest_price_on_sb
        
        price_to_set = round(price_to_set, 2)
        logging.debug("price_to_set: %s", price_to_set)

        if current_price == price_to_set:
            logging.warning("best price already set")
            logging.info("------------------------------------------------------")
            continue
        
        new_row = pd.DataFrame([{"name":name, "old_price":current_price, "new_price":price_to_set, "price_change":price_to_set-current_price}])

        acceptable_offers_changes_df = pd.concat([acceptable_offers_changes_df, new_row], ignore_index=True)

        items_to_adapt.append(create_item(sale_id=sale_id, price=price_to_set))
        logging.info("------------------------------------------------------")

    # -------------------------------------------------------------------------------------

    logging.debug(utils.prettyprint(items_to_adapt))

    borderline_offers_changes_df = borderline_offers_changes_df.sort_values("price_change").reset_index(drop=True)
    logging.debug("borderline_offers_changes_df: \n%s", borderline_offers_changes_df.to_string())

    tolerateable_offers_changes_df = tolerateable_offers_changes_df.sort_values("price_change").reset_index(drop=True)
    logging.debug("tolerateable_offers_changes_df: \n%s", tolerateable_offers_changes_df.to_string())

    acceptable_offers_changes_df = acceptable_offers_changes_df.sort_values("price_change").reset_index(drop=True)
    logging.debug("acceptable_offers_changes_df: \n%s", acceptable_offers_changes_df.to_string())

    if __should_adapt__:
        edit_prices(items=items_to_adapt)
        delete_cached_df()
            

        

    