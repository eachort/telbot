import random
import time
import datetime
import pytz
import telegram
import sqlite3
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update

# replace YOUR_API_TOKEN with your actual API token from BotFather
API_TOKEN = 'YOUR_API_TOKEN'

# set up the time zone
timezone = pytz.timezone('Europe/Paris')

# set up the pause flag and pause time
is_paused = False
pause_time = None

# define the function to send a random message
def send_random_message(context):
    global is_paused, pause_time
    if is_paused:
        if datetime.datetime.now().replace(tzinfo=timezone) >= pause_time:
            is_paused = False
            pause_time = None
        else:
            return
    message = random.choice(messages)
    context.bot.send_message(chat_id='YOUR_CHAT_ID', text=message)

# define the /start command handler
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text='Привет, я бот для регулярных напоминаний')

# define the /add command handler
def add(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Please send me your message.")
    context.chat_data['waiting_for_message'] = True

def add_message(update: Update, context: CallbackContext):
    """Add a message to the database."""
    update.message.reply_text("Please enter your message to be added:")
    context.user_data["adding_message"] = True

def save_message(update: Update, context: CallbackContext):
    """Save the message to the database."""
    message_text = update.message.text
    with sqlite3.connect('messages.db') as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (message) VALUES (?)", (message_text,))
        conn.commit()
    context.user_data["adding_message"] = False
    update.message.reply_text(f"Message '{message_text}' has been added to the array.")

# define the /show command handler
def show(update, context):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('SELECT message_text FROM messages')
    messages = c.fetchall()
    num_messages = len(messages)
    message_list = "\n".join([f"{i+1}. {message[0]}" for i, message in enumerate(messages)])
    message = f"There are {num_messages} messages in the list:\n{message_list}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)
    conn.close()

# define the /del command handler
def delete(update, context):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('SELECT message_text FROM messages')
    messages = c.fetchall()
    num_messages = len(messages)
    message_list = "\n".join([f"{i+1}. {message[0]}" for i, message in enumerate(messages)])
    message = f"Which message do you want to delete? Here is the list:\n{message_list}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)
    context.chat_data['waiting_for_message'] = True
    conn.close()

def handle_message(update, context):
    message_text = update.message.text
    if context.chat_data.get('waiting_for_message'):
        context.chat_data['waiting_for_message'] = False
        num_messages = len(context.chat_data['messages'])
        if message_text.isdigit() and int(message_text) <= num_messages:
            message_index = int(message_text) - 1
            del context.chat_data['messages'][message_index]
            conn = sqlite3.connect('messages.db')
            c = conn.cursor()
            c.execute('DELETE FROM messages WHERE message_id = ?', (message_index+1,))
            conn.commit()
            conn.close()
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Message #{message_index+1} has been deleted.")
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Invalid input. Please enter a number between 1 and {num_messages}.")
    elif message_text.lower() == 'stop':
        context.bot.send_message(chat_id=update.effective_chat.id, text="Stopping the bot.")
        updater.stop()
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=random.choice(messages))

# set up the updater and dispatcher
updater = Updater(API_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# set up the command handlers
start_handler = CommandHandler('start', start)
add_handler = CommandHandler('add', add)
pause_handler = CommandHandler('pause', pause)
show_handler = CommandHandler('show', show)
del_handler = CommandHandler('del', delete)

dispatcher.add_handler(start_handler)
dispatcher.add_handler(add_handler)
dispatcher.add_handler(pause_handler)
dispatcher.add_handler(show_handler)
dispatcher.add_handler(del_handler)

# set up the job queue
job_queue = updater.job_queue
job_queue.run_daily(send_random_message, time=datetime.time(hour=random.randint(9, 21), minute=random.randint(0, 59), tzinfo=timezone))

# start the bot
updater.start_polling()
updater.idle()
