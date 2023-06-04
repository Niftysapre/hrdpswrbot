import telebot
from telebot import types
import sqlite3
import random
import string
import threading


TOKEN = None

with open("token.txt") as f:
    TOKEN = f.read().strip()

bot = telebot.TeleBot(TOKEN)

conn = None
cursor = None
db_lock = threading.Lock()

def get_database_name(chat_id):
    return f"passwords_{chat_id}.db"

def connect_to_database(chat_id):
    db_name = get_database_name(chat_id)
    conn = sqlite3.connect(db_name, check_same_thread=False)
    cursor = conn.cursor()
    return conn, cursor

def generate_password():
    length = random.randint(8, 12)
    chars = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(chars) for _ in range(length))
    return password


@bot.message_handler(commands=['start'])
def start_start(message):
    chat_id = message.chat.id
    conn, cursor = connect_to_database(chat_id)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            password TEXT
        )
    ''')
    conn.commit()

    menu_markup = types.ReplyKeyboardMarkup(row_width=2)
    generate_button = types.KeyboardButton('/generate')
    view_button = types.KeyboardButton('/view')
    menu_markup.add(generate_button, view_button)

    bot.reply_to(message, "Привет! Я бот для генерации и управления паролями.", reply_markup=menu_markup)


@bot.message_handler(commands=['generate'])
def generate_generate(message):
    global conn, cursor

    chat_id = message.chat.id
    conn, cursor = connect_to_database(chat_id)

    password = generate_password()
    bot.reply_to(message, f"Сгенерированный пароль: {password}")

    save_button = types.InlineKeyboardButton("Сохранить", callback_data=f"save:{password}")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(save_button)

    msg = bot.send_message(message.chat.id, "Действия с паролем:", reply_markup=keyboard)


@bot.message_handler(commands=['view'])
def view_view(message):
    cursor.execute('SELECT id, password FROM passwords')
    rows = cursor.fetchall()
    if rows:
        passwords = []
        for row in rows:
            password_id, password = row
            passwords.append(f"{password_id}. {password}")
        keyboard = types.InlineKeyboardMarkup()
        delete_button = types.InlineKeyboardButton("Удалить пароль", callback_data="delete")
        keyboard.row(delete_button)

        bot.reply_to(message, "\n".join(passwords), reply_markup=keyboard)
    else:
        bot.reply_to(message, "Нет сохраненных паролей")


@bot.callback_query_handler(func=lambda call: True)
def save_save(call):
    global conn, cursor

    chat_id = call.message.chat.id
    conn, cursor = connect_to_database(chat_id)

    if call.message:
        if call.data.startswith('save:'):
            password = call.data.split(':')[1]
            cursor.execute('INSERT INTO passwords (password) VALUES (?)', (password,))
            conn.commit()
            bot.answer_callback_query(call.id, text="Пароль сохранен")
            cursor.execute('SELECT id, password FROM passwords')
            rows = cursor.fetchall()


            for i, row in enumerate(rows, start=1):
                password_id, password = row
                cursor.execute('UPDATE passwords SET id = ? WHERE password = ?', (i, password))
                conn.commit()


            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)

        elif call.data == 'delete':
            bot.send_message(call.message.chat.id, "Введите ID пароля для удаления или 'все' для удаления всех паролей")
            bot.register_next_step_handler(call.message, delete_delete)

def delete_delete(message):
    chat_id = message.chat.id
    if message.text == 'все':
        with db_lock:
            cursor.execute('DELETE FROM passwords')
            conn.commit()
        bot.send_message(chat_id, "Все пароли удалены")
    else:
        try:
            password_id = int(message.text)
            with db_lock:
                cursor.execute('DELETE FROM passwords WHERE id = ?', (password_id,))
                conn.commit()


                cursor.execute('SELECT id, password FROM passwords')
                rows = cursor.fetchall()


                for i, row in enumerate(rows, start=1):
                    password_id, password = row
                    cursor.execute('UPDATE passwords SET id = ? WHERE password = ?', (i, password))
                    conn.commit()

            bot.send_message(chat_id, f"Пароль с ID {password_id} удален")
        except ValueError:
            bot.send_message(chat_id, "Неверный формат. Введите ID пароля или 'все'")


bot.polling()
