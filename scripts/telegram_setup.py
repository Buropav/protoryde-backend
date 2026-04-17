import requests


def get_chat_id():
    print("Welcome to ProtoRyde Telegram Setup!")
    token = input("1. Enter your Telegram Bot Token from BotFather: ").strip()
    if not token:
        print("Token is required.")
        return

    print("Fetching updates...")
    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
    data = response.json()

    if data.get("ok") and len(data["result"]) > 0:
        chat_id = data["result"][0]["message"]["chat"]["id"]
        print(f"\n✅ SUCCESS! Found your Chat ID: {chat_id}\n")
        print("Add this to your .env file or environment variables:")
        print(f"TELEGRAM_BOT_TOKEN={token}")
        print(f"TELEGRAM_CHAT_ID={chat_id}")
    else:
        print(
            "\n❌ No messages found. Please send a message (like 'Hello') to your bot on Telegram and run this script again."
        )


if __name__ == "__main__":
    get_chat_id()
