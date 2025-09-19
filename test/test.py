import logging
import time
import src.libs.logs as logs

logs.init_logging(log_level=logging.DEBUG)

#from src.scripts import item_lister
import src.scripts.analytics as analytics
#import src.scripts.price_adapter as price_adapter
#import src.scripts.commission_updater as commission_updater
#import src.scripts.link_purchases_to_offers as link_purchases_to_offers

import pandas as pd

def main():
    analytics.main(use_existing_linked_purchases=True)
    # commission_updater.main(use_existing_linked_purchases=True)
    # time.sleep(120)
    # price_adapter.main(use_existing_linked_purchases=False, use_current_bot_skinlist=True)
    # time.sleep(30)
    # analytics.main(use_existing_linked_purchases=False)

main()