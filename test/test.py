import logging

import src.libs.logs as logs

logs.init_logging(log_level=logging.DEBUG)

import src.scripts.analytics as analytics
import src.scripts.price_adapter as price_adapter

import pandas as pd

def main():

    #price_adapter.main(use_existing_linked_purchases=True, use_current_bot_skinlist=True)
    analytics.main(use_existing_linked_purchases=False)

main()