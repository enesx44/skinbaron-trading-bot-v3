import logging
from datetime import datetime

import pandas as pd

from src.libs import csvs, utils

__base_path__ = "./generated_files/bot_skinlist_checker"
__last_updated_path__ = __base_path__ + "/last_updates.csv"

__base_path_create_bot_skinlist__ = "./generated_files/create_bot_skinlist"
__bot_skinlist_metadata_path__ = __base_path_create_bot_skinlist__ + "/metadata.json"

__base_path_manual_data__ = "./manual_data"
__base_path_price_calc__ = __base_path_manual_data__ + "/price_calculation"
__base_path_fee_codes__ = __base_path_price_calc__ + "/fee_codes.csv"


# Find best available fee code (lowest rank, not expired)
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

# Determine which updates are due
def check_update_flags(last_updated_df):
    logging.debug("--> check_update_flags()")

    logging.info("getting todays date")
    today = datetime.today().date()     
    logging.debug("today: %s", today)   
    
    logging.info("reading bot skinlist metadata")
    bot_skinlist_metadata = utils.read_cached_json_objects(__bot_skinlist_metadata_path__)
    logging.debug("bot_skinlist_metadata: %s", bot_skinlist_metadata)

    logging.info("reading current fee code")
    current_fee_code = bot_skinlist_metadata["fee_code"]
    logging.debug("current_fee_code: %s", current_fee_code)
    
    logging.info("reading fee codes csv as dataframe")
    fee_codes_df = pd.read_csv(__base_path_fee_codes__, parse_dates=["expire_date"])
    logging.debug("fee_codes_df:\n%s", fee_codes_df)
    
    logging.info("finding best fee code")
    best_fee_code = get_best_fee_code(fee_codes_df)
    logging.debug("best_fee_code: %s", best_fee_code)

    logging.info("determining if fee code has to be renewed")
    if best_fee_code:       

        logging.info("checking if current fee code is same as best fee code")
        renew_fee_code = (current_fee_code != best_fee_code)
        logging.debug("renew_fee_code: %s", renew_fee_code)

        logging.info("checking if fee codes have same commission_factor")
        if renew_fee_code:
            logging.info("reading current fee code's commission")
            current_fee_code_commission = fee_codes_df[fee_codes_df["name"] == current_fee_code]

            if current_fee_code_commission.empty:
                current_fee_code_commission = 0.15
            else:
                current_fee_code_commission = current_fee_code_commission.iloc[0]["commission_factor"]

            logging.debug("current_fee_code_commission: %s", current_fee_code_commission)

            logging.info("reading best fee code's commission")
            best_fee_code_commission = fee_codes_df[fee_codes_df["name"] == best_fee_code].iloc[0]["commission_factor"]
            logging.debug("best_fee_code_commission: %s", best_fee_code_commission)

            logging.info("checking if current and best fee code have the same commission factor")
            if current_fee_code_commission == best_fee_code_commission:
                renew_fee_code = False
                logging.debug("renew_fee_code: %s", renew_fee_code)

    else:
        renew_fee_code = True
        logging.debug("renew_fee_code: %s", renew_fee_code)
    
    logging.info("reading last updated date")
    last_updated = last_updated_df['last_updated'].iloc[0].date()
    logging.debug("last_updated: %s", last_updated)

    logging.info("reading last_16 updated date")
    last_16 = last_updated_df['last_16day_update'].iloc[0].date()
    logging.debug("last_16: %s", last_16)

    logging.info("reading last_64 updated date")
    last_64 = last_updated_df['last_64day_update'].iloc[0].date()
    logging.debug("last_64: %s", last_64)

    return {
        'today': today,
        'renew_fee_code': renew_fee_code,
        'every_2': (today - last_updated).days >= 2,
        'every_16': (today - last_16).days >= 16,
        'every_64': (today - last_64).days >= 64,
    }

# Placeholder skinlist generation logic
def regenerate_skinlist(params):
    logging.debug("--> regenerate_skinlist()")

    logging.info("reading mode")
    mode = params["mode"]
    logging.debug("mode: %s", mode)

    import src.scripts.create_bot_skinlist as create_bot_skinlist

    if mode == "pricelist_update":
        create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=False, use_existing_pricelist=False)
    elif mode == "popular_skinlist_update":
        create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=False, use_existing_pricelist=True)
    elif mode == "regular_update":
        create_bot_skinlist.main(should_scrape=True, use_existing_popular_skinlist=True, use_existing_pricelist=True)
    elif mode == "renew_fee":
        create_bot_skinlist.main(should_scrape=False, use_existing_popular_skinlist=True, use_existing_pricelist=True)
    elif mode == "recalc_prices":
        create_bot_skinlist.main(should_scrape=False, use_existing_popular_skinlist=True, use_existing_pricelist=True)
    logging.info("[✓] Skinlist generation completed.")

# Main logic
def main(recalc_prices_if_no_update:bool = False):
    logging.debug("bot_skinlist_checker.py --> main()")
    
    logging.info("reading last updated csv as dataframe")
    last_updated_df = csvs.read_df(__last_updated_path__, parse_dates_columns=["last_updated", "last_16day_update", "last_64day_update"])
    logging.debug("last_updated_df:\n%s", last_updated_df.to_string())

    logging.info("determining update flags")
    update_flags = check_update_flags(last_updated_df)
    logging.debug("update_flags: %s", update_flags)

    logging.info("create today str")
    today_str = update_flags['today'].strftime("%Y-%m-%d")
    logging.debug("today_str: %s", today_str)

    # Prepare update parameters
    params = {
    }

    # PRIORITY ORDER: 64 > 16 > fee > 2
    if update_flags['every_64']:
        params['mode'] = 'pricelist_update'
        last_updated_df.at[0, "last_64day_update"] = today_str
        last_updated_df.at[0, "last_16day_update"] = today_str
        last_updated_df.at[0, "last_updated"] = today_str
    elif update_flags['every_16']:
        params['mode'] = 'popular_skinlist_update'
        last_updated_df.at[0, "last_16day_update"] = today_str
        last_updated_df.at[0, "last_updated"] = today_str
    elif update_flags['every_2']:
        params['mode'] = 'regular_update'
        last_updated_df.at[0, "last_updated"] = today_str
    elif update_flags['renew_fee_code']:
        params['mode'] = 'renew_fee'
    else:
        logging.info("no update needed today")

        if recalc_prices_if_no_update:
            params['mode'] = 'recalc_prices'
        else:
            return

    # Regenerate and update metadata
    regenerate_skinlist(params)
    csvs.save_df(last_updated_df, __last_updated_path__)
    
    logging.debug("bot_skinlist_checker.py <-- main()")
