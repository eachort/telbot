import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import sqlite3
import random
import datetime
import threading
from telegram import Update


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a thread-local storage to hold the database connection
db_local = threading.local()

def get_db_connection():
    # Check if the current thread already has a database connection
    if not hasattr(db_local, 'conn') or db_local.conn is None or not hasattr(db_local.conn, 'closed') or db_local.conn.closed:
        # If not, create a new connection and store it in the thread-local storage
        db_local.conn = sqlite3.connect('my_telegram_bot.db')

    # Return the connection
    return db_local.conn


def handle_message(update, context):
    user_id = update.message.from_user.id

    # Get the database connection from the thread-local storage
    conn = get_db_connection()

    # Use the connection to execute the database query
    c = conn.cursor()
    c.execute("SELECT pause_time FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()

    # Close the database cursor
    c.close()

    # Send the response message
    if result is None:
        context.bot.send_message(chat_id=update.effective_chat.id, text="You are not registered yet. Please use the /start command to register.")
        return
    else:
        pause_time = result[0]
        if pause_time is None:
            context.bot.send_message(chat_id=update.effective_chat.id, text="Your bot is active.")
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="Your bot is paused until {}.".format(pause_time))

    # Check if the user is paused
    if pause_time is not None and datetime.datetime.now() < pause_time:
        # The user is paused, so don't send any messages
        return

    # Use the connection to execute the database query
    c = conn.cursor()
    c.execute("SELECT messages FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()

    # Close the database cursor
    c.close()

    # If the result is None, send a message indicating that there are no messages
    if result is None:
        context.bot.send_message(chat_id=update.effective_chat.id, text="You have no messages.")
        return

    # If there are messages, send them as a numbered list
    messages = result[0].split(';')
    if len(messages) == 0:
        context.bot.send_message(chat_id=update.effective_chat.id, text="You have no messages.")
        return

    numbered_messages = '\n'.join(['{}. {}'.format(i+1, message) for i, message in enumerate(messages)])
    context.bot.send_message(chat_id=update.effective_chat.id, text=numbered_messages)

    # Commit any changes to the database and close the connection
    conn.commit()
    conn.close()



def start_bot():
    updater = Updater(token="", use_context=True)
    dp = updater.dispatcher

    # Add handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("add", add_message, pass_args=True))
    dp.add_handler(CommandHandler("show", show_messages))
    dp.add_handler(CommandHandler("del", delete_message))
    dp.add_handler(CommandHandler("pause", pause_bot))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the bot
    updater.start_polling()
    updater.idle()


def start(update, context):
    # Get the user ID from the message
    user_id = update.message.from_user.id

    # Get the database connection
    conn = get_db_connection()
    c = conn.cursor()

    # Check if the user is already registered
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()

    if result is not None:
        # User is already registered, update the registration time
        c.execute("UPDATE users SET registration_time=? WHERE user_id=?", (datetime.datetime.now(), user_id))
        conn.commit()

        # Send welcome back message
        context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome back!")

    else:
        # User is not yet registered, insert a new row into the users table
        c.execute("INSERT INTO users (user_id, registration_time) VALUES (?, ?)", (user_id, datetime.datetime.now()))
        conn.commit()

        # Send welcome message
        context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome to the reminder bot! Use the /add command to add a new message to your reminders.")

    # Close the database cursor and connection
    c.close()
    conn.close()


def help_command(update, context):
    """Send a message when the /help command is issued."""
    update.message.reply_text('Helpful message here.')

def add_message(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter your message:")
    user_id = update.message.from_user.id

    def save_message(update: Update, context: CallbackContext):
        message = update.message.text
        user_id = update.message.from_user.id

        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT messages FROM users WHERE user_id=?", (user_id,))
        result = c.fetchone()

        if result is None:
            messages = []
        else:
            messages = result[0].split(';')

        messages.append(message)
        c.execute("REPLACE INTO users (user_id, messages) VALUES (?, ?)", (user_id, ';'.join(messages)))
        conn.commit()

        context.bot.send_message(chat_id=update.effective_chat.id, text="Your message has been added.")

        # Close the connection
        conn.close()


    # Add a message handler for the user's response
    message_handler = MessageHandler(Filters.text & ~Filters.command, save_message)
    context.dispatcher.add_handler(message_handler)


def show_messages(update, context):
    user_id = update.message.from_user.id

    # Get the database connection from the thread-local storage
    conn = get_db_connection()

    # Use the connection to execute the database query
    c = conn.cursor()
    c.execute("SELECT messages FROM users WHERE user_id=?", (user_id,))

    # Fetch the result and close the cursor
    result = c.fetchone()
    c.close()

    # If the result is None, send a message indicating that there are no messages
    if result is None:
        context.bot.send_message(chat_id=update.effective_chat.id, text="You have no messages.")
        return

    # If there are messages, split them and send each one in a separate message
    messages_str = result[0]
    if messages_str:
        messages = messages_str.split(';')
        for message in messages:
            context.bot.send_message(chat_id=update.effective_chat.id, text=message)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="You have no messages.")


def delete_message(update, context, dp):
    user_id = update.message.from_user.id

    def send_message_list(messages):
        message_list = "\n".join([f"{i}. {msg}" for i, msg in enumerate(messages, start=1)])
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Please select the number of the message you want to delete:\n{message_list}")

    def delete_selected_message(selected_index):
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT messages FROM users WHERE user_id=?", (user_id,))
        result = c.fetchone()

        if result is None:
            messages = []
        else:
            messages = result[0].split(';')

        if not messages:
            context.bot.send_message(chat_id=update.effective_chat.id, text="You have no messages.")
            return

        if selected_index < 1 or selected_index > len(messages):
            context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid message number.")
            return

        del messages[selected_index - 1]
        c.execute("REPLACE INTO users (user_id, messages) VALUES (?, ?)", (user_id, ';'.join(messages)))
        conn.commit()

        context.bot.send_message(chat_id=update.effective_chat.id, text="The message has been deleted.")

        # Close the connection
        conn.close()

        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT messages FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    if result is None:
        messages = []
    else:
        messages = result[0].split(';')

    # Close the connection
    conn.close()

    if not messages:
        context.bot.send_message(chat_id=update.effective_chat.id, text="You have no messages.")
    elif len(messages) == 1:
        delete_selected_message(1)
    else:
        send_message_list(messages)

        # Add a message handler for the user's response
        selected_index_handler = MessageHandler(Filters.regex(r'^\d+$'), delete_selected_message)
        dp.add_handler(selected_index_handler)


def pause_bot(update, context):
    user_id = update.message.from_user.id

    conn = get_db_connection()
    c = conn.cursor()

    c.execute("UPDATE users SET paused_until=? WHERE user_id=?", (datetime.now() + timedelta(days=2), user_id))
    conn.commit()

    # Close the connection
    conn.close()

    context.bot.send_message(chat_id=update.effective_chat.id, text="The bot has been paused for 2 days.")


if __name__ == '__main__':
    start_bot()

