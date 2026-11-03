"""One-time login via QR code (no confirmation code needed).

Run: python login_qr.py
Then on your phone: Telegram -> Settings -> Devices -> Link Desktop Device -> scan the QR.
After that scraper.py reuses the saved session.
"""
import asyncio
import getpass
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

load_dotenv()

SESSION = "collector_session"


def show_qr(url):
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
    except ImportError:
        print("Install 'qrcode' (pip install qrcode) to see the QR here,")
        print("or paste this link into any QR generator:")
    print(url)


async def main():
    client = TelegramClient(SESSION, int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Already logged in as {me.first_name} (@{me.username})")
        await client.disconnect()
        return

    qr = await client.qr_login()
    while True:
        print("\nScan with Telegram: Settings -> Devices -> Link Desktop Device\n")
        show_qr(qr.url)
        try:
            await qr.wait(timeout=60)
            break
        except asyncio.TimeoutError:
            print("QR expired, generating a new one...")
            await qr.recreate()
        except SessionPasswordNeededError:
            await client.sign_in(password=getpass.getpass("2FA password: "))
            break

    me = await client.get_me()
    print(f"Logged in as {me.first_name} (@{me.username}). Now run scraper.py")
    await client.disconnect()


asyncio.run(main())
