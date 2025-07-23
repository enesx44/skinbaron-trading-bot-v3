import logging
import pandas as pd
import datetime

from src.libs import csvs
import src.libs.utils as utils
import src.scripts.scraper_purchases as scraper_purchases
import src.scripts.scraper_offers as scraper_offers
import src.scripts.db as db
import src.libs.skinbaron as sb

__base_path__ = "./generated_files/link_purchases_to_offers"
__linked_purchases_path__ = __base_path__ + "/linked_purchases.csv"

def add_profit_column(linked_purchases_df: pd.DataFrame) -> pd.DataFrame:
    logging.debug("--> add_profit_column()")
    linked_purchases_df['profit'] = linked_purchases_df.apply(
        lambda row: round(
            row['linkedOfferInfo']['price'] * (1 - row['linkedOfferInfo']['commissionFactor'])
            - row['purchaseItems'][0]['price'], 2
        ) if row['linkedOfferInfo'] and row['purchaseItems'] else 0, axis=1
    )
    
    logging.debug("<-- add_profit_column()")
    return linked_purchases_df

def add_min_price_column(linked_purchases_df: pd.DataFrame) -> pd.DataFrame:
    logging.debug("--> add_min_price_column()")
    linked_purchases_df['minSellingPrice'] = linked_purchases_df.apply(
        lambda row: round(
            (row['purchaseItems'][0]['price'] + 0.01) / (1 - row['linkedOfferInfo']['commissionFactor']), 2
        ) if row['linkedOfferInfo'] and row['purchaseItems'] else 0, axis=1
    )
    
    logging.debug("<-- add_min_price_column()")
    return linked_purchases_df

def add_time_to_sell_column(linked_purchases_df: pd.DataFrame) -> pd.DataFrame:
    logging.debug("--> add_time_to_sell_column()")
    
    linked_purchases_df['timeToSell'] = linked_purchases_df.apply(
        lambda row: (
            max((datetime.datetime.strptime(row['linkedOfferInfo']['formattedDateSold'], "%m/%d/%Y") -
                 datetime.datetime.strptime(row['formattedDate'], "%d.%m.%Y %H:%M")).days, 0)  # Ensure non-negative values
        ) if row['linkedOfferInfo'] and 'formattedDateSold' in row['linkedOfferInfo'] and row['linkedOfferInfo']['formattedDateSold']
        else None,
        axis=1
    ).astype('Int64')
    
    logging.debug("<-- add_time_to_sell_column()")
    return linked_purchases_df

def post_process_linked_purchases(linked_purchases_df: pd.DataFrame):
    logging.debug("--> post_process_linked_purchases()")

    def restructure_dataframe(linked_purchases_df: pd.DataFrame) -> pd.DataFrame:

        def extract_name(row):
            if row['linkedOfferInfo']:
                return row['linkedOfferInfo']['name']
            if row['purchaseItems']:
                item = row['purchaseItems'][0]
                if item.get("localizedExteriorName"):
                    return f"{item['localizedName']} ({item['localizedExteriorName']})"
                return item['localizedName']
            return None
        
        def extract_wear(row):
            if row['linkedOfferInfo']:
                return row['linkedOfferInfo'].get('wear')
            if row['purchaseItems']:
                item = row['purchaseItems'][0]
                return item.get('wearPercent') if item.get('wearPercent') else None
            return None

        restructured_df = pd.DataFrame()
        restructured_df['transfer_id'] = linked_purchases_df['transferId']
        restructured_df['buy_price'] = linked_purchases_df['purchaseItems'].apply(lambda x: x[0]['price'] if (x and len(x) == 1) else None)
        restructured_df['buy_date'] = linked_purchases_df['formattedDate']
        restructured_df['name'] = linked_purchases_df.apply(extract_name, axis=1)
        restructured_df['wear'] = linked_purchases_df.apply(extract_wear, axis=1) 
        restructured_df['uuid'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['uuid'] if x else None)
        restructured_df['meta_offer_id'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['metaOfferId'] if x else None)
        restructured_df["meta_offer_id"] = pd.to_numeric(restructured_df["meta_offer_id"], errors='coerce').astype('Int64')
        restructured_df["stackable"] = linked_purchases_df['purchaseItems'].apply(lambda x: x[0]['stackable'] if (x and len(x) == 1) else None)
        restructured_df['sale_id'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['sale_id'] if x else None)
        restructured_df['offer_date_created'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['formattedDateCreated'] if x else None)
        restructured_df['offer_date_trade_unlock'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['formattedDateTradeUnlock'] if x else None)
        restructured_df['state'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['state'] if x else None)
        restructured_df['offer_date_sold'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['formattedDateSold'] if x else None)
        restructured_df['time_to_sell'] = linked_purchases_df['timeToSell']
        restructured_df['commission_factor'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['commissionFactor'] if x else None)
        restructured_df['selling_price'] = linked_purchases_df['linkedOfferInfo'].apply(lambda x: x['price'] if x else None)
        restructured_df['min_selling_price'] = linked_purchases_df['minSellingPrice']
        restructured_df['profit'] = linked_purchases_df['profit']        
        return restructured_df

    def serialize_timestamps(value):
        logging.debug("--> serialize_timestamps()")
        if isinstance(value, pd.Timestamp):
            # Convert Timestamp to ISO8601 string
            return value.isoformat()
        elif isinstance(value, dict):
            # Recursively serialize timestamps in nested dictionaries
            return {key: serialize_timestamps(val) for key, val in value.items()}
        elif isinstance(value, list):
            # Recursively serialize timestamps in nested lists
            return [serialize_timestamps(item) for item in value]
        return value

    logging.info("Post-processing data for easier read/write")

    linked_purchases_df = restructure_dataframe(linked_purchases_df)
    logging.debug("linked_purchases_df after restructure: \n%s", linked_purchases_df.to_string())

    date_formats = {
        "buy_date": "%d.%m.%Y %H:%M",
        "offer_date_created": "%Y-%m-%d",
        "offer_date_trade_unlock": "%m/%d/%Y",
        "offer_date_sold": "%m/%d/%Y"
        }

    utils.standardize_date_format(linked_purchases_df, date_formats)
    logging.debug("linked_purchases_df after standardize date formats: \n%s", linked_purchases_df.to_string())

    # Process other columns, converting timestamps at top level
    for column in linked_purchases_df.columns:
        linked_purchases_df.loc[:, column] = linked_purchases_df[column].apply(serialize_timestamps)
    logging.debug("linked_purchases_df after serializing timestamps: \n%s", linked_purchases_df.to_string())

    logging.debug("<-- post_process_linked_purchases()")
    return linked_purchases_df

def get_all_sales(type: int) -> pd.DataFrame:
    logging.debug("--> get_all_sales()")
    
    all_sales = []
    first_page = sb.get_sales(type=type)["response"]
    if len(first_page) != 0:
        all_sales.extend(first_page)
        last_sale = first_page[-1]
        last_sale_id = last_sale["id"]
    if len(first_page) < 50:
        return pd.DataFrame(all_sales)

    while True:
        next_page = sb.get_sales(type=type, after_sale_id=last_sale_id)["response"]
        if len(next_page) != 0:
            all_sales.extend(next_page)
            last_sale = next_page[-1]
            last_sale_id = last_sale["id"]
        
        if len(next_page) < 50:
            return pd.DataFrame(all_sales)
        
def link_offers_to_sales(new_offers_available_df: pd.DataFrame, new_sales_available_df: pd.DataFrame) -> pd.DataFrame:
    logging.debug("--> link_offers_to_sales()")

    # Define the preprocessing function
    def pre_process_data(df: pd.DataFrame):
        logging.debug("--> pre_process_data()")
        # Replace numerical state values with string representations
        df['state'] = df['state'].replace({2: 'AVAILABLE', 4: 'SOLD'})
        # Round wear values to two decimal places
        df['wear'] = df['wear'].round(2)
        logging.debug("df: \n%s", df.to_string())
        return df

    # Step 1: Preprocess both DataFrames
    new_offers_available_df = pre_process_data(new_offers_available_df)  # First DataFrame with wear adjustment
    new_sales_available_df = pre_process_data(new_sales_available_df)  # Second DataFrame without wear adjustment

    # Step 2: Initialize sale_id column in offers DataFrame
    new_offers_available_df['sale_id'] = None  # Set default value to None

    # Step 3: Find partial matches and assign sale_id
    for idx, offer_row in new_offers_available_df.iterrows():
        # Search for a matching row in the sales DataFrame
        match = new_sales_available_df[
            (new_sales_available_df['name'] == offer_row['name']) &
            (new_sales_available_df['price'] == offer_row['price']) &
            (new_sales_available_df['state'] == offer_row['state']) &
            ((new_sales_available_df['wear'] == offer_row['wear']) | pd.isna(new_sales_available_df['wear']) | pd.isna(offer_row['wear']))
        ]
        
        # If a match is found, assign the sales id to the offer row
        if not match.empty:
            matching_index = match.index[0]  # Get the index of the first matching row
            new_offers_available_df.at[idx, 'sale_id'] = new_sales_available_df.at[matching_index, 'id']  # Assign sale_id

            # Remove the matched sale row to ensure it is not reused
            new_sales_available_df = new_sales_available_df.drop(index=matching_index)

    return new_offers_available_df

def link_purchases_to_offers(purchases_df, offers_df):
    logging.debug("--> link_purchases_to_offers()")

    def pre_process_purchases(purchases_df: pd.DataFrame) -> pd.DataFrame:
        logging.debug("--> pre_process_purchases()")
        purchases_df = purchases_df[purchases_df["state"] == "SUCCEEDED"]
        logging.debug("<-- pre_process_purchases()")
        return purchases_df

    def pre_process_offers(offers_df: pd.DataFrame) -> pd.DataFrame:
        logging.debug("--> pre_process_offers()")
        # Create rows with single item amounts for each offer where amount > 1
        expanded_offers = []
        for _, offer in offers_df.iterrows():
            for _ in range(int(offer["amount"])):
                single_item_offer = offer.copy()
                single_item_offer["amount"] = 1  # Each row now corresponds to one item
                expanded_offers.append(single_item_offer)

        expanded_offers_df = pd.DataFrame(expanded_offers).reset_index(drop=True)
        logging.debug("expanded_offers_df: \n%s", expanded_offers_df.to_string())

        logging.debug("<-- pre_process_offers()")
        return expanded_offers_df

    # Normalize and adjust dates in offers DataFrame
    offers_df["formattedDateCreated"] = pd.to_datetime(offers_df["formattedDateCreated"])
    offers_df["formattedDateCreated"] += pd.Timedelta(days=1)  # Add 1 day to offers' creation date

    # remove purchases where state != SUCCEEDED
    purchases_df = pre_process_purchases(purchases_df)

    # Split offers into single-item rows
    offers_df = pre_process_offers(offers_df)

    new_sales_available_df = get_all_sales(type = 2) 
    logging.debug("new_sales_available_df:\n%s", new_sales_available_df.to_string()) 
    
    new_sales_sold_df = get_all_sales(type = 4) 
    logging.debug("new_sales_sold_df:\n%s", new_sales_sold_df.to_string()) 
    
    sales_df = pd.concat([new_sales_available_df, new_sales_sold_df], ignore_index=True) 
    sales_df['wear'] = (sales_df['wear'] * 100) 
    logging.debug("sales_df:\n%s", sales_df.head(200).to_string()) 
    
    offers_df = link_offers_to_sales(offers_df, sales_df) 
    logging.debug("linked_offers_df:\n%s", offers_df.to_string())

    # Add a new column to purchases_df for linked offer information
    purchases_df["linkedOfferInfo"] = None

    # Create a copy of offers_df for internal tracking of used rows
    available_offers = offers_df.copy()

    for index, purchase in purchases_df.iterrows():        
        tranfser_id = purchase["transferId"]

        logging.info("Processing item %d/%d: %s", index, len(purchases_df), tranfser_id)
        logging.debug("transfer_id: %s", tranfser_id)

        purchase_date = pd.to_datetime(purchase["formattedDate"], dayfirst=True)
        
        # Access the purchaseItems directly since they're already parsed
        purchase_items = purchase["purchaseItems"]
        purchase_item = purchase_items[0]  # Accessing the first item
        logging.debug("purchase_item: \n%s", purchase_item)
        
        # Handle missing attributes using .get() safely
        souvenir_string = purchase_item.get("souvenirString", None)
        logging.debug("souvenir_string: \n%s", souvenir_string)
        statTrak_string = purchase_item.get("statTrakString", None)
        logging.debug("statTrak_string: \n%s", statTrak_string)
        localized_exterior_name = purchase_item.get("localizedExteriorName", None)
        logging.debug("localized_exterior_name: \n%s", localized_exterior_name)

        purchase_name = purchase_item.get("localizedName")        
        if souvenir_string:
            purchase_name = souvenir_string + " " + purchase_name
        elif statTrak_string:
            purchase_name = statTrak_string + " " + purchase_name

        if localized_exterior_name:
            purchase_name = purchase_name + " (" + localized_exterior_name + ")"

        purchase_exterior = purchase_item.get("exteriorClassName", None)
        purchase_wear = purchase_item.get("wearPercent", None)

        logging.debug("offers_df['name']: \n%s", offers_df["name"])
        logging.debug("purchase_name: \n%s", purchase_name)

        logging.debug("offers_df['exteriorClassName']: \n%s", offers_df["exteriorClassName"])
        logging.debug("purchase_exterior: \n%s", purchase_exterior)
        logging.debug("pd.isna(purchase_exterior): \n%s", pd.isna(purchase_exterior))

        logging.debug("purchase_wear: \n%s", purchase_wear)
        logging.debug("offers_df['wear'].round(2): \n%s", offers_df["wear"].round(2))

        if purchase_wear is not None:
            logging.debug("round(purchase_wear, 2): \n%s", round(purchase_wear, 2))
            logging.debug("pd.isna(purchase_wear): \n%s", pd.isna(purchase_wear))
        
        # Filter offers based on relaxed criteria
        matching_offers_df = available_offers[
            (available_offers["name"] == purchase_name) &
            ((available_offers["exteriorClassName"] == purchase_exterior) | pd.isna(purchase_exterior)) &
            ((available_offers["wear"].round(2) == round(purchase_wear, 2) if purchase_wear is not None else False) | pd.isna(purchase_wear))
        ]

        logging.debug("matching_offers_df: \n%s", matching_offers_df.to_string())

        # Sort offers by creation date and select the first valid one after the purchase date
        if not matching_offers_df.empty:
            matching_offers_df.loc[:, "formattedDateCreated"] = pd.to_datetime(matching_offers_df["formattedDateCreated"])
            valid_offers = matching_offers_df[matching_offers_df["formattedDateCreated"] >= purchase_date]

            if not valid_offers.empty:
                closest_offer_index = valid_offers["formattedDateCreated"].idxmin()
                closest_offer = valid_offers.loc[closest_offer_index]
                
                # Link the offer directly without modifying its amount
                closest_offer_dict = closest_offer.to_dict()
                purchases_df.at[index, "linkedOfferInfo"] = closest_offer_dict
                
                # Remove the used offer from the tracking DataFrame
                available_offers = available_offers.drop(closest_offer_index)

    logging.debug("<-- link_purchases_to_offers()")
    return purchases_df

def main():
    logging.debug("link_purchases_to_offers.py --> main()")

    logging.debug("updating purchases")
    scraper_purchases.main(full_update=False)

    logging.debug("getting purchases from db")
    purchases_df = db.get_purchases()
    logging.debug("purchases_df: \n%s", purchases_df.to_string())

    logging.debug("updating offers")
    scraper_offers.main()
    
    logging.debug("getting offers from db")
    offers_df = db.get_offers()
    
    logging.debug("selecting offers where state = AVAILABLE or SOLD, not needed but just making sure")
    offers_df = offers_df[offers_df["state"].isin(["AVAILABLE", "SOLD"])]
    logging.debug("offers_df: \n%s", offers_df.to_string())

    logging.debug("linking purchases to offers")
    linked_purchases_df = link_purchases_to_offers(purchases_df, offers_df)
    logging.debug("linked_purchases_df: \n%s", linked_purchases_df.to_string())

    linked_purchases_df = add_profit_column(linked_purchases_df)
    logging.debug("linked_purchases_df after adding profit column: \n%s", linked_purchases_df.to_string())
    linked_purchases_df = add_min_price_column(linked_purchases_df)
    logging.debug("linked_purchases_df after adding min_price column: \n%s", linked_purchases_df.to_string())
    linked_purchases_df = add_time_to_sell_column(linked_purchases_df)
    logging.debug("linked_purchases_df after adding time_to_sell column: \n%s", linked_purchases_df.to_string())

    none_count = linked_purchases_df['linkedOfferInfo'].isna().sum()
    logging.debug("Number of rows with None or NaN values in linkedOfferInfo: %s", none_count)
    
    none_rows = linked_purchases_df[linked_purchases_df['linkedOfferInfo'].isna()]
    logging.debug("rows with None or NaN values in linkedOfferInfo: %s", none_rows.to_string())

    logging.info("postprocessing linked purchases dataframe for easier read / write")
    linked_purchases_df = post_process_linked_purchases(linked_purchases_df)
    logging.debug("linked_purchases_df after post processing: \n%s", linked_purchases_df.to_string())

    logging.info("saving linked purchases dataframe to csv")
    csvs.save_linked_purchases(linked_purchases_df=linked_purchases_df)

    logging.debug("link_purchases_to_offers.py <-- main()")