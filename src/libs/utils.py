from io import StringIO
import pandas as pd
import json
import os
import logging
import time
import traceback
import datetime

def standardize_date_format(df: pd.DataFrame, date_columns: dict, target_format: str = '%Y-%m-%d') -> pd.DataFrame:
    for column, format in date_columns.items():
        df[column] = df[column].astype(str).str.strip()
        df[column] = pd.to_datetime(df[column], format=format, errors='coerce')
        df[column] = df[column].apply(lambda x: x.strftime(target_format) if pd.notna(x) else x)
    return df

def prettyprint(data: dict) -> str:
    logging.debug("--> prettyprint()")

    return json.dumps(data, indent=4)

def cache_json_objects(file_path, json_objects):
    logging.debug("--> cache_json_objects()")

    cached_objects = read_cached_json_objects(file_path)

    if cached_objects:
        with open(file_path, 'w') as file:
            json.dump(cached_objects + json_objects, file)
    else:
        with open(file_path, 'w') as file:
            json.dump(json_objects, file)

def cache_json_objects_always_overwrite(file_path, json_objects):
    logging.debug("--> cache_json_objects_overwrite()")
    
    with open(file_path, 'w') as file:
        json.dump(json_objects, file)

def read_cached_json_objects(file_path) -> dict:
    logging.debug("--> read_cached_json_objects()")

    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    
def repeat_call(call: callable, *args: tuple, timeout: int):
    logging.debug("--> repeat_call()")

    logging.debug("callable: %s, args: %s, timeout: %s", str(call), str(*args), str(timeout))

    start_time = time.time()

    while True:

        if (time.time() - start_time) > timeout:
            raise TimeoutError("timeout reached")

        try:
            logging.info("calling callable with args: %s", args)
            response = call(*args[0])
            break
        except:
            logging.error("%s", traceback.format_exc())
            logging.info("repeating action after 4 seconds beacuse of an error")
            time.sleep(4)

    return response

def clear_buf(buf: StringIO):
    buf.truncate(0)
    buf.seek(0)
    return buf

def get_date_n_months_ago(n_months : int, days_in_month: int = 30) -> datetime.date:
    total_days = n_months * days_in_month
    fixed_days_ago = datetime.datetime.now() - datetime.timedelta(days=total_days)
    return fixed_days_ago.date()

def get_datetime_n_days_ago(n_days : int) -> datetime.date:
    fixed_days_ago = datetime.datetime.now() - datetime.timedelta(days=n_days)
    return fixed_days_ago
