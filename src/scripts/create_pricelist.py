import gc
from io import StringIO
import logging
import sys

import pandas as pd
import numpy as np

import src.libs.utils as utils
import src.libs.skinbaron as sb

logging.debug("----> create_pricelist.py")

# config variables
__lowest_price_median_percentage_cutoff__ = 0.2

__base_path__ = "./generated_files/create_pricelist"
__pricelist_path__ = __base_path__ + "/pricelist.csv"

def get_pricelist(use_existing_pricelist: bool) -> pd.DataFrame:  
    logging.debug("create_price_list.py --> get_pricelist()")
    
    if use_existing_pricelist:
        logging.info("using existing pricelist")

        logging.info("reading pricelist.csv and replacing NaN with None")
        pricelist_df = pd.read_csv(__pricelist_path__).fillna(np.nan).replace([np.nan], [None])
        logging.debug("pricelist_df:\n%s", pricelist_df.head().to_string())
    else:
        logging.info("creating new pricelist")
        pricelist_df = main()
        
    logging.debug("create_price_list.py <-- get_pricelist()")
    return pricelist_df     

def main() -> pd.DataFrame:
    logging.debug("create_price_list.py --> main()")

    pricelist = sb.get_pricelist()["map"]    

    logging.info("pricelist json object to dataframe and replace NaN with None")
    pricelist_df = pd.DataFrame(pricelist).fillna(np.nan).replace([np.nan], [None])
    logging.debug("pricelist_df:\n%s", pricelist_df.head().to_string())

    del pricelist
    gc.collect()

    buf = StringIO()

    pricelist_df.info(buf=buf)
    logging.debug("info:\n%s", buf.getvalue())
    utils.clear_buf(buf=buf)
    
    logging.info("sort pricelist dataframe by quantity")
    pricelist_df = pricelist_df.sort_values(by="quantity", ascending=False).reset_index(drop=True)
    logging.debug("pricelist_df:\n%s", pricelist_df.head().to_string())

    logging.info("drop url column")
    pricelist_df = pricelist_df.drop(columns=["url"])
    logging.debug("pricelist_df:\n%s", pricelist_df.head().to_string())

    logging.info("drop rows where the quanitity is lower than the median")
    quantity_median = pricelist_df["quantity"].median()
    logging.debug("quantity_median:\n%s", str(quantity_median))
    pricelist_df = pricelist_df[pricelist_df["quantity"] >= quantity_median]
    logging.debug("pricelist_df:\n%s", pricelist_df.head().to_string())
    pricelist_df.info(buf=buf)
    logging.debug("info:\n%s", buf.getvalue())
    utils.clear_buf(buf=buf)    

    logging.info("drop rows where the lowestPrice is lower than the percentage cutoff of the median")
    lowest_price_median = pricelist_df["lowestPrice"].median()
    logging.debug("lowest_price_median:\n%s", str(lowest_price_median))
    pricelist_df = pricelist_df[pricelist_df["lowestPrice"] > (lowest_price_median * __lowest_price_median_percentage_cutoff__)].reset_index(drop=True)
    logging.debug("pricelist_df:\n%s", pricelist_df.head().to_string())
    pricelist_df.info(buf=buf)
    logging.debug("info:\n%s", buf.getvalue())
    utils.clear_buf(buf=buf)

    del buf
    gc.collect()

    logging.info("saving pricelist dataframe to csv")
    pricelist_df.to_csv(__pricelist_path__, index=False)

    logging.debug("create_price_list.py <-- main()")
    return pricelist_df