#!/usr/bin/env python3
"""
Yuni Discord Bot - Thin client that connects to the Yuni Brain API.
Responds to all messages in configured channels + DMs.

Setup:
1. pip install discord.py aiohttp
2. Set environment variables:
   - DISCORD_BOT_TOKEN: Your Discord bot token
   - CODEWORDS_API_KEY: Your CodeWords API key  
3. python yuni_bot.py
"""

import os
import asyncio
import aiohttp
import discord
from discord import Intents

# ── Configuration ──────────────────────────────────────────
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CODEWORDS_API_KEY = os.environ["CODEWORDS_API_KEY"]
YUNI_SERVICE_ID = "yuni_discord_brain_35beac2f"
CODEWORDS_API_URL = f"https://runtime.codewords.ai/run/{YUNI_SERVICE_ID}"

# Channel IDs where Yuni responds to ALL messages (add more as needed)
ACTIVE_CHANNEL_IDS = {
    1500809803419750451,
}

# ── Discord Client Setup ───────────────────────────────────
intents = Intents.default()
intents.message_content = True  # Required to read message content
client = discord.Client(intents=intents)


async def call_yuni_brain(text: str, image_urls: list[str], username: str) -> str:
    """Call the CodeWords Yuni Brain service and return the response."""
    payload = {
        "text": text,
        "images": image_urls,
        "username": username,
    }
    headers = {
        "Content-Type": "application/json",
        "x-codewords-api-key": CODEWORDS_API_KEY,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(CODEWORDS_API_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("reply", "...")
            else:
                error_text = await resp.text()
                print(f"[ERROR] Yuni Brain returned {resp.status}: {error_text}")
                return None


@client.event
async def on_ready():
    print(f"\n{'='*50}")
    print(f"  Yuni is online as {client.user}")
    print(f"  Active channels: {ACTIVE_CHANNEL_IDS}")
    print(f"  DMs: enabled")
    print(f"{'='*50}\n")


@client.event
async def on_message(message: discord.Message):
    # Never respond to self
    if message.author == client.user:
        return

    # Ignore other bots
    if message.author.bot:
        return

    # Check if this is a DM or an active channel
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_active_channel = message.channel.id in ACTIVE_CHANNEL_IDS

    if not is_dm and not is_active_channel:
        return

    # Extract text content
    text = message.content or ""

    # Extract image URLs from attachments
    image_urls = []
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            image_urls.append(attachment.url)

    # Skip if no content at all
    if not text.strip() and not image_urls:
        return

    # Show typing indicator while processing
    async with message.channel.typing():
        reply = await call_yuni_brain(
            text=text,
            image_urls=image_urls,
            username=message.author.display_name,
        )

    if reply:
        # Discord has a 2000 char limit
        if len(reply) > 2000:
            reply = reply[:1997] + "..."
        await message.channel.send(reply)


# ── Run ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting Yuni Discord Bot...")
    client.run(BOT_TOKEN)
