import telebot
import os
from dotenv import load_dotenv

load_dotenv()

CHAVE_API = os.getenv("TELEGRAM_TOKEN")

if not CHAVE_API:
    raise ValueError("token nao encontrado!")

bot = telebot.TeleBot(CHAVE_API)


@bot.message_handler(commands=["start", "ola"])
def ans_greeting(message):
    bot.reply_to(
        message, "Ola! bem vindo ao seu registrados de financas, como posso ajudar?"
    )


print("Bot est'a rodando...")
bot.polling()
