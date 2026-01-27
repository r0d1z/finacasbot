import telebot
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
import calendar

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
        "📊 /month_expenses - Veja seu resumo do mês. Ex: `/month_expenses 01 2026`\n\n"
        "Como posso te ajudar hoje?"
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
        bot.reply_to(message, f"Erro ao registrar: {str(e)}\nVerifique as permissões do banco de dados.")


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
                parse_mode="Markdown"
            )
            return

        amount = float(args[0].replace(",", "."))
        category = args[1]

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
        if len(args) != 2:
            bot.reply_to(message, "Formato inválido. Use: /month_expenses <MM> <YYYY>")
            return

        month = int(args[0])
        year = int(args[1])

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


def setup_bot_info():
    """Configura a descrição e os comandos do bot no Telegram."""
    try:
        # Descrição (O que aparece na tela 'O que este bot pode fazer?')
        bot.set_my_description(
            "🌟 Bem-vindo ao Finanças Bot!\n\n"
            "Eu sou seu assistente pessoal para controle financeiro. "
            "Comigo você pode registrar seus gastos diários, organizar por categorias "
            "e visualizar relatórios mensais.\n\n"
            "Clique em /start para começar a organizar sua vida financeira!"
        )

        # Descrição Curta (O que aparece no perfil do bot e links de compartilhamento)
        bot.set_my_short_description("Seu assistente pessoal de controle financeiro 💰")

        # Menu de Comandos (Botão Menu azul no canto inferior esquerdo)
        bot.set_my_commands([
            telebot.types.BotCommand("/start", "Iniciar o bot e ver instruções"),
            telebot.types.BotCommand("/register", "Criar sua conta"),
            telebot.types.BotCommand("/add_expense", "Adicionar nova despesa"),
            telebot.types.BotCommand("/month_expenses", "Ver resumo do mês")
        ])
        print("Informações do bot atualizadas com sucesso!")
    except Exception as e:
        print(f"Erro ao atualizar informações do bot: {e}")


print("Bot está rodando...")
setup_bot_info()
bot.polling()

