"""
PCOS Care AI - Render Deployment Version
Webhook-based Telegram Bot
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

BOT_TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)
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
# WEB SEARCH WITH FALLBACK
# ==========================================

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def web_search_pcos(topic):
    try:
        url = f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"
        res = requests.get(url, headers=HEADERS, timeout=5)

        if res.status_code != 200:
            raise Exception("Blocked")

        soup = BeautifulSoup(res.text, "html.parser")
        for p in soup.select("p"):
            text = p.get_text().strip()
            if len(text) > 120:
                return text[:900] + "\n\n⚠️ This is general information, not medical advice."
        raise Exception("No content")

    except:
        return (
            "Polycystic Ovary Syndrome (PCOS) is a hormonal disorder common among women "
            "of reproductive age. It involves irregular periods, excess androgen levels, "
            "and metabolic challenges.\n\n"
            "Common symptoms include acne, facial hair, weight gain, and hair thinning.\n\n"
            "Lifestyle management and medical consultation are recommended.\n\n"
            "⚠️ This is general information, not medical advice."
        )

# ==========================================
# BOT COMMANDS
# ==========================================

@bot.message_handler(commands=['start'])
def start(message):
    user_data[message.from_user.id] = {}
    bot.send_message(
        message.chat.id,
        "🌸 *Welcome to PCOS Care AI* 🌸\n\n"
        "/assess – PCOS risk assessment\n"
        "/about – About PCOS\n"
        "/help – PCOS guidance\n\n"
        "Type /assess to begin.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['about'])
def about(message):
    bot.send_message(message.chat.id, "🔍 Fetching PCOS information...")
    info = web_search_pcos("Polycystic ovary syndrome")
    bot.send_message(message.chat.id, f"🔬 *About PCOS*\n\n{info}", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.send_message(message.chat.id, "🔍 Fetching PCOS guidance...")
    info = web_search_pcos("Polycystic ovary syndrome management")
    bot.send_message(message.chat.id, f"📚 *PCOS Help & Guidance*\n\n{info}", parse_mode="Markdown")

@bot.message_handler(commands=['assess'])
def assess(message):
    user_data[message.from_user.id] = {'stage': 'cycle'}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add('Regular', 'Irregular', 'None')
    bot.send_message(
        message.chat.id,
        "🩺 *Question 1/3:* How is your menstrual cycle?",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.from_user.id in user_data and 'stage' in user_data[m.from_user.id])
def assessment_flow(message):
    uid = message.from_user.id
    stage = user_data[uid]['stage']

    if stage == 'cycle':
        user_data[uid]['cycle_regularity'] = message.text
        user_data[uid]['stage'] = 'length'
        bot.send_message(message.chat.id, "🩺 *Question 2/3:* Enter cycle length (days):")

    elif stage == 'length':
        user_data[uid]['cycle_length'] = message.text
        user_data[uid]['stage'] = 'symptoms'
        bot.send_message(
            message.chat.id,
            "🩺 *Question 3/3:* Enter symptoms separated by commas:\nAcne, Facial Hair, Weight Gain, Hair Thinning"
        )

    elif stage == 'symptoms':
        user_data[uid]['symptoms'] = [s.strip() for s in message.text.split(',')]
        generate_report(message)

def generate_report(message):
    uid = message.from_user.id
    data = user_data[uid]

    score = PCOSScorer.calculate_total_score(data)
    risk = PCOSScorer.get_risk_category(score)

    report = f"""
📊 *PCOS RISK REPORT*
━━━━━━━━━━━━━━━━━━
Risk Score: {score}%
Category: {risk}

⚠️ This is not a medical diagnosis.
"""
    bot.send_message(message.chat.id, report, parse_mode="Markdown")
    user_data.pop(uid, None)

@bot.message_handler(func=lambda m: True)
def general_questions(message):
    keywords = ["pcos", "period", "cycle", "hormone", "ovary", "acne", "fertility"]
    if any(k in message.text.lower() for k in keywords):
        bot.send_message(message.chat.id, "🔍 Searching trusted sources...")
        info = web_search_pcos(message.text)
        bot.send_message(message.chat.id, f"🩺 *General Information*\n\n{info}", parse_mode="Markdown")
    else:
        bot.send_message(
            message.chat.id,
            "❓ Ask me anything related to PCOS, symptoms, causes, or lifestyle management."
        )

# ==========================================
# FLASK WEBHOOK FOR RENDER
# ==========================================

@app.route('/', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/', methods=['GET'])
def home():
    return "PCOS Care AI Bot is running!", 200
