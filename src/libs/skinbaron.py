from typing import Literal
import src.enums.enums as enums
import src.libs.utils as utils

import http

import time
import logging
import requests
import json
import traceback
import pandas as pd

# api key
__api_key__ = enums.ApiKey.API_KEY.value

# browser api cookie
AUTH_ID = "399ab48388988c159b45880b09274f37c182491e8e3957d1743d9dd535b0e2c9"
LOGIN_TIME = "1746700045543"
U = "3488507"

# returns a function that returns true if "delay" seconds have passed since the last call
def init_api_timing(delay: int) -> callable: 
    logging.debug("--> init_api_timing()")
    last_call_time = [0]
    state = [True]

    def check_api_timing():
        current_time = time.time()
        if current_time - last_call_time[0] >= delay:
            logging.debug("--> check_api_timing()")
            state[0] = True
        if state[0]:
            state[0] = False
            last_call_time[0] = current_time
            return True
        return False

    return check_api_timing

logging.debug("----> skinbaron.py")
__api_is_ready__ = init_api_timing(2)
logging.debug("<---- skinbaron.py")

def api(endpoint: str, body: dict) -> dict:

    logging.debug("--> api()")

    while not __api_is_ready__():
        time.sleep(0.1)

    headers = {"Content-Type": "application/json",
               "x-requested-with": "XMLHttpRequest"}
    url = "https://api.skinbaron.de/"+endpoint

    response = requests.post(url=url, headers=headers, json=body)

    if response:
        response = response.json()
        logging.debug("response: %s", utils.prettyprint(response))
        return response
    else:
        logging.error(
            "api(%s, %s) --> error in api response (%s):\n%s", endpoint, json.dumps(body), str(response.status_code), response.text)
        raise Exception("error in api response")

# OFFICIAL API WRAPPERS BELOW

# {
#   "apikey": "string"
# }
def get_balance() -> dict:
    logging.debug("--> get_balance()")

    body = {"apikey": __api_key__}
    return utils.repeat_call(api, (enums.Endpoints.GET_BALANCE.value, body), timeout=30)

def edit_price_multi(item_chunk: list) -> dict:
    logging.debug("--> edit_price_multi()")

    body = { 
        "apikey": __api_key__, 
        "items": item_chunk
        }
    return api(endpoint=enums.Endpoints.EDIT_PRICE_MULTI.value, body=body)

# {
#   "apikey": "string",
#   "type": 0,
#   "appid": 0,
#   "after_saleid": "string",
#   "items_per_page": 0,
#   "sort_order": 0
# }

# type : integer
# Optional filter to determine the type of sales you want to get: 
# 1 - items listed for sale but not yet available in the market. The item might be processing, stuck in a trade escrow or simply waiting for you to accept the trade offer from our bots 
# 2 - Item listed for sale on SkinBaron : AVAILABLE
# 3 - Sold but not payed or forwarded to the buyer 
# 4 - Sold, payed and delivered. You got money. : SOLD
# 5 - Return of item requested, but not fully processed yet. 
# 6 - Item has been returned. 
# 7 - Item has been canceled to SkinBaron inventory

# sort_order : integer
# Optional parameter to specify sort order of results. 
# 0 - sort by internal order, usually this gives you most recently added offers first. This is the default if the parameter is not specified.
# 1 - sort by "most recently added" 
# 2 - sort by "most recently sold"
def get_sales(type: int, after_sale_id: str | None = None) -> dict:
    logging.debug("--> get_sales()")

    body = {
        "apikey": __api_key__,
        "type": type,
        "appId": enums.AppIds.CSGO.value,
        "after_saleid": after_sale_id,
        "items_per_page": 50,
        "sort_order": 1,
    }
    return api(endpoint=enums.Endpoints.GET_SALES.value, body=body)

# {
#   "apikey": "string",
#   "appid": 0,
#   "search_item": "string",
#   "min": 0,
#   "max": 0,
#   "tradelocked": true,
#   "after_saleid": "string",
#   "items_per_page": 0,
#   "stattrak": true,
#   "souvenir": true,
#   "stackable": true,
#   "minWear": 0,
#   "maxWear": 0
# }
def search(search_item: str, min: int = None, max: int = None, tradelocked: bool = None) -> dict:
    logging.debug("--> search()")

    search_item_full = search_item

    if search_item.find("StatTrak™") != -1:
        isStatTrak = True
        search_item = search_item.replace("StatTrak™", "").strip()
    else:
        isStatTrak = False

    if search_item.find("Souvenir") != -1:
        isSouvenir = True
        search_item = search_item.replace("Souvenir", "").strip()
    else:
        isSouvenir = False

    noWear = False
    if search_item.find("(Factory New)") != -1:
        minWear = 0.00
        maxWear = 0.07
        search_item = search_item.replace("(Factory New)", "").strip()
    elif search_item.find("(Minimal Wear)") != -1:
        minWear = 0.07
        maxWear = 0.15
        search_item = search_item.replace("(Minimal Wear)", "").strip()
    elif search_item.find("(Field-Tested)") != -1:
        minWear = 0.15
        maxWear = 0.38
        search_item = search_item.replace("(Field-Tested)", "").strip()
    elif search_item.find("(Well-Worn)") != -1:
        minWear = 0.38
        maxWear = 0.45
        search_item = search_item.replace("(Well-Worn)", "").strip()
    elif search_item.find("(Battle-Scarred)") != -1:
        minWear = 0.45
        maxWear = 1.00
        search_item = search_item.replace("(Battle-Scarred)", "").strip()
    else:
        noWear = True

    if noWear:
        body = {"apikey": __api_key__, 
                "appid": 730,
                "search_item": search_item, 
                "min": min, 
                "max": max,
                "tradelocked": tradelocked,
                "stattrak": isStatTrak,
                "souvenir": isSouvenir}
    else:
        body = {"apikey": __api_key__, 
                "appid": 730,
                "search_item": search_item, 
                "min": min, 
                "max": max,
                "tradelocked": tradelocked,
                "minWear": minWear,
                "maxWear": maxWear,
                "stattrak": isStatTrak,
                "souvenir": isSouvenir}   
    
    try:
        response = utils.repeat_call(api, (enums.Endpoints.SEARCH.value, body), timeout=30)
    except TimeoutError:
        logging.error("%s", traceback.format_exc())
        response = None

    if response:
        name_matching_sales = []

        for sale in response["sales"]:
            if sale["market_name"] == search_item_full:
                name_matching_sales.append(sale)

        return name_matching_sales
    else:
        return None
    
# {
#   "apikey": "string",
#   "total": 0,
#   "toInventory": true,
#   "saleids": [
#     "string"
#   ]
# }
def buy_offer(offer: pd.DataFrame):

    body = {
        "apikey": __api_key__, 
        "total": offer["price"],        
        "toInventory": True,
        "saleids": [
            offer["id"]
        ]
    }
    return api(endpoint=enums.Endpoints.BUY_ITEMS.value, body=body)
    
# {
#   "apikey": "string",
#   "appId": 0
# }
def get_pricelist() -> dict:
    logging.debug("--> get_pricelist()")

    body = {
        "apikey": __api_key__,
        "appId": enums.AppIds.CSGO.value
    }
    return api(endpoint=enums.Endpoints.GET_PRICELIST.value, body=body)

# {
#   "apikey": "string",
#   "itemName": true,
#   "statTrak": true,
#   "souvenir": true,
#   "dopplerPhase": "string"
# } 
# market hash name is the name of the item + exterior (e.g. "AK-47 | Redline (Field-Tested)")
# doppler phase is only needed for doppler knives
def get_newest_sales_30_days(marketHashName: str, is_statTrak: bool, is_souvenir: bool, dopplerPhase: str | None) -> dict:
    logging.debug("--> get_newest_sales_30_days()")

    body = {
        "apikey": __api_key__,
        "itemName": marketHashName,
        "statTrak": is_statTrak,
        "souvenir": is_souvenir,
        "dopplerPhase": dopplerPhase
    }

    try:
        response = utils.repeat_call(api, (enums.Endpoints.GET_NEWEST_SALES_30_DAYS.value, body), timeout=30)["newestSales30Days"]
    except TimeoutError:
        logging.error("%s", traceback.format_exc())
        response = None

    return response

# OFFICIAL API WRAPPERS ABOVE

# BROWSER REQUESTS BELOW 

def browser_api(endpoint: str, method: http.HTTPMethod, body: dict | None = None):
    """
    Send an API request to the specified endpoint.

    Parameters:
    - endpoint (str): The API endpoint (relative to the base URL).
    - method (http.HTTPMethod): The HTTP method to use (GET or POST).
    - body (dict | None, optional): Request payload, required for POST requests. Defaults to None.

    Raises:
    - ValueError: If body is not provided for a POST request.
    - Exception: For any other API response errors.

    Returns:
    - dict: The parsed JSON response.
    """

    logging.debug("--> browser_api()")

    while not __api_is_ready__():
        time.sleep(0.1)
        
    url = "https://skinbaron.de/"+endpoint

    if method == http.HTTPMethod.GET:
        headers = {"Cookie": "AUTHID='" + AUTH_ID + "-loginTime=" + LOGIN_TIME + "&u=" + U + "&LANG=en'"}        
        response = requests.get(url=url, headers=headers)
    elif method == http.HTTPMethod.POST:
        headers = {"Content-Type": "application/json",
                "x-requested-with": "XMLHttpRequest",
                "Cookie": "AUTHID='" + AUTH_ID + "-loginTime=" + LOGIN_TIME + "&u=" + U + "&LANG=en'"} 
        
        if body is None:  # Explicit check for body when method is POST
                raise ValueError("Body is required when method is POST")
               
        response = requests.post(url=url, headers=headers, json=body)

    if response:
        response = response.json()
        logging.debug("response: %s", utils.prettyprint(response))
        return response
    else:
        logging.error(
            "api(%s, %s) --> error in api response (%s):\n%s", endpoint, json.dumps(body), str(response.status_code), response.text)
        raise Exception("error in api response")

def get_purchases_page(page: str = "1") -> pd.DataFrame:
    logging.debug("--> get_purchases_page()")

    endpoint = enums.BrowserEndpoints.PURCHASES.value

    pagination = "pagination=%7B%22page%22:" + page + ",%22pageSize%22:25%7D"

    query_parameters = "?" + pagination

    endpoint = endpoint + query_parameters

    try:
        response = utils.repeat_call(browser_api, (endpoint, http.HTTPMethod.GET), timeout=30)["purchaseGroups"]
    except TimeoutError:
        logging.error("%s", traceback.format_exc())
        raise TimeoutError()
    
    df = pd.DataFrame(response)
    logging.debug("df: \n%s", df.to_string())

    if not df.empty:    
        df = df[["transferId", "totalPrice", "formattedDate", "purchaseItems", "state", "marketplaceFees"]]

    return df

def get_offers_page(type: Literal["AVAILABLE", "SOLD"], page: str = "1") -> pd.DataFrame:
    logging.debug("--> get_offers_page()")

    endpoint = enums.BrowserEndpoints.OFFERS.value

    offer_filters = "offerFilters=" + type

    sort_order = "&sortOrder=DATE_CREATED_DESC"

    pagination = "&pagination=%7B%22page%22:" + page + ",%22pageSize%22:25%7D"

    query_parameters = "?" + offer_filters + sort_order + pagination

    endpoint = endpoint + query_parameters

    try:
        response = utils.repeat_call(browser_api, (endpoint, http.HTTPMethod.GET), timeout=30)["offers"]
    except TimeoutError:
        logging.error("%s", traceback.format_exc())
        raise TimeoutError()
    
    df = pd.DataFrame(response)
    logging.debug("df: \n%s", df.to_string())

    return df



def get_inventory_page(page: str = "1") -> pd.DataFrame:
    logging.debug("--> get_inventory_page()")

    endpoint = enums.BrowserEndpoints.INVENTORY.value

    app_id = "appId=730"

    pagination = "&pagination=%7B%22page%22:" + page + ",%22pageSize%22:50,%22reset%22:false%7D"

    query_parameters = "?" + app_id + pagination

    endpoint = endpoint + query_parameters

    try:
        response = utils.repeat_call(browser_api, (endpoint, http.HTTPMethod.GET), timeout=30)["items"]
    except TimeoutError:
        logging.error("%s", traceback.format_exc())
        raise TimeoutError()
    
    df = pd.DataFrame(response)
    logging.debug("df: \n%s", df.to_string())

    return df

# BROWSER REQUESTS ABOVE 