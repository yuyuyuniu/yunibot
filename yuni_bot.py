#!/usr/bin/env python3
"""
Yuni Discord Bot - Thin client that connects to the Yuni Brain API.
Responds to all messages in configured channels + DMs.
Passes channel_id for 3-message conversation memory.
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

# Channel IDs where Yuni responds to ALL messages
ACTIVE_CHANNEL_IDS = {
    1500809803419750451,
}

# ── Discord Client Setup ───────────────────────────────────
intents = Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


async def call_yuni_brain(text: str, image_urls: list[str], username: str, channel_id: str) -> str:
    """Call the CodeWords Yuni Brain service and return the response."""
    payload = {
        "text": text,
        "images": image_urls,
        "username": username,
        "channel_id": channel_id,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CODEWORDS_API_KEY}",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            CODEWORDS_API_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
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
    print(f"  Random messages: OFF")
    print(f"  Memory: last 3 exchanges per channel")
    print(f"{'='*50}\n")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if message.author.bot:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_active_channel = message.channel.id in ACTIVE_CHANNEL_IDS

    if not is_dm and not is_active_channel:
        return

    text = message.content or ""
    image_urls = []
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            image_urls.append(attachment.url)

    if not text.strip() and not image_urls:
        return

    channel_id = str(message.author.id) if is_dm else str(message.channel.id)

    async with message.channel.typing():
        reply = await call_yuni_brain(
            text=text,
            image_urls=image_urls,
            username=message.author.display_name,
            channel_id=channel_id,
        )

    if reply:
        if len(reply) > 2000:
            reply = reply[:1997] + "..."
        await message.channel.send(reply)


if __name__ == "__main__":
    print("Starting Yuni Discord Bot...")
    client.run(BOT_TOKEN)
