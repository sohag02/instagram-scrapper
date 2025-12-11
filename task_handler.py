from insta_scraper import Scraper
from database import Database

def handle_task(db: Database, task_id: int, task_type: str, target: str, max_items: int = 10000):
    try:
        account = db.get_available_account()
        if not account:
            raise ValueError("No available accounts")

        scraper = Scraper(f'{account["username"]}')

        if task_type == 'comments':
            result = scraper.get_comments(target, max_items)
        elif task_type == 'followers':
            result = scraper.get_followers(target, max_items)
        elif task_type == 'likes':
            result = scraper.get_likes(target, max_items)
        elif task_type == 'profile':
            result = scraper.get_profile(target)
        else:
            raise ValueError(f"Invalid task type: {task_type}")

        print(result)
        print(type(result))

        db.save_scraped_data(task_id, task_type, result)

        db.update_task_status(task_id, 'completed', result=result)
        return result
    except Exception as e:
        db.update_task_status(task_id, 'failed', error_message=str(e))
        raise
    