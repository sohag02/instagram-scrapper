import sqlite3
from datetime import datetime
import json
from contextlib import contextmanager

class Database:
    def __init__(self, db_path='data/scraper.db'):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Accounts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    tasks_completed INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    cooldown_until TIMESTAMP,
                    status TEXT DEFAULT 'available',
                    ip TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tasks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    account_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES accounts (id)
                )
            ''')
            
            # Scraped data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraped_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    data_type TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                )
            ''')
    
    # Account Management
    def add_account(self, username, password):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO accounts (username, password) VALUES (?, ?)',
                (username, password)
            )
            return cursor.lastrowid
    
    # def get_available_account(self):
    #     with self.get_connection() as conn:
    #         cursor = conn.cursor()
    #         cursor.execute('''
    #             SELECT * FROM accounts 
    #             WHERE is_active = 1 
    #             AND status = 'available'
    #             AND (cooldown_until IS NULL OR cooldown_until < datetime('now'))
    #             ORDER BY tasks_completed ASC, last_used ASC
    #             LIMIT 1
    #         ''')
    #         row = cursor.fetchone()  # <-- FETCH ONCE
    #         return dict(row) if row else None  # <-- USE THE FETCHED ROW

    def get_available_account(self):
        """Get an available account, prioritizing active ones, but fallback to any account if needed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # First, try to get an account that meets all conditions
            cursor.execute('''
                SELECT * FROM accounts 
                WHERE is_active = 1 
                AND status = 'available' 
                AND (cooldown_until IS NULL OR cooldown_until < datetime('now'))
                ORDER BY tasks_completed ASC, last_used ASC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            
            # If no available account, find any inactive account and activate it
            cursor.execute('''
                SELECT * FROM accounts 
                WHERE (cooldown_until IS NULL OR cooldown_until < datetime('now'))
                ORDER BY tasks_completed ASC, last_used ASC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            
            if row:
                account = dict(row)
                # Auto-activate this account
                self.activate_account(account['id'])
                # Return the updated account data
                cursor.execute('SELECT * FROM accounts WHERE id = ?', (account['id'],))
                return dict(cursor.fetchone())
            
            # If all accounts are in cooldown, reset the one with earliest cooldown
            cursor.execute('''
                SELECT * FROM accounts 
                ORDER BY cooldown_until ASC, tasks_completed ASC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            
            if row:
                account = dict(row)
                # Reset cooldown and activate
                self.reset_account_cooldown(account['id'])
                self.activate_account(account['id'])
                cursor.execute('SELECT * FROM accounts WHERE id = ?', (account['id'],))
                return dict(cursor.fetchone())
            
            return None   
        
    def update_account_status(self, account_id, status):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE accounts SET status = ?, last_used = ? WHERE id = ?',
                (status, datetime.now(), account_id)
            )
    
    def increment_account_tasks(self, account_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE accounts SET tasks_completed = tasks_completed + 1 WHERE id = ?',
                (account_id,)
            )
    
    def set_account_cooldown(self, account_id, cooldown_seconds):
        from datetime import timedelta
        cooldown_until = datetime.now() + timedelta(seconds=cooldown_seconds)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE accounts SET cooldown_until = ?, status = ? WHERE id = ?',
                (cooldown_until, 'cooldown', account_id)
            )
    
    def get_all_accounts(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accounts ORDER BY id DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    # Task Management
    def create_task(self, task_type, target, account_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO tasks (task_type, target, account_id) VALUES (?, ?, ?)',
                (task_type, target, account_id)
            )
            return cursor.lastrowid
    
    def update_task_status(self, task_id, status, result=None, error_message=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            completed_at = datetime.now() if status == 'completed' else None
            if isinstance(result, (dict, list)):
                result_to_store = json.dumps(result, default=str)
            else:
                result_to_store = result
            cursor.execute(
                '''UPDATE tasks 
                   SET status = ?, result = ?, error_message = ?, completed_at = ?
                   WHERE id = ?''',
                (status, result_to_store, error_message, completed_at, task_id)
            )
    
    def get_tasks(self, status=None, limit=50):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    'SELECT * FROM tasks WHERE status = ? ORDER BY id DESC LIMIT ?',
                    (status, limit)
                )
            else:
                cursor.execute('SELECT * FROM tasks ORDER BY id DESC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # Data Storage
    def save_scraped_data(self, task_id, data_type, data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO scraped_data (task_id, data_type, data) VALUES (?, ?, ?)',
                (task_id, data_type, json.dumps(data, default=str))
            )
            return cursor.lastrowid
    
    def get_scraped_data(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM scraped_data WHERE task_id = ?', (task_id,))
            results = cursor.fetchall()
            return [{'id': row['id'], 'data_type': row['data_type'], 
                    'data': json.loads(row['data']), 'created_at': row['created_at']} 
                   for row in results]
            
    def activate_account(self, account_id):
        """Activate an account when a task is assigned"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE accounts SET is_active = 1, status = ? WHERE id = ?',
                ('available', account_id)
            )
            print(f"✅ Account {account_id} automatically activated")

    def reset_account_cooldown(self, account_id):
        """Reset account cooldown to make it immediately available"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE accounts SET cooldown_until = NULL WHERE id = ?',
                (account_id,)
            )
            print(f"🔄 Account {account_id} cooldown reset")

    def assign_task_to_account(self, task_id, account_id):
        """Assign a task to an account and ensure account is activated"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Update task with account
            cursor.execute(
                'UPDATE tasks SET account_id = ? WHERE id = ?',
                (account_id, task_id)
            )
            # Auto-activate the account
            cursor.execute(
                'UPDATE accounts SET is_active = 1, status = ?, last_used = ? WHERE id = ?',
                ('available', datetime.now(), account_id)
            )

if __name__ == '__main__':
    db = Database()
    db.init_db()
        
