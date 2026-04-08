import csv
import matplotlib.pyplot as plt

def plot_split_graph():
    seconds = []
    anomaly_score = []
    server_threshold = []
    cumulative_throughput = []

    file_name = 'attack_research_data_ga.csv'
    try:
        with open(file_name, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    seconds.append(float(row['seconds_since_start']))
                    anomaly_score.append(float(row['anomaly_score']))
                    server_threshold.append(float(row['server_threshold']))
                    cumulative_throughput.append(float(row['cumulative_throughput']))
                except (ValueError, KeyError):
                    continue
    except FileNotFoundError:
        print(f"Error: Could not find '{file_name}'. Make sure you are in the right directory and the GA has run.")
        return

    if not seconds:
        print("Error: No valid data found in the file. Let the algorithm run a bit longer.")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    fig.suptitle('Creeping Ransomware (GA): Stealth vs. Cumulative Damage', fontsize=16, fontweight='bold', y=0.95)

    ax1.plot(seconds, anomaly_score, label='Raw Anomaly Score', color='#1f77b4', linewidth=1.5)
    ax1.plot(seconds, server_threshold, label='Detection Threshold (Floor)', color='#d62728', linewidth=2, linestyle='--')
    
    ax1.fill_between(seconds, 0, server_threshold, color='#d62728', alpha=0.1)

    ax1.set_title('Detection Status: Maintaining Raw Score Above the Threshold', fontsize=12)
    ax1.set_ylabel('Anomaly Score')
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right')

    ax2.plot(seconds, cumulative_throughput, label='Cumulative Damage (Chars Changed)', color='#2ca02c', linewidth=2)
    ax2.fill_between(seconds, 0, cumulative_throughput, color='#2ca02c', alpha=0.2)

    ax2.set_title('Attack Impact: Accumulating Damage Over Time', fontsize=12)
    ax2.set_xlabel('Time Since Start (seconds)')
    ax2.set_ylabel('Cumulative Damage')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper left')

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    output_filename = 'split_results_graph_ga.png'
    plt.savefig(output_filename, dpi=300)
    print(f"Graph successfully saved as '{output_filename}'")

if __name__ == "__main__":
    plot_split_graph()