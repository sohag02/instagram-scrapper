from database import Database
from config import Config

class AccountManager:
    def __init__(self):
        self.db = Database()
        self.current_account = None
        self.tasks_with_current = 0

    def get_account_for_task(self):
        """Get an available account, implementing rotation strategy"""
        # Check if current account needs rotation
        if (
            self.current_account
            and self.tasks_with_current >= Config.MAX_TASKS_PER_ACCOUNT
        ):
            print(
                f"🔄 Rotating account: {self.current_account['username']} completed {self.tasks_with_current} tasks"
            )
            self.db.set_account_cooldown(
                self.current_account["id"], Config.ACCOUNT_COOLDOWN_TIME
            )
            self.current_account = None
            self.tasks_with_current = 0

        # Get available account
        if not self.current_account:
            self.current_account = self.db.get_available_account()
            if not self.current_account:
                raise Exception(
                    "No available accounts. All accounts are in cooldown or inactive."
                )

            # Auto-activate the account when assigned to a task
            self.db.activate_account(self.current_account["id"])
            self.tasks_with_current = 0
            print(
                f"✅ Selected and activated account: {self.current_account['username']}"
            )

        return self.current_account

    def mark_task_complete(self, account_id):
        """Mark task as complete and increment counter"""
        self.db.increment_account_tasks(account_id)
        self.tasks_with_current += 1

    def mark_account_error(self, account_id, error_type="error"):
        """Handle account errors (blocks, login failures, etc.)"""
        print("Account error detected. Setting cooldown.")
        self.db.set_account_cooldown(account_id, Config.ACCOUNT_COOLDOWN_TIME * 2)
        self.current_account = None
        self.tasks_with_current = 0

    def add_account(self, username, password, proxy=None):
        """Add a new Instagram account to the pool"""
        return self.db.add_account(username, password, proxy)

    def get_all_accounts(self):
        """Get all accounts with their status"""
        return self.db.get_all_accounts()
