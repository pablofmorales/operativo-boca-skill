import os
import sys
import json
import subprocess
import urllib.request
from datetime import datetime, timedelta

TELEGRAM_CHAT_ID = "7727530215"
BOCA_ACCOUNTS = [
    "La12tuittera", "Tato_Aguilera", "SANGREXENEIZE", "DavooXeneizeJRR",
    "BocaJrsOficial", "TermitoBostero", "Labocatw", "EslovenoOficial"
]

def send_telegram_message(text):
    cmd = [
        "openclaw", "message", "send",
        "--channel", "telegram",
        "--to", TELEGRAM_CHAT_ID,
        "--message", text
    ]
    subprocess.run(cmd, capture_output=True)

def get_twitter_creds():
    try:
        auth_token = subprocess.run(["pass", "show", "x-twitter/bird"], capture_output=True, text=True).stdout.strip()
        ct0 = subprocess.run(["pass", "show", "x-twitter/bird-ct0"], capture_output=True, text=True).stdout.strip()
        return auth_token, ct0
    except:
        return None, None

def check_boca_match_today():
    config_path = "/home/pablo/.openclaw/alfred-workspace/memory/boca_fixture.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = json.load(f)
            today_str = datetime.now().strftime("%Y-%m-%d")
            if today_str in data:
                match_time_str = data[today_str]["time"]
                hour, minute = map(int, match_time_str.split(":"))
                now = datetime.now()
                match_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return True, match_start
    return False, None

def get_reddit_thread_comments():
    try:
        req = urllib.request.Request(
            "https://www.reddit.com/r/BocaJuniors/new.json?limit=15",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OperativoBoca/1.0"}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        target_thread_id = None
        target_title = ""
        keywords = ['partido', 'previa', 'post', 'discusion', 'thread', 'vs', 'mt']
        
        for post in data['data']['children']:
            title = post['data']['title'].lower()
            if any(word in title for word in keywords) and ("boca" in title or "mt" in title):
                target_thread_id = post['data']['id']
                target_title = post['data']['title']
                break
                
        if not target_thread_id:
            req_hot = urllib.request.Request(
                "https://www.reddit.com/r/BocaJuniors/hot.json?limit=5",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OperativoBoca/1.0"}
            )
            with urllib.request.urlopen(req_hot) as response_hot:
                data_hot = json.loads(response_hot.read().decode())
                for post in data_hot['data']['children']:
                    title = post['data']['title'].lower()
                    if any(word in title for word in keywords) and ("boca" in title or "mt" in title):
                        target_thread_id = post['data']['id']
                        target_title = post['data']['title']
                        break

        if not target_thread_id:
            return ""

        req_comments = urllib.request.Request(
            f"https://www.reddit.com/r/BocaJuniors/comments/{target_thread_id}.json?sort=new",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OperativoBoca/1.0"}
        )
        with urllib.request.urlopen(req_comments) as response_comments:
            comments_data = json.loads(response_comments.read().decode())
            
        comments = []
        for child in comments_data[1]['data']['children'][:10]:
            body = child['data'].get('body')
            if body and body != "[deleted]" and body != "[removed]":
                comments.append(body.replace('\n', ' '))
                
        if not comments:
            return f"(Thread '{target_title}' encontrado, pero sin comentarios recientes)"
            
        return f"Thread Reddit: {target_title}\n" + "\n".join([f"- {c}" for c in comments])
    except Exception as e:
        return f"(Error leyendo Reddit: {e})"

def get_tweets_and_summarize():
    auth_token, ct0 = get_twitter_creds()
    all_tweets = []
    
    if auth_token and ct0:
        for account in BOCA_ACCOUNTS:
            try:
                result = subprocess.run([
                    "bird", 
                    "--auth-token", auth_token, 
                    "--ct0", ct0, 
                    "user-tweets", account, "--json"
                ], capture_output=True, text=True)
                
                tweets = json.loads(result.stdout)
                for t in tweets[:3]:
                    all_tweets.append(f"@{account}: {t.get('text', '')}")
            except Exception as e:
                continue
    
    tweets_text = "\n---\n".join(all_tweets) if all_tweets else "(No se pudieron obtener tweets)"
    
    reddit_comments = get_reddit_thread_comments()
    reddit_context = f"\n\nComentarios en Reddit (r/BocaJuniors):\n{reddit_comments}" if reddit_comments else ""
            
    if not all_tweets and not reddit_comments:
        return "🔵🟡🔵 *Operativo Boca*: No pude recuperar datos de Twitter ni de Reddit."
        
    prompt = f"""Estás monitoreando las redes (Twitter y Reddit) durante un evento/partido de Boca Juniors. 
Resume el 'termómetro' de los hinchas basándote en la siguiente data. 
Sé breve, tipo reporte de situación crudo y directo (máximo 5 líneas). Destaca calenturas, festejos, o críticas a jugadores/DT.

Tweets de referentes:
{tweets_text}
{reddit_context}
"""
    
    resumen = subprocess.run(["openclaw", "run", "--model", "gemini-flash", "--prompt", prompt], capture_output=True, text=True).stdout
    
    return f"🔵🟡🔵 **Termómetro Xeneize** 🔵🟡🔵\n\n{resumen.strip()}"

def main():
    force_run = len(sys.argv) > 1 and sys.argv[1] == "--force"
    
    has_match, match_start = check_boca_match_today()
    
    if not has_match and not force_run:
        sys.exit(0)
        
    if has_match:
        now = datetime.now()
        start_window = match_start - timedelta(minutes=15)
        end_window = match_start + timedelta(minutes=135)
        if not (start_window <= now <= end_window) and not force_run:
            sys.exit(0)
            
    resumen = get_tweets_and_summarize()
    send_telegram_message(resumen)

if __name__ == "__main__":
    main()
