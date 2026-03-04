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

# Cargar config
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
        print("⚠️ TELEGRAM_CHAT_ID no configurado. Solo imprimiendo en consola:")
        print(text)
        return

    cmd = [
        "openclaw", "message", "send",
        "--channel", "telegram",
        "--to", TELEGRAM_CHAT_ID,
        "--message", text
    ]
    subprocess.run(cmd, capture_output=True)

def get_twitter_creds():
    # 1. Intentar leer de variables de entorno (Estándar genérico)
    auth_token = os.environ.get("TWITTER_AUTH_TOKEN")
    ct0 = os.environ.get("TWITTER_CT0")
    
    # 2. Fallback al password manager local (Unix pass) para compatibilidad heredada
    if not auth_token or not ct0:
        try:
            auth_token = subprocess.run(["pass", "show", "x-twitter/bird"], capture_output=True, text=True).stdout.strip()
            ct0 = subprocess.run(["pass", "show", "x-twitter/bird-ct0"], capture_output=True, text=True).stdout.strip()
        except:
            pass
            
    return auth_token, ct0

def check_boca_match_today():
    # Si la ruta es absoluta, usarla, si no, resolver desde BASE_DIR
    if FIXTURE_RELATIVE_PATH.startswith("/"):
        fixture_path = FIXTURE_RELATIVE_PATH
    else:
        fixture_path = os.path.join(BASE_DIR, FIXTURE_RELATIVE_PATH)
        
    # Compatibilidad heredada para entorno local específico
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
    else:
        print(f"⚠️ Archivo de fixture no encontrado en {fixture_path}")
        
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
        
        # Buscar en new
        for post in data['data']['children']:
            title = post['data']['title'].lower()
            if any(word in title for word in REDDIT_KEYWORDS):
                target_thread_id = post['data']['id']
                target_title = post['data']['title']
                break
                
        # Fallback a hot
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
            return ""

        req_comments = urllib.request.Request(
            f"https://www.reddit.com/r/{REDDIT_SUB}/comments/{target_thread_id}.json?sort=new",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OperativoBocaBot/1.0"}
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
            
        return f"Thread Reddit (r/{REDDIT_SUB}): {target_title}\n" + "\n".join([f"- {c}" for c in comments])
    except Exception as e:
        return f"(Error leyendo Reddit: {e})"

def get_tweets_and_summarize():
    auth_token, ct0 = get_twitter_creds()
    all_tweets = []
    
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
                for t in tweets[:3]:
                    all_tweets.append(f"@{account}: {t.get('text', '')}")
            except Exception as e:
                continue
    
    tweets_text = "\n---\n".join(all_tweets) if all_tweets else "(No se pudieron obtener tweets. Verifica credenciales o lista de cuentas.)"
    
    reddit_comments = get_reddit_thread_comments()
    reddit_context = f"\n\nComentarios en Reddit:\n{reddit_comments}" if reddit_comments else ""
            
    if not all_tweets and not reddit_comments:
        return "🔵🟡🔵 *Operativo Boca*: No pude recuperar datos de Twitter ni de Reddit."
        
    prompt = f"""Estás monitoreando las redes (Twitter y Reddit) durante un evento/partido. 
Resume el 'termómetro' de los hinchas basándote en la siguiente data. 
Sé breve, tipo reporte de situación crudo y directo (máximo 5 líneas). Destaca calenturas, festejos, o críticas a jugadores/DT.

Tweets de referentes:
{tweets_text}
{reddit_context}
"""
    
    # Intenta ejecutar un modelo genérico en OpenClaw, idealmente configurado en defaults
    resumen = subprocess.run(["openclaw", "run", "--model", "default", "--prompt", prompt], capture_output=True, text=True).stdout
    if not resumen.strip():
        # Fallback si "default" falla
        resumen = subprocess.run(["openclaw", "run", "--model", "gemini-flash", "--prompt", prompt], capture_output=True, text=True).stdout
    
    return f"🔵🟡🔵 **Termómetro del Partido** 🔵🟡🔵\n\n{resumen.strip()}"

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
