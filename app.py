"""
PCOS Care AI - Render Deployment Version
Webhook-based Telegram Bot (FIXED)
"""

import os
import telebot
from telebot import types
from flask import Flask, request
import requests
from bs4 import BeautifulSoup

# ==========================================
# BOT INITIALIZATION
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://pcos-bot.onrender.com{WEBHOOK_PATH}"

user_data = {}

# ==========================================
# WEIGHTED SCORING SYSTEM
# ==========================================

WEIGHTS = {
    'cycle_regularity': {'Regular': 0, 'Irregular': 35, 'None': 40},
    'cycle_length': {'normal': 0, 'short': 15, 'long': 25, 'none': 30},
    'symptoms': {'Acne': 8, 'Facial Hair': 12, 'Weight Gain': 10, 'Hair Thinning': 10}
}

# ==========================================
# PCOS SCORER
# ==========================================

class PCOSScorer:
    @staticmethod
    def calculate_cycle_length_weight(length, regularity):
        if regularity == 'None':
            return WEIGHTS['cycle_length']['none']
        try:
            days = int(length)
            if 21 <= days <= 35:
                return 0
            elif days < 21:
                return 15
            else:
                return 25
        except:
            return 0

    @staticmethod
    def calculate_total_score(data):
        score = 0
        score += WEIGHTS['cycle_regularity'].get(data.get('cycle_regularity', 'Regular'), 0)
        score += PCOSScorer.calculate_cycle_length_weight(
            data.get('cycle_length', '28'),
            data.get('cycle_regularity', 'Regular')
        )
        for s in data.get('symptoms', []):
            score += WEIGHTS['symptoms'].get(s, 0)
        return min(score, 100)

    @staticmethod
    def get_risk_category(score):
        if score < 30:
            return "Low"
        elif score <= 70:
            return "Medium"
        else:
            return "High"

# ==========================================
# SAFE WEB SEARCH (OPTIONAL)
# ==========================================

HEADERS = {"User-Agent": "Mozilla/5.0"}

def web_search_pcos(topic):
    try:
        url = f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"
        res = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        for p in soup.select("p"):
            text = p.get_text().strip()
            if len(text) > 120:
                return text[:900] + "\n\n⚠️ Not medical advice."
    except:
        pass

    return (
        "PCOS is a hormonal disorder affecting reproductive-age women.\n\n"
        "Symptoms include irregular periods, acne, facial hair, and weight gain.\n\n"
        "⚠️ Not medical advice."
    )

# ==========================================
# BOT COMMANDS
# ==========================================

@bot.message_handler(commands=["start"])
def start(message):
    user_data[message.from_user.id] = {}
    bot.send_message(
        message.chat.id,
        "🌸 *Welcome to PCOS Care AI* 🌸\n\n"
        "/assess – PCOS risk assessment\n"
        "/about – About PCOS\n"
        "/help – Guidance\n\n"
        "Type /assess to begin.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["about"])
def about(message):
    bot.send_message(message.chat.id, web_search_pcos("Polycystic ovary syndrome"))

@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(message.chat.id, web_search_pcos("PCOS management"))

@bot.message_handler(commands=["assess"])
def assess(message):
    user_data[message.from_user.id] = {'stage': 'cycle'}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Regular", "Irregular", "None")
    bot.send_message(
        message.chat.id,
        "🩺 *Question 1/3:* Menstrual cycle?",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.from_user.id in user_data and "stage" in user_data[m.from_user.id])
def assessment_flow(message):
    uid = message.from_user.id
    stage = user_data[uid]["stage"]

    if stage == "cycle":
        user_data[uid]["cycle_regularity"] = message.text
        user_data[uid]["stage"] = "length"
        bot.send_message(message.chat.id, "Enter cycle length (days):")

    elif stage == "length":
        user_data[uid]["cycle_length"] = message.text
        user_data[uid]["stage"] = "symptoms"
        bot.send_message(message.chat.id, "Enter symptoms (comma-separated):")

    elif stage == "symptoms":
        user_data[uid]["symptoms"] = [s.strip() for s in message.text.split(",")]
        generate_report(message)

def generate_report(message):
    uid = message.from_user.id
    data = user_data[uid]
    score = PCOSScorer.calculate_total_score(data)
    risk = PCOSScorer.get_risk_category(score)

    bot.send_message(
        message.chat.id,
        f"📊 *PCOS Risk Report*\n\nScore: {score}%\nRisk: {risk}\n\n⚠️ Not a diagnosis.",
        parse_mode="Markdown"
    )
    user_data.pop(uid, None)

# ==========================================
# FLASK ROUTES (FIXED)
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return "PCOS Care AI Bot is running", 200


@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200
