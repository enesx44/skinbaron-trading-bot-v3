from enum import Enum

class Endpoints(Enum):
    GET_PRICELIST = "GetPriceList"
    GET_NEWEST_SALES_30_DAYS = "GetNewestSales30Days"
    GET_SALES = "GetSales"
    EDIT_PRICE_MULTI = "EditPriceMulti"
    LIST_ITEMS = "ListItems"
    GET_INVENTORY = "GetInventory"
    GET_BALANCE = "GetBalance"
    SEARCH = "Search"
    BUY_ITEMS = "BuyItems"
    
class BrowserEndpoints(Enum):
    PURCHASES = "api/v2/Purchases"
    OFFERS = "api/v2/Offers"
    INVENTORY = "api/v2/User/Inventory"
    LIST_ITEMS = "api/v2/User/Inventory/Sell"
    CANCEL_OFFERS = "api/v2/Offers/Cancel"


class AppIds(Enum):
    CSGO = 730


# mahmud: 370245-aba8d661-f107-438c-acba-6c2dab06589d
# enes: 3488507-80179c10-4d72-4a57-a0b1-62dcc969fd1d
class ApiKey(Enum):
    API_KEY = "3488507-80179c10-4d72-4a57-a0b1-62dcc969fd1d"

class Scripts(Enum):
    CREATE_PRICELIST = 1
    CREATE_POPULAR_SKINLIST = 2
    SCRAPER = 3
    CREATE_BOT_SKINLIST = 4
    BOT = 5
    ITEM_LISTER = 6
    PRICE_ADAPTER = 7
