import os
import requests
import base64
from dotenv import load_dotenv

# טעינת משתני הסביבה
load_dotenv()
CLIENT_ID = os.getenv("MUSICAPI_CLIENT_ID")
CLIENT_SECRET = os.getenv("MUSICAPI_CLIENT_SECRET")

def get_access_token():
    """פונקציה לקבלת טוקן זמני מ-MusicAPI"""
    url = "https://api.musicapi.com/api/token" # נתיב משוער, ייתכן שנצטרך לעדכן לפי הדוקומנטציה שלהם
    
    # קידוד ה-ID וה-Secret לפי סטנדרט OAuth
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")
    
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "client_credentials"
    }
    
    print("Requesting access token...")
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Failed to get token: {response.status_code}")
        print(response.text)
        return None

def test_search_song(song_name, artist, token):
    """פונקציה לחיפוש שיר בעזרת הטוקן שקיבלנו"""
    url = "https://api.musicapi.com/api/search"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    params = {
        "q": f"{song_name} {artist}",
        "type": "track",
        "limit": 1
    }
    
    print(f"Searching for: {song_name} by {artist}...")
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        print("Success! Here is the data:")
        print(response.json())
    else:
        print(f"Search failed with status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    # שלב 1: קבלת טוקן
    token = get_access_token()
    
    # שלב 2: אם קיבלנו טוקן, נבצע את החיפוש
    if token:
        print("\nToken received successfully!")
        test_search_song("Hotel California", "Eagles", token)