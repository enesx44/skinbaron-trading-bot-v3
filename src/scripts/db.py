import sqlite3 as db
import pandas as pd
import logging
import json

__base_path__ = "./generated_files"
__db_path__ = __base_path__ + "/bot.db"

def get_connection():
    logging.debug("db.py --> get_connection()")
    logging.debug("db.py <-- get_connection()")
    return db.connect(__db_path__)

def save_df_to_db(df: pd.DataFrame, table_name: str):
    logging.debug("db.py --> save_df_to_db()")

    con = get_connection()
    row_count = df.to_sql(table_name, con, if_exists="replace", index=False)
    logging.debug("rows in %s table: %s", table_name, row_count)
    con.close()

    logging.debug("db.py <-- save_df_to_db()")

def read_df_from_db(query: str) -> pd.DataFrame:
    logging.debug("db.py --> read_df_from_db()")

    con = get_connection()
    df = pd.read_sql_query(sql=query, con=con)
    logging.debug("df:\n%s", df.head(100).to_string())
    logging.debug("df:\n%s", df.tail(100).to_string())
    con.close()

    logging.debug("db.py <-- read_df_from_db()")
    return df

def get_sales():
    return read_df_from_db(query="SELECT * FROM scraped_sales")

def get_purchases():
    # Fetch the raw DataFrame from the database
    purchases_df = read_df_from_db(query="SELECT * FROM scraped_purchases")
    
    # Parse the 'purchaseItems' column from JSON strings to Python objects, if necessary
    if "purchaseItems" in purchases_df.columns:
        purchases_df["purchaseItems"] = purchases_df["purchaseItems"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else x
        )
    
    return purchases_df

def get_offers():
    return read_df_from_db(query="SELECT * FROM scraped_offers")

def set_sales(df: pd.DataFrame):
    save_df_to_db(df=df, table_name="scraped_sales")

def set_purchases(df: pd.DataFrame):
    save_df_to_db(df=df, table_name="scraped_purchases")

def set_offers(df: pd.DataFrame):
    save_df_to_db(df=df, table_name="scraped_offers")
