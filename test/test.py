import logging

import src.libs.logs as logs

logs.init_logging(log_level=logging.DEBUG)

import src.scripts.analytics as analytics
import src.scripts.scraper_offers as scraper_offers
import src.scripts.link_purchases_to_offers as link_purchases_to_offers
import src.libs.skinbaron as sb
import src.libs.utils as utils
import src.scripts.price_adapter as price_adapter

import pandas as pd

def main():

    #price_adapter.main(use_existing_linked_purchases=True, use_current_bot_skinlist=True)
    analytics.main(use_existing_linked_purchases=False)

main()