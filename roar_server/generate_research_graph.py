import pandas as pd
import matplotlib.pyplot as plt
import os

# ודאי שהנתיב תואם למה שקרסור הגדיר
LOG_FILE = "anomaly_log.csv"

def generate_graph():
    if not os.path.exists(LOG_FILE):
        print(f"Error: {LOG_FILE} not found. Run the server and client first!")
        return

    # טעינת הנתונים
    df = pd.read_csv(LOG_FILE)
    
    # המרת זמן לשניות מתחילת הניסוי כדי שיהיה קריא
    df['elapsed_time'] = df['timestamp'] - df['timestamp'].iloc[0]

    plt.figure(figsize=(14, 7))
    
    # ציור הציון (Score)
    plt.plot(df['elapsed_time'], df['score'], label='Isolation Forest Score', color='#3498db', alpha=0.7)
    
    # ציור הסף (Threshold) - זה הקו שזוחל!
    plt.plot(df['elapsed_time'], df['threshold'], label='Adaptive Threshold (EMA)', color='#e74c3c', linewidth=2.5)
    
    # סימון אנומליות בנקודות שחורות
    anomalies = df[df['is_anomaly'] == 1]
    if not anomalies.empty:
        plt.scatter(anomalies['elapsed_time'], anomalies['score'], color='black', marker='x', s=100, label='Detection Triggered', zorder=5)

    # הוספת כותרות ועיצוב
    plt.title("The Adaptivity Paradox: How Creeping Ransomware Exploits Flexible Defense", fontsize=16)
    plt.xlabel("Time Since Start (seconds)", fontsize=12)
    plt.ylabel("Score Value", fontsize=12)
    plt.legend(loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # שמירת הגרף כתמונה למצגת שלך
    plt.savefig("research_final_result.png", dpi=300)
    print("Success! Graph saved as 'research_final_result.png'")
    plt.show()

if __name__ == "__main__":
    generate_graph()
    