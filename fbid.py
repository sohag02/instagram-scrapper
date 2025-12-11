from insta_scraper import Scraper
from database import Database
import logging
import time
import random

PER_AC_LIMIT = 200

db = Database()

logger = logging.getLogger(__name__)

def enrich_fbid(session: str, data: list[dict], task_id: int):
    logger.info(f'Enriching fbid for {len(data)} users')
    logger.info(f'Using session: {session} for {task_id} | fbid')
    scraper = Scraper(session)
    new_data = []
    for item in data:
        item['fbid'] = scraper.get_profile(item['username'])['fbid']
        new_data.append(item)

        # update db
        db.update_task_data(task_id, new_data)

        # sleep
        time.sleep(random.randint(10, 20))
    accs = db.get_all_accounts()
    for acc in accs:
        if acc['username'] == session:
            db.update_account_status(acc['id'], 'available')
    return new_data
        