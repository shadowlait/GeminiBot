import telebot
import html
import re
import os

from dotenv import load_dotenv
from google import genai
# from google.colab import userdata # Use userdata to access secrets

# Load environment variables from .env file
load_dotenv("bot_credentials.env")

# Get API keys from environment variables
gemini_key = os.getenv("GEMINI_API")
bot_token = os.getenv("BOT_TOKEN_KEY")

# Initialize Telegram Bot and Gemini Client
bot = telebot.TeleBot(bot_token)
client = genai.Client(api_key=gemini_key)

def format_text_for_telegram(text):
    """
    Format text for Telegram using only supported HTML tags.
    Telegram supports: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>, <a>, <code>, <pre>
    """
    # Escape HTML special characters first
    text = html.escape(text)

    # Convert markdown-like bold syntax to HTML bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

    # Convert numbered lists
    text = re.sub(r'^(\d+)\.\s+', r'<b>\1.</b> ', text, flags=re.MULTILINE)

    # Convert bullet points
    text = re.sub(r'^[\*\-]\s+', r'• ', text, flags=re.MULTILINE)

    # For line breaks, we'll use newline characters instead of <br> tags
    # Telegram will automatically handle newlines in HTML mode

    return text

@bot.message_handler(commands=["start"])
def handle_commands(message):
    """Handles the /start command and sends a welcome message."""
    greeting = "Welcome! Thanks for using the Gemini AI Bot\n\nStart by sending a query or question."
    bot.reply_to(message, greeting)

@bot.message_handler(func=lambda message: True)
def receive_message(message):
    """Receives user messages, sends to Gemini, and sends the response back."""
    # Send a "Generating Response..." message to the user
    sent_generating = None
    try:
        sent_generating = bot.send_message(message.chat.id, "⏳ Generating Response...")
    except Exception as e:
        print(f"Error sending generating message: {e}")
        # Continue without the generating message

    try:
        # Get response from Gemini model
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text
        )

        # Get the raw response text
        text = response.text

        # Format with Telegram-supported HTML tags only
        text = format_text_for_telegram(text)

        # Telegram has a limit of 4096 characters per message
        max_message_length = 4096

        # Try to delete the "Generating Response..." message if it exists
        if sent_generating:
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=sent_generating.message_id)
            except Exception as delete_error:
                print(f"Error deleting message (may already be deleted): {delete_error}")
                # It's okay if we can't delete it - just continue

        # Split and send messages if longer than max_message_length
        if len(text) > max_message_length:
            # Split by paragraphs to maintain readability
            paragraphs = text.split('\n\n')
            chunks = []
            current_chunk = ""

            for para in paragraphs:
                if len(current_chunk) + len(para) + 2 <= max_message_length:
                    current_chunk += para + '\n\n'
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = para + '\n\n'

            if current_chunk:
                chunks.append(current_chunk.strip())

            for chunk in chunks:
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode='HTML')
                except Exception as chunk_error:
                    print(f"Error sending chunk: {chunk_error}")
                    # If HTML fails, try sending as plain text
                    try:
                        plain_text = html.unescape(re.sub(r'<[^>]+>', '', chunk))
                        bot.send_message(message.chat.id, plain_text)
                    except Exception as fallback_error:
                        print(f"Error sending fallback text: {fallback_error}")
        else:
            try:
                bot.send_message(message.chat.id, text, parse_mode='HTML')
            except Exception as html_error:
                print(f"HTML parse error: {html_error}")
                # Fallback to plain text if HTML fails
                try:
                    plain_text = html.unescape(re.sub(r'<[^>]+>', '', text))
                    bot.send_message(message.chat.id, plain_text)
                except Exception as fallback_error:
                    print(f"Error sending fallback text: {fallback_error}")

    except Exception as e:
        # Handle any errors that might occur
        error_msg = f"❌ Sorry, an error occurred: {str(e)}"

        # Try to delete the generating message if it exists
        if sent_generating:
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=sent_generating.message_id)
            except Exception as delete_error:
                print(f"Error deleting message: {delete_error}")

        # Send error message without HTML formatting to avoid issues
        try:
            bot.send_message(message.chat.id, error_msg)
        except Exception as send_error:
            print(f"Error sending error message: {send_error}")

# Start the bot
print("Bot is running...")
bot.polling(none_stop=True)