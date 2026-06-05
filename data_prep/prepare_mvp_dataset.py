import pandas as pd

INPUT_PATH = r"data\all_songs_rating_review\song.csv"
OUTPUT_PATH = r"cleaned_large_dataset.csv"

# טעינת הנתונים
df = pd.read_csv(INPUT_PATH)
initial_rows = len(df)

# מחיקת שורות שבהן עמודת התיאור חסרה (NaN/Null)
df = df.dropna(subset=["Description"])

# מחיקת שורות שבהן עמודת התיאור ריקה או מכילה רק רווחים
df = df[df["Description"].str.strip() != ""]

final_rows = len(df)

# שמירת הדאטה-סט הנקי לקובץ חדש
df.to_csv(OUTPUT_PATH, index=False)

# הדפסות לבקרה (כדי שתוכל לראות כמה שורות נשארו)
print(f"Success! '{OUTPUT_PATH}' created.")
print(f"Rows BEFORE cleaning: {initial_rows}")
print(f"Rows AFTER cleaning: {final_rows}")
print(f"Total rows removed: {initial_rows - final_rows}")

print(f"\nColumns ({len(df.columns)}):")
print(df.columns.tolist())