from typing import Literal
import src.libs.skinbaron as sb
import src.scripts.db as db

import logging
import pandas as pd

def get_all_offers(type: Literal["AVAILABLE", "SOLD"], first_row: pd.Series = None) -> pd.DataFrame:
    logging.debug("--> get_all_offers()")
    
    last_page_df = None  # Initialize to track the last page data

    all_offers_df = pd.DataFrame()
    page = 1

    while True:
        try:
            # Fetch the current page
            df = sb.get_offers_page(type, str(page))

            # Check if the response contains data
            if df.empty:
                logging.debug(f"No more data found on page {page}. Stopping.")
                break

            # Check if the response contains duplicate data
            if last_page_df is not None and df.equals(last_page_df):
                logging.debug(f"Duplicate data found on page {page}. Stopping.")
                break

            # Update last_page_df for comparison
            last_page_df = df.copy()

            # If first_row is provided, check if columns overlap and match
            if first_row is not None:
                common_columns = first_row.index.intersection(df.columns)  # Get overlapping columns
                match_found = df[common_columns].apply(lambda row: row.equals(first_row[common_columns]), axis=1).any()

                if match_found:
                    logging.debug(f"Partial match found with first row on page {page}. Stopping.")

                    # Find the index of the first matching row based on common columns
                    stop_index = df[df[common_columns].apply(lambda row: row.equals(first_row[common_columns]), axis=1)].index[0]

                    # Keep rows up to the matching row (excluding it)
                    df = df.iloc[:stop_index]
                    all_offers_df = pd.concat([all_offers_df, df], ignore_index=True)
                    break

            # Merge the data into the final dictionary
            all_offers_df = pd.concat([all_offers_df, df], ignore_index=True)
            logging.debug(f"Page {page} of {type} offers processed. Total items: {len(all_offers_df)}")

            # Increment the page counter
            page += 1
        except TimeoutError:
            logging.error("Timeout occurred while fetching page %d", page)
            raise
        except Exception as e:
            logging.error(f"Unexpected error occurred: {str(e)}")
            raise
    
    all_offers_df = all_offers_df.drop(columns=["stackable", "formattedState", "offerLink", 
                                                "rarityClassName", "isPrivate", "isSoldAndPaid", 
                                                "appId", "imageUrl", "viewedCount", "stickers",                                             
                                                ], errors="ignore")
    logging.debug("all_offers_df:\n%s", all_offers_df.to_string())

    return all_offers_df    

def main():
    logging.debug("scraper_offers.py --> main()")

    new_offers_available_df = get_all_offers(type="AVAILABLE")
    logging.debug("new_offers_available_df:\n%s", new_offers_available_df.to_string())

    new_offers_sold_df = get_all_offers(type="SOLD")
    logging.debug("new_offers_sold_df:\n%s", new_offers_sold_df.to_string())    

    new_offers_df = pd.concat([new_offers_available_df, new_offers_sold_df], ignore_index=True)
    logging.debug("new_offers_df:\n%s", new_offers_df.to_string())
        
    if new_offers_df.empty:
        logging.info("No new scraped offers exist to add to db")
        return

    logging.debug("new_offers_df:\n%s", new_offers_df.to_string())

    logging.info("saving new scraped offers to db")
    db.set_offers(df=new_offers_df)
    
    logging.debug("scraper_offers.py <-- main()")