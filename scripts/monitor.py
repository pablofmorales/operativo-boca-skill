import os
import sys
import json
import subprocess
import urllib.request
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.json")
EXAMPLE_CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.example.json")

if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        CONFIG = json.load(f)
else:
    print(f"⚠️ No se encontró {CONFIG_PATH}. Usando configuración de ejemplo.")
    with open(EXAMPLE_CONFIG_PATH, "r") as f:
        CONFIG = json.load(f)

TELEGRAM_CHAT_ID = CONFIG.get("telegram_chat_id")
BOCA_ACCOUNTS = CONFIG.get("twitter_accounts", [])
REDDIT_SUB = CONFIG.get("reddit_subreddit", "BocaJuniors")
REDDIT_KEYWORDS = CONFIG.get("reddit_keywords", ["partido", "previa", "post", "discusion", "thread", "mt"])
FIXTURE_RELATIVE_PATH = CONFIG.get("fixture_path", "config/fixture.example.json")

def send_telegram_message(text):
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "TU_CHAT_ID_AQUI":
        print("⚠️ TELEGRAM_CHAT_ID no configurado. Consola:")
        print(text)
        return

    cmd = [
        "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", TELEGRAM_CHAT_ID,
        "--message", text
    ]
    subprocess.run(cmd, capture_output=True)

def get_twitter_creds():
    auth_token = os.environ.get("TWITTER_AUTH_TOKEN")
    ct0 = os.environ.get("TWITTER_CT0")
    if not auth_token or not ct0:
        try:
            auth_token = subprocess.run(["pass", "show", "x-twitter/bird"], capture_output=True, text=True).stdout.strip()
            ct0 = subprocess.run(["pass", "show", "x-twitter/bird-ct0"], capture_output=True, text=True).stdout.strip()
        except:
            pass
    return auth_token, ct0

def check_boca_match_today():
    if FIXTURE_RELATIVE_PATH.startswith("/"):
        fixture_path = FIXTURE_RELATIVE_PATH
    else:
        fixture_path = os.path.join(BASE_DIR, FIXTURE_RELATIVE_PATH)
        
    legacy_path = "/home/pablo/.openclaw/alfred-workspace/memory/boca_fixture.json"
    if not os.path.exists(fixture_path) and os.path.exists(legacy_path):
        fixture_path = legacy_path

    if os.path.exists(fixture_path):
        with open(fixture_path, "r") as f:
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
            f"https://www.reddit.com/r/{REDDIT_SUB}/new.json?limit=15",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OperativoBocaBot/1.0"}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        target_thread_id = None
        target_title = ""
        
        for post in data['data']['children']:
            title = post['data']['title'].lower()
            if any(word in title for word in REDDIT_KEYWORDS):
                target_thread_id = post['data']['id']
                target_title = post['data']['title']
                break
                
        if not target_thread_id:
            req_hot = urllib.request.Request(
                f"https://www.reddit.com/r/{REDDIT_SUB}/hot.json?limit=5",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OperativoBocaBot/1.0"}
            )
            with urllib.request.urlopen(req_hot) as response_hot:
                data_hot = json.loads(response_hot.read().decode())
                for post in data_hot['data']['children']:
                    title = post['data']['title'].lower()
                    if any(word in title for word in REDDIT_KEYWORDS):
                        target_thread_id = post['data']['id']
                        target_title = post['data']['title']
                        break

        if not target_thread_id:
            return "", []

        req_comments = urllib.request.Request(
            f"https://www.reddit.com/r/{REDDIT_SUB}/comments/{target_thread_id}.json?sort=top",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OperativoBocaBot/1.0"}
        )
        with urllib.request.urlopen(req_comments) as response_comments:
            comments_data = json.loads(response_comments.read().decode())
            
        raw_comments = []
        top_highlights = []
        
        valid_comments = [
            c['data'] for c in comments_data[1]['data']['children'] 
            if c.get('kind') == 't1' and c['data'].get('body') and c['data'].get('body') not in ["[deleted]", "[removed]"] 
            and c['data'].get('author') != 'AutoModerator'
        ]
        
        for child in valid_comments[:15]:
            body = child.get('body').replace('\n', ' ')
            raw_comments.append(body)
            
        for child in sorted(valid_comments, key=lambda x: x.get('score', 0), reverse=True)[:3]:
            body = child.get('body').replace('\n', ' ')
            score = child.get('score', 0)
            author = child.get('author', 'anon')
            top_highlights.append(f"🔼 {score} pts | u/{author}: \"{body[:150]}{'...' if len(body)>150 else ''}\"")
                
        if not raw_comments:
            return f"(Thread '{target_title}' sin comentarios válidos)", []
            
        context_string = f"Thread Reddit (r/{REDDIT_SUB}): {target_title}\n" + "\n".join([f"- {c}" for c in raw_comments])
        return context_string, top_highlights
    except Exception as e:
        return f"(Error leyendo Reddit: {e})", []

def call_ollama(prompt):
    payload = {
        "model": "qwen3.5:9b",
        "prompt": prompt,
        "stream": False
    }
    
    try:
        req = urllib.request.Request(
            "http://192.168.1.22:11434/api/generate",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('response', '')
    except Exception as e:
        return f"Error conectando a Ollama Krillin: {e}"

def get_tweets_and_summarize():
    auth_token, ct0 = get_twitter_creds()
    all_tweets = []
    top_tweets_highlights = []
    
    if auth_token and ct0 and BOCA_ACCOUNTS:
        for account in BOCA_ACCOUNTS:
            try:
                result = subprocess.run([
                    "bird", 
                    "--auth-token", auth_token, 
                    "--ct0", ct0, 
                    "user-tweets", account, "--json"
                ], capture_output=True, text=True)
                
                tweets = json.loads(result.stdout)
                for t in tweets[:2]:
                    text = t.get('text', '').replace('\n', ' ')
                    views = t.get('views', 0)
                    all_tweets.append({"account": account, "text": text, "views": views})
            except Exception as e:
                continue
                
    if all_tweets:
        sorted_tweets = sorted(all_tweets, key=lambda x: x.get('views', 0) or 0, reverse=True)
        for t in sorted_tweets[:3]:
            top_tweets_highlights.append(f"🐦 @{t['account']}: \"{t['text'][:150]}{'...' if len(t['text'])>150 else ''}\"")
            
        tweets_text = "\n---\n".join([f"@{t['account']}: {t['text']}" for t in all_tweets])
    else:
        tweets_text = "(No se pudieron obtener tweets)"
    
    reddit_comments_raw, reddit_highlights = get_reddit_thread_comments()
    reddit_context = f"\n\nComentarios en Reddit:\n{reddit_comments_raw}" if reddit_comments_raw else ""
            
    if not all_tweets and not reddit_comments_raw:
        return "🔵🟡🔵 *Operativo Boca*: No pude recuperar datos de Twitter ni de Reddit."
        
    prompt = f"""Sos un analista deportivo monitoreando las redes sociales (Twitter y Reddit) durante un evento/partido. 
Armá un párrafo corto (3 o 4 líneas máximo) resumiendo el 'termómetro' general de los hinchas basándote en la siguiente data cruda extraída hace minutos. 
Destacá si hay enojo, festejos, ironía o críticas a jugadores/DT puntuales. 
Importante: No incluyas citas textuales en tu resumen ni listados, quiero solo el análisis en prosa rápida.

Data cruda:
{tweets_text}
{reddit_context}
"""
    
    resumen = call_ollama(prompt)
    
    final_message = f"🔵🟡🔵 **Termómetro del Partido** 🔵🟡🔵\n\n"
    final_message += f"📊 **Resumen General:**\n{resumen.strip()}\n\n"
    
    if top_tweets_highlights:
        final_message += "🗣️ **Destacados en X (Twitter):**\n"
        final_message += "\n".join(top_tweets_highlights) + "\n\n"
        
    if reddit_highlights:
        final_message += f"🔥 **Top Comentarios en r/{REDDIT_SUB}:**\n"
        final_message += "\n".join(reddit_highlights)
    
    return final_message.strip()

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
