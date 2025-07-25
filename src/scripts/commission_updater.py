from src.libs import csvs, skinbaron as sb
from src.scripts import link_purchases_to_offers
import time
from datetime import datetime
import pandas as pd
import logging
import os
import json
import sys

__base_path__ = "./generated_files/commission_updater"
os.makedirs(__base_path__, exist_ok=True)

__canceled_offer_infos_path__ =__base_path__ +  "/canceled_offers_infos.csv"

__base_path_manual_data__ = "./manual_data"
__base_path_price_calc__ = __base_path_manual_data__ + "/price_calculation"
__base_path_fee_codes__ = __base_path_price_calc__ + "/fee_codes.csv"

should_cancel = True
should_cancel_sb = True
should_list = True
should_list_sb = True

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

def main(use_existing_linked_purchases: bool):
    
    if not use_existing_linked_purchases:        
        logging.info("creating linked purchases dataframe")
        link_purchases_to_offers.main()

    time.sleep(1)

    logging.info("reading linked purchases dataframe")
    linked_purchases_df = csvs.read_linked_purchases()
    logging.debug("linked_purchases_df: \n%s", linked_purchases_df.to_string())
    
    logging.info("filtering active offers from linked purchases")
    active_offers_df = linked_purchases_df[linked_purchases_df["state"] == "AVAILABLE"].sort_values(by="buy_date", ascending=True).reset_index(drop=True)
    logging.debug("active_offers_df: \n%s", active_offers_df.to_string())
    
    logging.info("filtering not trade locked offers from active offers")
    today = datetime.today().date()

    # Ensure the date column is parsed and normalized
    active_offers_df["offer_date_trade_unlock"] = pd.to_datetime(
        active_offers_df["offer_date_trade_unlock"], errors="coerce"
    ).dt.date

    # Only keep rows that are either:
    # 1) No unlock date (NaT), OR
    # 2) Unlock date strictly before today (exclude today)
    not_tradelocked_offers_df = active_offers_df[
        active_offers_df["offer_date_trade_unlock"].isna() |
        (active_offers_df["offer_date_trade_unlock"].notna() & 
        (active_offers_df["offer_date_trade_unlock"] < today))
    ].reset_index(drop=True)

    logging.debug("not_tradelocked_offers_df: \n%s", not_tradelocked_offers_df.to_string())
    
    logging.info("reading fee codes csv as dataframe")
    fee_codes_df = pd.read_csv(__base_path_fee_codes__, parse_dates=["expire_date"])
    logging.debug("fee_codes_df:\n%s", fee_codes_df)

    logging.info("finding best fee code")
    best_fee_code = get_best_fee_code(fee_codes_df)
    logging.debug("best_fee_code: %s", best_fee_code)
    
    logging.info("reading best fee code's commission")
    best_fee_code_commission = fee_codes_df[fee_codes_df["name"] == best_fee_code].iloc[0]["commission_factor"]
    logging.debug("best_fee_code_commission: %s", best_fee_code_commission)

    logging.info("filtering offers to cancel from active offers without tradelock")
    offers_to_cancel_df = not_tradelocked_offers_df[not_tradelocked_offers_df["commission_factor"] > best_fee_code_commission].reset_index(drop=True)
    logging.info("offers_to_cancel_df: \n%s", offers_to_cancel_df.to_string())

    # Separate offers into two groups:
    # - Non-stackable OR have a uuid
    # - Stackable (to group)
    non_stackable = offers_to_cancel_df[
        (offers_to_cancel_df["uuid"].notna()) | (~offers_to_cancel_df["stackable"])
    ].copy()

    non_stackable["amount"] = 1

    # Stackable ones to group
    stackable = offers_to_cancel_df[
        offers_to_cancel_df["uuid"].isna() & (offers_to_cancel_df["stackable"])
    ].copy()

    # Group stackable offers by meta_offer_id, selling_price, commission_factor, and offer_date_created
    # Keep all other columns by taking the first row of each group
    stacked = (
        stackable.groupby(
            ["meta_offer_id", "selling_price", "commission_factor", "offer_date_created"], 
            as_index=False
        )
        .apply(lambda g: g.iloc[0])  # keep a representative row
        .reset_index(drop=True)
    )

    # Count how many offers in each group for amount
    amounts = (
        stackable.groupby(
            ["meta_offer_id", "selling_price", "commission_factor", "offer_date_created"]
        )
        .size()
        .rename("amount")
        .reset_index()
    )

    # Merge the counts back into stacked so it has the amount column
    stacked = pd.merge(
        stacked, 
        amounts, 
        on=["meta_offer_id", "selling_price", "commission_factor", "offer_date_created"]
    )

    # Combine results
    offers_to_cancel_df = pd.concat([non_stackable, stacked], ignore_index=True).reset_index(drop=True)

    # Ensure meta_offer_id is an integer (not float)
    if "meta_offer_id" in offers_to_cancel_df.columns:
        offers_to_cancel_df["meta_offer_id"] = offers_to_cancel_df["meta_offer_id"].astype("Int64")  # Nullable int type

    logging.info("final offers_to_cancel_df (stacked): \n%s", offers_to_cancel_df.to_string())
    
    logging.info("saving canceled offers infos for relisting")
    canceled_offer_infos_df = offers_to_cancel_df[["name", "selling_price", "amount"]]
    logging.info("canceled_offer_infos_df:\n%s", canceled_offer_infos_df.to_string())
    canceled_offer_infos_df.to_csv(__canceled_offer_infos_path__, index=False)

    # CANCELING PROCESS
    if should_cancel:

        offers_to_cancel = []

        for index, row in offers_to_cancel_df.iterrows():
            if isinstance(row["uuid"], str):
                offers_to_cancel.append({"uuid": row["uuid"]})
            else:
                offers_to_cancel.append({"metaOfferId": row["meta_offer_id"], "amount": row["amount"], "state": row["state"], "price": row["selling_price"]})
        logging.info("offers_to_cancel: \n%s", offers_to_cancel)
        
        # Send offers in chunks of 25
        chunk_size = 25
        for i in range(0, len(offers_to_cancel), chunk_size):
            chunk = offers_to_cancel[i:i+chunk_size]
            logging.debug("chunk: %s", str(json.dumps(chunk, indent=4)))
            
            if should_cancel_sb:
                sb.cancel_offers(offers_to_cancel=chunk)

        time.sleep(20)
    
    # CANCELING PROCESS

    # LISTING PROCESS
    if should_list:
        
        inventory_df = sb.get_inventory()
        logging.debug("inventory_df: \n%s", inventory_df.to_string())

        items = []
        search_strings = []

        for i, row in inventory_df.iterrows():
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

            search_strings.append(search_name)

            logging.debug("search_name: %s", search_name)

        inventory_df["search_strings"] = search_strings
        logging.debug("inventory_df: \n%s", inventory_df.to_string())

        for i, row in canceled_offer_infos_df.iterrows():
            name = row["name"]
            logging.debug("name: %s", name)
            price = row["selling_price"]
            logging.debug("price: %s", price)
            amount = row["amount"]
            logging.debug("amount: %s", amount)

            selected_offers_from_inv = inventory_df.loc[inventory_df["search_strings"] == name]
            logging.debug("selected_offers_from_inv: \n%s", selected_offers_from_inv.to_string())

            selected_offers_from_inv = selected_offers_from_inv.head(amount)
            logging.debug("selected_offers_from_inv: \n%s", selected_offers_from_inv.to_string())        

            inventory_df = inventory_df[~inventory_df.isin(selected_offers_from_inv.to_dict(orient='list')).all(axis=1)]

            for i, row in selected_offers_from_inv.iterrows():
                items.append({"assetId": row["id"], "price": price, "name": row["localizedName"]})

        logging.debug("items: \n%s", items)
        
        chunk_size = 50
        chunks = [items[i:i + chunk_size]
                for i in range(0, len(items), chunk_size)]

        for chunk in chunks:
            logging.debug("chunk: %s", str(json.dumps(chunk, indent=4)))

            if should_list_sb:
                response = sb.list_items(items=chunk, promotion_code=best_fee_code)
                
                if "errors" in response:
                    logging.error("error: %s", response["errors"])
                    sys.exit(1)
                
    # LISTING PROCESS