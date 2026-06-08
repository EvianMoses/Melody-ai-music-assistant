import spotipy
from spotipy.oauth2 import SpotifyOAuth

# הכנס את המפתחות שלך כאן (בתוך הגרשיים)
CLIENT_ID = 'eaad377589d14dc2bb7bedf97db5f58a'
CLIENT_SECRET = '20906ddca2834d9283dbf16ccfa6e553'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

# אלו ההרשאות שאנחנו מבקשים עבור ה-Agent שלנו:
# 1. קריאת היסטוריית שמיעה
# 2. קריאת האמנים האהובים עליך
# 3. הוספת שירים לפלייליסטים פומביים ופרטיים
SCOPE = 'user-read-recently-played user-top-read playlist-modify-public playlist-modify-private'

print("Starting authentication process...")

# הפעלת תהליך ההתחברות לספוטיפיי
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    open_browser=True # פותח את הדפדפן אוטומטית
))

# ביצוע קריאה פשוטה כדי לאלץ את ההתחברות לקרות עכשיו
user = sp.current_user()
print(f"\nSuccess! Logged in as: {user['display_name']}")

# שליפת מפתח המאסטר מתוך קובץ הזיכרון
auth_manager = sp.auth_manager
token_info = auth_manager.get_cached_token()

print("\n" + "="*40)
print("🎯 THIS IS YOUR MASTER REFRESH TOKEN 🎯")
print("="*40)
print(token_info['refresh_token'])
print("="*40 + "\n")
print("Copy the token above and save it somewhere safe.")