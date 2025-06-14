import src.libs.skinbaron as sb
import src.scripts.db as db

import logging
import pandas as pd

import json

def get_all_purchases(transfer_id: str = None) -> pd.DataFrame:
    logging.debug("--> get_all_purchases()")

    all_purchases_df = pd.DataFrame()
    page = 1

    while True:
        try:
            # Fetch the current page
            df = sb.get_purchases_page(str(page))

            # Check if the response contains data
            if df.empty:
                logging.debug(f"No more data found on page {page}. Stopping.")
                break

            # Check if the transfer_id exists in the current page
            if transfer_id and transfer_id in df.values:
                logging.debug(f"Transfer ID {transfer_id} found on page {page}. Stopping.")
                
                # Find the row index of the transfer_id
                stop_index = df[df.isin([transfer_id]).any(axis=1)].index[0]

                # Cut entries after the transfer_id and merge
                df = df.iloc[:stop_index]
                all_purchases_df = pd.concat([all_purchases_df, df], ignore_index=True)
                break

            # Merge the data into the final dictionary
            all_purchases_df = pd.concat([all_purchases_df, df], ignore_index=True)
            logging.debug(f"Page {page} processed. Total items: {len(all_purchases_df)}")

            # Increment the page counter
            page += 1
        except TimeoutError:
            logging.error("Timeout occurred while fetching page %d", page)
            raise
        except Exception as e:
            logging.error(f"Unexpected error occurred: {str(e)}")
            raise

    return all_purchases_df

def main(full_update: bool = False):
    logging.debug("scraper_purchases.py --> main()")

    try:
        logging.info("reading presisted scraped purchases dataframe from db")
        old_purchases_df = db.get_purchases()
        logging.debug("old_purchases_df:\n%s", old_purchases_df.to_string())
    except:
        logging.info("an error occured while reading persisted scraped purchases dataframe from db")
        logging.info("probably the table does not exist yet")
        logging.info("setting old scraped purchases dataframe to None")
        old_purchases_df = None

    if old_purchases_df is None or full_update:
        new_purchases_df = get_all_purchases()
        logging.debug("new_purchases_df:\n%s", new_purchases_df.to_string())
    else:
        new_purchases_df = get_all_purchases(old_purchases_df.iloc[0]["transferId"])
        logging.debug("new_purchases_df:\n%s", new_purchases_df.to_string())
        
    if new_purchases_df.empty:
        logging.info("No new purchases exist to add to db")
        return  

    if old_purchases_df is None or full_update:
        combined_df = new_purchases_df 
        combined_df['purchaseItems'] = combined_df['purchaseItems'].apply(json.dumps)
    else:
        combined_df = pd.concat([new_purchases_df, old_purchases_df], ignore_index=True)
        combined_df['purchaseItems'] = combined_df['purchaseItems'].apply(json.dumps)

    logging.debug("combined_df:\n%s", combined_df.to_string())

    logging.info("saving combined scraped purchases to db")
    db.set_purchases(df=combined_df)
    
    logging.debug("scraper_purchases.py <-- main()")