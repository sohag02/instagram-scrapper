

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from database import Database
from account_manager import AccountManager
from scraper import InstagramScraper
from config import Config
from data_formatter import DataFormatter
import threading
import os
import json
from functools import wraps
from datetime import datetime
from task_handler import handle_task

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Initialize components
db = Database()
account_manager = AccountManager()

# Active scrapers
active_scrapers = {}

# Simple API key authentication
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        expected_key = os.getenv('API_KEY', 'dev-key-change-in-production')
        
        if api_key != expected_key:
            return jsonify({'error': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

def load_accounts_from_env():
    """Load Instagram accounts from .env file on startup"""
    accounts = Config.get_instagram_accounts()
    
    if not accounts:
        print("⚠️  No Instagram accounts found in .env file")
        print("💡 Add accounts to .env file or use the web interface")
        return
        
    print(f"🔄 Loading {len(accounts)} Instagram accounts from .env...")
    
    for acc in accounts:
        try:
            # Check if account already exists
            existing_accounts = db.get_all_accounts()
            exists = any(a['username'] == acc['username'] for a in existing_accounts)
            
            if not exists:
                db.add_account(acc['username'], acc['password'])
                print(f"✅ Added account: {acc['username']}")
            else:
                print(f"ℹ️  Account already exists: {acc['username']}")
                
        except Exception as e:
            print(f"❌ Error adding account {acc['username']}: {str(e)}")
            
    print(f"✨ Account loading complete!")


def process_task(task_id):
    """Process a scraping task in background"""
    scraper = None
    account = None
    
    try:
        # Get task details
        tasks = db.get_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        
        if not task:
            raise Exception(f"Task {task_id} not found")

        max_items = task.get('max_items', 10000)

        # Get available account
        account = db.get_available_account()
        if not account:
            raise Exception("No available accounts")
        
        # Update task status
        db.update_task_status(task_id, 'running')
        
        # Initialize scraper
        scraper = InstagramScraper()
        print('inti')
        scraper.init_driver()
        
        # Login
        print('logging in')
        if not scraper.login(account['username'], account['password']):
            raise Exception("Login failed")
        
        # Execute task based on type
        result = None
        
        if task['task_type'] == 'profile':
            result = scraper.scrape_profile(task['target'])
            db.save_scraped_data(task_id, 'profile', result)
            
        elif task['task_type'] == 'posts':
            result = scraper.scrape_posts(task['target'], max_posts=max_items)
            db.save_scraped_data(task_id, 'posts', result)
            
        elif task['task_type'] == 'hashtag':
            result = scraper.scrape_hashtag(task['target'], max_posts=max_items)
            db.save_scraped_data(task_id, 'hashtag', result)
            
        elif task['task_type'] == 'followers':
            result = scraper.scrape_followers(task['target'], max_followers=max_items)
            db.save_scraped_data(task_id, 'followers', result)
            
        elif task['task_type'] == 'following':
            result = scraper.scrape_following(task['target'], max_following=max_items)
            db.save_scraped_data(task_id, 'following', result)
            
        # NEW: Comments scraping
        elif task['task_type'] == 'comments':
            result = scraper.scrape_post_comments(task['target'], max_comments=max_items)
            db.save_scraped_data(task_id, 'comments', result)
            
        # NEW: Likes scraping
        elif task['task_type'] == 'likes':
            result = scraper.scrape_post_likes(task['target'], max_likes=max_items)
            db.save_scraped_data(task_id, 'likes', result)
        
        # Calculate result count
        result_count = 1 if isinstance(result, dict) else len(result) if isinstance(result, list) else 0
        
        # Mark task complete
        db.update_task_status(
            task_id,
            'completed',
            result=f"Successfully scraped {result_count} item(s) from {task['target']}"
        )
        
        db.increment_account_tasks(account['id'])
        print(f"✅ Task {task_id} completed - {result_count} items scraped")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Task {task_id} failed: {error_msg}")
        db.update_task_status(task_id, 'failed', error_message=error_msg)
        
    finally:
        if scraper:
            scraper.close()
        if task_id in active_scrapers:
            del active_scrapers[task_id]

@app.route('/')
def index():
    """Render main application page"""
    return render_template('index.html')

@app.route('/api/accounts', methods=['GET', 'POST'])
def manage_accounts():
    """Manage Instagram accounts"""
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
            
        try:
            account_id = db.add_account(username, password)
            return jsonify({'success': True, 'account_id': account_id})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    else:  # GET
        accounts = db.get_all_accounts()
        # Remove passwords from response for security
        for acc in accounts:
            acc['password'] = '********'
        return jsonify(accounts)


@app.route('/api/tasks', methods=['GET', 'POST'])
def manage_tasks():
    if request.method == 'POST':
        data = request.json
        task_type = data.get('task_type')
        target = data.get('target')
        max_items = data.get('max_items', 10000)
        
        if not task_type or not target:
            return jsonify({'error': 'Task type and target required'}), 400
        
        # Updated valid task types - includes comments and likes
        valid_types = ['profile', 'posts', 'hashtag', 'followers', 'following', 'comments', 'likes']
        
        if task_type not in valid_types:
            return jsonify({
                'error': f'Invalid task type. Must be one of: {", ".join(valid_types)}'
            }), 400
        
        try:
            # Create task
            task_id = db.create_task(task_type, target)
            
            # Start task in background
            thread = threading.Thread(target=handle_task, args=(db, task_id, task_type, target, max_items))
            thread.daemon = True
            thread.start()
            print(f'Task #{task_id} started. Type : {task_type}')
            
            active_scrapers[task_id] = thread
            
            return jsonify({
                'success': True, 
                'task_id': task_id,
                'message': f'Task #{task_id} created. Scraping up to {max_items} items from {target}'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    else:  # GET
        status = request.args.get('status')
        limit = request.args.get('limit', 100, type=int)
        tasks = db.get_tasks(status=status, limit=limit)
        return jsonify(tasks)

@app.route('/api/tasks/<int:task_id>')
def get_task(task_id):
    """Get specific task details"""
    try:
        tasks = db.get_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
            
        return jsonify(task)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/data')
def get_task_data(task_id):
    """Get scraped data for a task (raw JSON format)"""
    try:
        data = db.get_scraped_data(task_id)
        
        if not data:
            return jsonify({'error': 'No data found for this task'}), 404
            
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/data/table')
def get_task_data_table(task_id):
    """Get task data in flattened table format for web display"""
    try:
        # Get raw scraped data
        scraped_data_records = db.get_scraped_data(task_id)
        if not scraped_data_records:
            return jsonify({'error': 'No data found'}), 404
        
        # Get task details
        tasks = db.get_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Extract the actual data
        if isinstance(scraped_data_records, list) and len(scraped_data_records) > 0:
            raw_data = scraped_data_records[0].get('data')
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
        else:
            raw_data = scraped_data_records
        
        # Flatten the data based on task type
        flattened_rows = DataFormatter.format_for_task_type(task['task_type'], raw_data)
        
        # Get column order
        columns = DataFormatter.get_column_order(task['task_type'])
        if not columns and flattened_rows:
            columns = list(flattened_rows[0].keys())
        
        return jsonify({
            'task_id': task_id,
            'task_type': task['task_type'],
            'target': task['target'],
            'columns': columns,
            'rows': flattened_rows,
            'total_rows': len(flattened_rows)
        })
    except Exception as e:
        print(f"Table Data Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/export/csv')
def export_task_csv(task_id):
    """Export task data as flattened CSV file"""
    try:
        # Get raw scraped data
        scraped_data_records = db.get_scraped_data(task_id)
        if not scraped_data_records:
            return jsonify({'error': 'No data found'}), 404
        
        # Get task details
        tasks = db.get_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Extract the actual data (it's stored in 'data' field of scraped_data records)
        if isinstance(scraped_data_records, list) and len(scraped_data_records) > 0:
            raw_data = scraped_data_records[0].get('data')
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
        else:
            raw_data = scraped_data_records
        
        # Flatten the data based on task type
        flattened_rows = DataFormatter.format_for_task_type(task['task_type'], raw_data)
        
        if not flattened_rows:
            return jsonify({'error': 'No data to export'}), 404
        
        # Convert to CSV
        csv_data = DataFormatter.to_csv(flattened_rows)
        
        # Generate safe filename
        safe_target = "".join(c for c in task['target'] if c.isalnum() or c in ('-', '_'))
        filename = f"instagram_{task['task_type']}_{safe_target}_{task_id}.csv"
        
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
    except Exception as e:
        print(f"CSV Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/export/json')
def export_task_json(task_id):
    """Export task data as JSON file"""
    try:
        data = db.get_scraped_data(task_id)
        
        if not data:
            return jsonify({'error': 'No data found'}), 404
        
        # Get task details
        tasks = db.get_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Generate safe filename
        safe_target = "".join(c for c in task['target'] if c.isalnum() or c in ('-', '_'))
        filename = f"instagram_{task['task_type']}_{safe_target}_{task_id}.json"
        
        return Response(
            json.dumps(data, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'application/json; charset=utf-8'
            }
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    try:
        accounts = db.get_all_accounts()
        tasks = db.get_tasks(limit=1000)
        
        stats = {
            'total_accounts': len(accounts),
            'active_accounts': len([a for a in accounts if a.get('is_active')]),
            'available_accounts': len([a for a in accounts if a.get('status') == 'available']),
            'cooldown_accounts': len([a for a in accounts if a.get('status') == 'cooldown']),
            'total_tasks': len(tasks),
            'pending_tasks': len([t for t in tasks if t.get('status') == 'pending']),
            'running_tasks': len([t for t in tasks if t.get('status') == 'running']),
            'completed_tasks': len([t for t in tasks if t.get('status') == 'completed']),
            'failed_tasks': len([t for t in tasks if t.get('status') == 'failed']),
            'active_scrapers': len(active_scrapers)
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db.get_tasks(limit=1)
        db_status = 'connected'
    except:
        db_status = 'error'
    
    return jsonify({
        'status': 'healthy' if db_status == 'connected' else 'degraded',
        'active_scrapers': len(active_scrapers),
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/tasks/<int:task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """Cancel a running task"""
    try:
        if task_id in active_scrapers:
            db.update_task_status(task_id, 'failed', error_message='Task cancelled by user')
            del active_scrapers[task_id]
            return jsonify({'success': True, 'message': 'Task cancelled'})
        else:
            return jsonify({'error': 'Task not found or not running'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create required directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Load accounts from .env file
    print("\n" + "="*60)
    print("🚀 Instagram Scraper Pro - Starting...")
    print("="*60)
    
    try:
        load_accounts_from_env()
    except Exception as e:
        print(f"⚠️  Warning loading accounts: {str(e)}")
    
    port = int(os.getenv('PORT', 8002))
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    
    print("="*60)
    print(f"🌐 Server: http://0.0.0.0:{port}")
    print(f"🔧 Debug Mode: {debug_mode}")
    print(f"💾 Database: {Config.DATABASE_PATH}")
    print("="*60 + "\n")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port, threaded=True)
