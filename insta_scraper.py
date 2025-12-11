import random
from instagrapi import Client
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class SessionInvalid(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Invalid session: {session_id}")

class Scraper:
    def __init__(self, session_file: str, proxy: str = None) -> None:
        logger.info(f'Logging in with {session_file}...')
        self.session_file = session_file
        self.cl = Client()
        self.cl.load_settings(f'sessions/{session_file}.json')
        self.cl.delay_range = [1, 3]

        if proxy:
            logger.info(f'Using proxy: {proxy}')
            self.cl.set_proxy(proxy)

        if self.verify_session():
            logger.info("Session is valid")
        else:
            logger.error("Session is invalid")
            raise SessionInvalid(session_file)

    def verify_session(self):
        try:
            self.cl.get_timeline_feed()
            return True
        except Exception:
            return False

    def get_profile(self, username: str) -> dict:
        profile = self.cl.user_info_by_username(username)

        return {
            'username' : profile.username,
            'profile_pic_url': str(profile.profile_pic_url),
            'full_name': profile.full_name,
            'is_private': profile.is_private,
            'is_verified': profile.is_verified,
            'biography': profile.biography,
            'media_count': profile.media_count,
            'follower_count': profile.follower_count,
            'following_count': profile.following_count,
            'fbid': profile.interop_messaging_user_fbid,
        }

    def get_comments(self, post_url: str, amount: int = 20) -> list:
        logger.info(f'Fetching comments for : {post_url}')
        media_pk = self.cl.media_pk_from_url(post_url)
        comments = self.cl.media_comments(media_pk, amount=amount)
        print(f'len of comments: {len(comments)}')

        profiles = []
        for comment in comments:
            # user = (comment.user.username, comment.user.full_name)
            user = {
                'username': comment.user.username,
                'full_name': comment.user.full_name,
                'profile_pic_url': comment.user.profile_pic_url,
                'is_private': comment.user.is_private,
                # 'fbid': comment.user,
            }
            profiles.append(user)

        logger.info(f'Fetched {len(profiles)} comments')

        return profiles

    def get_likes(self, post_url: str, amount: int = 20) -> list:
        logger.info(f'Fetching likes for : {post_url}')
        media_pk = self.cl.media_pk_from_url(post_url)
        likes = self.cl.media_likers(media_pk)
        print(len(likes))

        profiles = []
        for like in likes:
            try:
                profiles.append({
                    "username": like.username,
                    "full_name": like.full_name,
                    "profile_pic_url": like.profile_pic_url,
                    "is_private": like.is_private,
                })
            except Exception:
                continue
            if len(profiles) >= amount:
                break
        
        logger.info(f'Fetched {len(profiles)} likes')

        return profiles

    def get_followers(self, username: str, amount: int = 20) -> list:
        BATCH_AMOUNT = 100

        logger.info(f'Starting to fetch followers for {username}')
        user_id = self.cl.user_id_from_username(username)
        next_max_id = "" # The "Cursor" - starts empty
        followers = []

        while len(followers) < amount:
            users_chunk, next_max_id = self.cl.user_followers_v1_chunk(
                user_id, 
                max_amount=min(amount, BATCH_AMOUNT), 
                max_id=next_max_id
            )
            logger.info(f'Fetched {len(users_chunk)} followers')

            followers.extend(
                {
                    'username': user.username, 
                    'full_name': user.full_name,
                    'profile_pic_url': user.profile_pic_url,
                    'is_private': user,
                }
                for user in users_chunk
            )

            if len(followers) >= amount:
                break

            if not next_max_id:
                break

            sleep_time = random.randint(15, 30)
            logger.info(f'Sleeping for {sleep_time} seconds')
            time.sleep(sleep_time)


        logger.info(f'Fetched Total {len(followers)} followers for {username}')

        return followers

