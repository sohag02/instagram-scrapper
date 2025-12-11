from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, ChallengeRequired
from instagrapi.mixins.challenge import ChallengeChoice
import os
from database import Database

os.makedirs('sessions', exist_ok=True)

db = Database()

def challenge_code_handler(username, choice):
    if choice == ChallengeChoice.SMS:
        code = input("Enter the code sent to your SMS: ")
    elif choice == ChallengeChoice.EMAIL:
        code = input("Enter the code sent to your EMAIL: ")
    return int(code)

def create_session(username, password):
    cl = Client()
    cl.challenge_code_handler = challenge_code_handler
    filename = f'sessions/{username}.json'
    
    # Optional: Set a specific device to look more "consistent"
    # cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "android_release": "8.0.0", "dpi": "480dpi", "resolution": "1080x1920", "manufacturer": "OnePlus", "device": "ONEPLUS A6003", "model": "OnePlus 6", "cpu": "qcom", "version_code": "314665256"})

    print(f"Attempting login for {username}...")

    try:
        cl.login(username, password)
    except TwoFactorRequired:
        # Handle 2FA if enabled
        code = input("2FA Code Required. Enter the SMS/App code: ")
        cl.two_factor_login(code)
    except ChallengeRequired:
        # Handle Email/SMS Challenge
        print("Challenge Required! The library is trying to resolve it...")
        # In many cases, you might need to approve the login on your phone manually
        # or use cl.challenge_resolve(cl.last_json) methods depending on the challenge type.
        code = input("Enter the code sent to your email/SMS: ")
        cl.challenge_code_handler(code, me=None) 

    # Verify login worked
    if cl.user_id:
        print(f"Login Successful! User ID: {cl.user_id}")
        
        # Dump settings to file
        cl.dump_settings(filename)

        db.add_account(username, password)
        
        print(f"✅ Session saved to '{filename}'")
    else:
        print("❌ Login failed (No User ID retrieved).")

if __name__ == "__main__":
    USER = input("Instagram Username: ")
    PASS = input("Instagram Password: ")
    create_session(USER, PASS)
    accounts = db.get_all_accounts()
    print(accounts)