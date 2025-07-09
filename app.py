from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
import os
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot=bot, update_queue=None, use_context=True)
scheduler = BackgroundScheduler()

# Komento /start
def start(update, context):
    update.message.reply_text("Botti on päällä ja toimii!")

dispatcher.add_handler(CommandHandler("start", start))

# Tallennetaan edelliset kertoimet muistiin (yksinkertainen muisti)
previous_odds = {}

# Tarkistetaan OddsAPI:n kertoimia ja muutoksia
def check_odds():
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?regions=eu&markets=h2h&oddsFormat=decimal"
    params = {"apiKey": ODDS_API_KEY}

    try:
        response = requests.get(url, params=params)
        data = response.json()
        for event in data:
            teams = event.get("teams", [])
            if len(teams) < 2:
                continue
            home, away = teams
            bookmakers = event.get("bookmakers", [])
            if not bookmakers:
                continue

            outcome = bookmakers[0]["markets"][0]["outcomes"]
            odds_map = {o["name"]: o["price"] for o in outcome}

            if home not in odds_map or away not in odds_map:
                continue

            key = f"{home} vs {away}"
            old = previous_odds.get(key, {"home": odds_map[home], "away": odds_map[away]})

            change_home = ((odds_map[home] - old["home"]) / old["home"]) * 100
            change_away = ((odds_map[away] - old["away"]) / old["away"]) * 100

            if abs(change_home) >= 15 or abs(change_away) >= 15:
                viesti = f"\u26a1️ *Kerroinmuutos!*\nOttelu: {home} vs {away}"
                if abs(change_home) >= 15:
                    viesti += f"\n{home}: {old['home']} → {odds_map[home]} ({change_home:+.1f}%)"
                if abs(change_away) >= 15:
                    viesti += f"\n{away}: {old['away']} → {odds_map[away]} ({change_away:+.1f}%)"

                bot.send_message(chat_id=CHAT_ID, text=viesti, parse_mode="Markdown")

            previous_odds[key] = {"home": odds_map[home], "away": odds_map[away]}

    except Exception as e:
        print("Virhe OddsAPI-haussa:", e)

# Tarkistetaan NewsAPI:lla jalkapallouutiset
def check_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "football OR soccer",
        "language": "en",
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
        "pageSize": 5
    }

    try:
        response = requests.get(url, params=params)
        articles = response.json().get("articles", [])
        for article in articles:
            title = article.get("title")
            url = article.get("url")
            published_at = article.get("publishedAt")
            viesti = f"\ud83d\udcf0 *Uutinen:* {title}\n{url}\nJulkaistu: {published_at}"
            bot.send_message(chat_id=CHAT_ID, text=viesti, parse_mode="Markdown")
    except Exception as e:
        print("Virhe NewsAPI-haussa:", e)

# Webhook route
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK", 200

# Health check
@app.route("/")
def index():
    return "Botti toimii!", 200

# Käynnistetään ajastettu taustatoiminto
scheduler.add_job(check_odds, "interval", minutes=10)
scheduler.add_job(check_news, "interval", minutes=30)
scheduler.start()

if __name__ == "__main__":
    app.run(port=5000)
