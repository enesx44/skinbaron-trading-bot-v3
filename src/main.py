import logging

import argparse
import src.libs.logs as logs
import src.enums.enums as enums

logs.init_logging(log_level=logging.DEBUG)

# Set up argparse
parser = argparse.ArgumentParser(description="Run a specific script.")
parser.add_argument(
    "script",
    type=str,
    choices=[script.name for script in enums.Scripts],
    help="Script to run: " + ", ".join([script.name for script in enums.Scripts])
)

args = parser.parse_args()

# Map string argument to enums.Scripts value
__script_to_execute__ = enums.Scripts[args.script]

if __script_to_execute__ == enums.Scripts.CREATE_PRICELIST:
    import src.scripts.create_pricelist as create_pricelist
    create_pricelist.main()
    
elif __script_to_execute__ == enums.Scripts.CREATE_POPULAR_SKINLIST:
    import src.scripts.create_pricelist as create_pricelist
    import src.scripts.create_popular_skinlist as create_popular_skinlist

    create_popular_skinlist.main(use_existing_pricelist=False)
    
elif __script_to_execute__ == enums.Scripts.SCRAPER:
    import src.scripts.scraper_sales as scraper_sales
    scraper_sales.main(use_existing_popular_skinlist=False, use_existing_pricelist=False)

elif __script_to_execute__ == enums.Scripts.CREATE_BOT_SKINLIST:
    import src.scripts.create_bot_skinlist as create_bot_skinlist
    create_bot_skinlist.main(should_scrape=False, use_existing_popular_skinlist=True, use_existing_pricelist=True)

elif __script_to_execute__ == enums.Scripts.BOT:
    import src.scripts.bot as bot
    bot.main(use_existing_linked_purchases=True)

elif __script_to_execute__ == enums.Scripts.ITEM_LISTER:
    import src.scripts.item_lister as item_lister
    item_lister.main()

elif __script_to_execute__ == enums.Scripts.PRICE_ADAPTER:
    import src.scripts.price_adapter as price_adapter
    price_adapter.main(use_existing_linked_purchases=True, use_current_bot_skinlist=True)
