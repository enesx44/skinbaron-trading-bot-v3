import pandas as pd

__base_path_linked_purchases__ = "./generated_files/link_purchases_to_offers"
__linked_purchases_path__ = __base_path_linked_purchases__ + "/linked_purchases.csv"

def read_linked_purchases() -> pd.DataFrame:
    return pd.read_csv(__linked_purchases_path__, parse_dates=["buy_date", "offer_date_created", "offer_date_trade_unlock", "offer_date_sold"])

def save_linked_purchases(linked_purchases_df: pd.DataFrame) -> pd.DataFrame:
    linked_purchases_df.to_csv(__linked_purchases_path__, index=False)