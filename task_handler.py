from insta_scraper import Scraper
from database import Database
from fbid import enrich_fbid


def handle_task(
    db: Database,
    task_id: int,
    task_type: str,
    target: str,
    task_data_id: int | None,
    max_items: int = 10000,
):
    try:
        account = db.get_available_account()
        db.update_account_status(account["id"], "in_use")
        if not account:
            raise ValueError("No available accounts")

        scraper = Scraper(f"{account['username']}", proxy=account.get("ip"))

        if task_type == "comments":
            result = scraper.get_comments(target, max_items)
        elif task_type == "followers":
            result = scraper.get_followers(target, max_items)
        elif task_type == "likes":
            result = scraper.get_likes(target, max_items)
        elif task_type == "profile":
            result = scraper.get_profile(target)
        elif task_type == "fbid":
            data_records = db.get_scraped_data(task_data_id)
            if not data_records:
                raise ValueError("No data found for the given task_data_id")

            # Extract the actual list of items from the first record
            data = data_records[0]["data"]
            data = data[:max_items]

            db.save_scraped_data(task_id, "fbid", [])
            result = enrich_fbid(account["username"], data, task_id)
        else:
            raise ValueError(f"Invalid task type: {task_type}")

        # print(result)
        # print(type(result))

        db.save_scraped_data(task_id, task_type, result)

        db.update_task_status(task_id, "completed", result=result)
        return result
    except Exception as e:
        db.update_task_status(task_id, "failed", error_message=str(e))
        raise
    finally:
        db.update_account_status(account["username"], "available")
