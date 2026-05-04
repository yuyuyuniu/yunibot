#!/usr/bin/env python3
"""
Yuni Discord Bot - Thin client that connects to the Yuni Brain API.
Responds to all messages in configured channels + DMs.
Sends 3 random messages per day between 9:00-23:00.
"""

import os
import random
import asyncio
import aiohttp
import discord
from discord import Intents
from datetime import datetime, time, timedelta

# ── Configuration ──────────────────────────────────────────
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CODEWORDS_API_KEY = os.environ["CODEWORDS_API_KEY"]
YUNI_SERVICE_ID = "yuni_discord_brain_35beac2f"
CODEWORDS_API_URL = f"https://runtime.codewords.ai/run/{YUNI_SERVICE_ID}"

# Channel IDs where Yuni responds to ALL messages (add more as needed)
ACTIVE_CHANNEL_IDS = {
    1500809803419750451,
}

# Random message settings
RANDOM_MESSAGES_PER_DAY = 3
QUIET_START_HOUR = 23  # no messages after 23:00
QUIET_END_HOUR = 9     # no messages before 9:00
# The bot uses the server's system time. Railway default is UTC.
# Set TZ=Etc/GMT-3 in Railway env vars if your timezone is UTC+3.

# ── Discord Client Setup ───────────────────────────────────
intents = Intents.default()
intents.message_content = True
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


async def get_random_thought() -> str:
    """Get a random unprompted thought from Yuni."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CODEWORDS_API_KEY}",
    }

    url = f"{CODEWORDS_API_URL}/random-thought"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("reply", None)
            else:
                error_text = await resp.text()
                print(f"[ERROR] Random thought failed {resp.status}: {error_text}")
                return None


def pick_random_times(count: int) -> list[time]:
    """Pick random times between QUIET_END_HOUR and QUIET_START_HOUR."""
    times = []
    for _ in range(count):
        hour = random.randint(QUIET_END_HOUR, QUIET_START_HOUR - 1)
        minute = random.randint(0, 59)
        times.append(time(hour, minute))
    return sorted(times)


async def random_message_scheduler():
    """Background task: send random Yuni messages at random times each day."""
    await client.wait_until_ready()
    print("[SCHEDULER] Random message scheduler started")

    while not client.is_closed():
        # Pick today's random times
        today_times = pick_random_times(RANDOM_MESSAGES_PER_DAY)
        print(f"[SCHEDULER] Today's random message times: {[t.strftime('%H:%M') for t in today_times]}")

        for scheduled_time in today_times:
            now = datetime.now()
            target = datetime.combine(now.date(), scheduled_time)

            # If time already passed today, skip it
            if target <= now:
                continue

            # Wait until the scheduled time
            wait_seconds = (target - now).total_seconds()
            print(f"[SCHEDULER] Next random message at {scheduled_time.strftime('%H:%M')} (in {wait_seconds/60:.0f} min)")

            await asyncio.sleep(wait_seconds)

            # Send random thought to a random active channel
            thought = await get_random_thought()
            if thought:
                for channel_id in ACTIVE_CHANNEL_IDS:
                    channel = client.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.send(thought)
                            print(f"[SCHEDULER] Sent random message to #{channel.name}: {thought[:50]}...")
                        except Exception as e:
                            print(f"[SCHEDULER] Failed to send to #{channel_id}: {e}")
                        break  # Send to first available channel only

        # Sleep until next day at QUIET_END_HOUR
        now = datetime.now()
        tomorrow_start = datetime.combine(
            now.date() + timedelta(days=1), time(QUIET_END_HOUR, 0)
        )
        sleep_until_tomorrow = (tomorrow_start - now).total_seconds()
        if sleep_until_tomorrow > 0:
            print(f"[SCHEDULER] Done for today. Sleeping until tomorrow {QUIET_END_HOUR}:00")
            await asyncio.sleep(sleep_until_tomorrow)


@client.event
async def on_ready():
    print(f"\n{'='*50}")
    print(f"  Yuni is online as {client.user}")
    print(f"  Active channels: {ACTIVE_CHANNEL_IDS}")
    print(f"  DMs: enabled")
    print(f"  Random messages: {RANDOM_MESSAGES_PER_DAY}/day ({QUIET_END_HOUR}:00-{QUIET_START_HOUR}:00)")
    print(f"{'='*50}\n")

    # Start the random message scheduler
    client.loop.create_task(random_message_scheduler())


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

    async with message.channel.typing():
        reply = await call_yuni_brain(
            text=text,
            image_urls=image_urls,
            username=message.author.display_name,
        )

    if reply:
        if len(reply) > 2000:
            reply = reply[:1997] + "..."
        await message.channel.send(reply)


if __name__ == "__main__":
    print("Starting Yuni Discord Bot...")
    client.run(BOT_TOKEN)
