import os
import json
import time
import requests
import subprocess

LOG_FILE = "/var/log/nginx/access.log"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")
ERROR_LIMIT = float(os.getenv("ERROR_RATE_THRESHOLD", 2.0))
CHECK_LAST = int(os.getenv("WINDOW_SIZE", 200))
WAIT_BETWEEN_ALERTS = int(os.getenv("ALERT_COOLDOWN_SEC", 300))

recent_requests = []
current_pool = None
last_alert = 0

def send_alert(msg):
    if not SLACK_WEBHOOK:
        print("Warning: No Slack webhook configured")
        return
    
    data = {"text": ":rotating_light: " + msg}
    
    try:
        response = requests.post(SLACK_WEBHOOK, json=data, timeout=5)
        if response.status_code != 200:
            print(f"Slack error: {response.status_code}")
    except Exception as err:
        print(f"Failed to send alert: {err}")

def check_if_pool_changed(pool_name):
    global current_pool, last_alert
    
    if current_pool is None:
        current_pool = pool_name
        return
    
    if pool_name != current_pool:
        now = time.time()
        if now - last_alert > WAIT_BETWEEN_ALERTS:
            message = f"Failover detected! Switched from {current_pool} to {pool_name}"
            send_alert(message)
            last_alert = now
        else:
            print("Failover detected but waiting before next alert")
        current_pool = pool_name

def check_errors():
    global last_alert
    if len(recent_requests) < CHECK_LAST:
        return
    
    error_count = sum(1 for status in recent_requests if status.startswith("5"))
    error_percent = (error_count / len(recent_requests)) * 100
    
    if error_percent > ERROR_LIMIT:
        now = time.time()
        if now - last_alert > WAIT_BETWEEN_ALERTS:
            message = f"High error rate: {error_percent:.1f}% (limit is {ERROR_LIMIT}%)"
            send_alert(message)
            last_alert = now
        else:
            print("High errors detected but waiting before next alert")

def watch_log_file():
    """Use tail -F so we can follow the log even on non-seekable volumes"""
    print(f"Starting to watch: {LOG_FILE}")
    
    try:
        proc = subprocess.Popen(
            ["tail", "-F", LOG_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError:
        print(f"Log file not found: {LOG_FILE}")
        return

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            log_data = json.loads(line)
            pool = log_data.get("pool")
            status = str(log_data.get("status", ""))
            
            check_if_pool_changed(pool)
            
            recent_requests.append(status)
            if len(recent_requests) > CHECK_LAST:
                recent_requests.pop(0)
            
            check_errors()
        except json.JSONDecodeError:
            continue

if __name__ == "__main__":
    print("Nginx Log Watcher Starting...")
    try:
        watch_log_file()
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
