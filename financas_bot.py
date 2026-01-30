import telebot
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime, timedelta
import calendar
import matplotlib

matplotlib.use("Agg")  # Set backend for non-interactive environments
import matplotlib.pyplot as plt
import io

load_dotenv()

CHAVE_API = os.getenv("TELEGRAM_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

if not CHAVE_API:
    raise ValueError("TELEGRAM_TOKEN nao encontrado no .env!")

bot = telebot.TeleBot(CHAVE_API)

# MongoDB Setup
client = MongoClient(MONGO_URI)
db = client["financas_bot"]
users_collection = db["users"]
expenses_collection = db["expenses"]


@bot.message_handler(commands=["start", "ola"])
def ans_greeting(message):
    bot.reply_to(
        message,
        "🌟 Olá! Eu sou seu assistente financeiro pessoal.\n\n"
        "Vou te ajudar a manter suas contas em dia! Veja o que posso fazer:\n\n"
        "✅ /register - Comece por aqui para criar sua conta.\n"
        "💰 /add_expense - Registre um gasto. Ex: `/add_expense 25.50 Almoço Pix`\n"
        "   *(Se quiser colocar uma data diferente, use: /add_expense 25.50 Almoço 20-01-2026 Pix)*\n"
        "📊 /month_expenses - Veja seu resumo do mês. Ex: `/month_expenses 01 2026`\n"
        "🍕 /expenses_graphic - Veja um gráfico dos seus gastos.\n"
        "   Ex: `/expenses_graphic 1m` (último mês), `1w` (última semana), `1d` (hoje) ou `1y` (último ano).\n\n"
        "Como posso te ajudar hoje?",
    )


@bot.message_handler(commands=["register"])
def ans_register(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name

        if users_collection.find_one({"_id": user_id}):
            bot.reply_to(message, "Você já está registrado!")
        else:
            users_collection.insert_one(
                {
                    "_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "created_at": datetime.now(),
                }
            )
            bot.reply_to(message, "Registrado com sucesso!")
    except Exception as e:
        bot.reply_to(
            message,
            f"Erro ao registrar: {str(e)}\nVerifique as permissões do banco de dados.",
        )


@bot.message_handler(commands=["add_expense"])
def ans_add_expense(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 3:
            bot.reply_to(
                message,
                "⚠️ *Formato incorreto!*\n\n"
                "Para registrar um gasto hoje, use:\n"
                "`/add_expense valor categoria metodo_pagamento` \n"
                "Ex: `/add_expense 15.00 Cafe Dinheiro` \n\n"
                "Para registrar um gasto em outra data, use:\n"
                "`/add_expense valor categoria DD-MM-YYYY metodo_pagamento` \n"
                "Ex: `/add_expense 15.00 Cafe 20-01-2026 Dinheiro` \n\n"
                "💡 *Dica:* Se o nome da categoria ou do método tiver mais de uma palavra, não tem problema!",
                parse_mode="Markdown",
            )
            return

        # Parse amount handling Brazilian format (1.200,50) vs US format (1200.50)
        raw_amount = args[0]
        if "," in raw_amount:
            amount_str = raw_amount.replace(".", "").replace(",", ".")
        else:
            amount_str = raw_amount
            
        amount = float(amount_str)
        category = args[1].title()

        try:
            date_obj = datetime.strptime(args[2], "%d-%m-%Y")
            payment_method = " ".join(args[3:])
            if not payment_method:
                bot.reply_to(message, "Por favor, informe o método de pagamento.")
                return
        except ValueError:
            date_obj = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            payment_method = " ".join(args[2:])

        expense = {
            "user_id": message.from_user.id,
            "amount": amount,
            "category": category,
            "date": date_obj,
            "payment_method": payment_method,
            "created_at": datetime.now(),
        }

        expenses_collection.insert_one(expense)
        date_str = date_obj.strftime("%d-%m-%Y")
        bot.reply_to(
            message,
            f"Despesa adicionada: {payment_method} ({category}) - R$ {amount:.2f} em {date_str}",
        )

    except ValueError:
        bot.reply_to(
            message, "Valor inválido. Certifique-se de usar números para o valor."
        )
    except Exception as e:
        bot.reply_to(message, f"Ocorreu um erro: {str(e)}")


@bot.message_handler(commands=["month_expenses"])
def ans_month_expenses(message):
    try:
        args = message.text.split()[1:]
        if len(args) == 2:
            month = int(args[0])
            year = int(args[1])
        elif len(args) == 0:
            today = datetime.now()
            month = today.month
            year = today.year
        else:
            bot.reply_to(
                message,
                "Formato invalido. Por favor use o formato: mes ano `(Ex:.. 01 2026)` ou apenas digite o comando para receber do mes atual.",
                parse_mode="Markdown",
            )
            return

        if month < 1 or month > 12:
            bot.reply_to(message, "Mês inválido (1-12).")
            return

        start_date = datetime(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = datetime(year, month, last_day, 23, 59, 59)

        pipeline = [
            {
                "$match": {
                    "user_id": message.from_user.id,
                    "date": {"$gte": start_date, "$lte": end_date},
                }
            },
            {
                "$group": {
                    "_id": "$category",
                    "total": {"$sum": "$amount"},
                    "count": {"$sum": 1},
                }
            },
        ]

        results = list(expenses_collection.aggregate(pipeline))

        if not results:
            bot.reply_to(message, f"Nenhuma despesa encontrada para {month}/{year}.")
            return

        response = f"Despesas de {month}/{year}:\n\n"
        total_month = 0
        for item in results:
            category = item["_id"]
            total = item["total"]
            count = item["count"]
            response += f"📂 {category}: R$ {total:.2f} ({count} itens)\n"
            total_month += total

        response += f"\nTotal Geral: R$ {total_month:.2f}"
        bot.reply_to(message, response)

    except ValueError:
        bot.reply_to(message, "Mês ou ano inválidos. Use números inteiros.")
    except Exception as e:
        bot.reply_to(message, f"Erro ao buscar despesas: {str(e)}")


@bot.message_handler(commands=["expenses_graphic"])
def ans_expenses_graphic(message):
    try:
        args = message.text.split()[1:]
        period = args[0].lower() if args else "1m"  # Default to 1 month

        end_date = datetime.now()
        start_date = None
        period_name = ""

        if period == "1d":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            period_name = "Hoje"
        elif period == "1w":
            start_date = end_date - timedelta(days=7)
            period_name = "Últimos 7 dias"
        elif period == "1m":
            start_date = end_date - timedelta(days=30)
            period_name = "Últimos 30 dias"
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
            period_name = "Último Ano"
        else:
            bot.reply_to(
                message,
                "⚠️ Opção inválida. Use:\n"
                "`1d` (Hoje)\n"
                "`1w` (7 dias)\n"
                "`1m` (30 dias)\n"
                "`1y` (365 dias)",
                parse_mode="Markdown",
            )
            return

        pipeline = [
            {
                "$match": {
                    "user_id": message.from_user.id,
                    "date": {"$gte": start_date, "$lte": end_date},
                }
            },
            {
                "$group": {
                    "_id": "$category",
                    "total": {"$sum": "$amount"},
                }
            },
        ]

        results = list(expenses_collection.aggregate(pipeline))

        if not results:
            bot.reply_to(message, f"Nenhuma despesa encontrada para: {period_name}.")
            return

        categories = [item["_id"] for item in results]
        totals = [item["total"] for item in results]

        plt.figure(figsize=(8, 6))
        plt.pie(totals, labels=categories, autopct="%1.1f%%", startangle=140)
        plt.title(f"Gastos - {period_name}")
        plt.axis("equal")

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close()

        bot.send_photo(
            message.chat.id, buf, caption=f"Gráfico de despesas: {period_name}"
        )

    except Exception as e:
        bot.reply_to(message, f"Erro ao gerar gráfico: {str(e)}")


def setup_bot_info():
    """Configura a descrição e os comandos do bot no Telegram."""
    try:
        # Descrição (O que aparece na tela 'O que este bot pode fazer?')
        bot.set_my_description(
            "🌟 Bem-vindo ao Finanças Bot!\n\n"
            "Eu sou seu assistente pessoal para controle financeiro. "
            "Comigo você pode registrar seus gastos diários, organizar por categorias "
            "e visualizar relatórios mensais."
        )
    except Exception as e:
        print(f"Erro ao configurar info do bot: {e}")


if __name__ == "__main__":
    setup_bot_info()
    bot.polling()
