import logging

import src.libs.logs as logs

logs.init_logging(log_level=logging.DEBUG)

#from src.scripts import bot_skinlist_checker, item_lister
import src.scripts.analytics as analytics
#import src.scripts.price_adapter as price_adapter
#import src.scripts.commission_updater as commission_updater
#import src.scripts.link_purchases_to_offers as link_purchases_to_offers

import pandas as pd

def main():
    #link_purchases_to_offers.main()
    #commission_updater.main(use_existing_linked_purchases=True)
    #price_adapter.main(use_existing_linked_purchases=True, use_current_bot_skinlist=True)
    analytics.main(use_existing_linked_purchases=False)
    #bot_skinlist_checker.main()
    #item_lister.main()

main()