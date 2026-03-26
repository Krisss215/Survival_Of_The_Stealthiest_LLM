import os
import pandas as pd
import glob
import numpy as np
from environment.settings import TRAINING_CSV_FOLDER_PATH, EVALUATION_CSV_FOLDER_PATH, ALL_CSV_HEADERS

# הגדרות נתיבים
RAW_DATA_PATH = "./fingerprints"
HEADERS = ALL_CSV_HEADERS.split(',')

def ingest_data():
    print("--- Starting Data Ingestion (Fixed Version) ---")
    
    all_files = glob.glob(os.path.join(RAW_DATA_PATH, "fp-*.txt"))
    if not all_files:
        print("Error: No raw fingerprints found!")
        return

    print(f"Found {len(all_files)} samples. Processing...")

    data_list = []
    for f in all_files:
        with open(f, 'r') as file:
            line = file.read().strip()
            
            # ניקוי הסוגריים המרובעים שהיו בתוך הטקסט
            line = line.replace('[', '').replace(']', '')
            
            row = line.split(',')
            if len(row) == len(HEADERS):
                data_list.append(row)

    # יצירת ה-DataFrame
    df = pd.DataFrame(data_list, columns=HEADERS)
    
    # המרה למספרים בצורה גורפת על כל הטבלה
    # השורה הזו מחליפה את הלולאה שגרמה לשגיאה
    df = df.apply(pd.to_numeric, errors='coerce')

    # ניקוי: השארת רק עמודות מספריות ומחיקת שורות עם ערכים חסרים
    df = df.select_dtypes(include=[np.number])
    df = df.dropna(axis=0, how='any')

    print(f"✅ Success! Processed {len(df)} clean rows.")

    # פיצול ל-Training ו-Evaluation (80/20)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    eval_df = df.iloc[split_idx:]

    # יצירת התיקיות במידה ולא קיימות
    os.makedirs(TRAINING_CSV_FOLDER_PATH, exist_ok=True)
    os.makedirs(EVALUATION_CSV_FOLDER_PATH, exist_ok=True)

    # שמירה
    train_path = os.path.join(TRAINING_CSV_FOLDER_PATH, "normal-behavior.csv")
    eval_path = os.path.join(EVALUATION_CSV_FOLDER_PATH, "normal-behavior.csv")
    
    train_df.to_csv(train_path, index=False)
    eval_df.to_csv(eval_path, index=False)

    print(f"Saved {len(train_df)} rows to Training and {len(eval_df)} rows to Evaluation.")
    print(f"Files saved at: {TRAINING_CSV_FOLDER_PATH}")

if __name__ == "__main__":
    ingest_data()