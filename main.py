import discord
from discord.ext import commands
import youtube_dl
import asyncio
import sys
from functools import partial

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Constants
# Ensure FFmpeg is correctly configured
FFMPEG_OPTIONS = {
  'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'
  }


# YouTube_DL options
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'verbose': True
}
queues = {}
idle_disconnect_time = 300  # 5 minutes in seconds


def check_queue(ctx):
    """Check the queue and play the next song."""
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        next_song = queues[ctx.guild.id].pop(0)
        ctx.voice_client.play(next_song, after=lambda e: check_queue(ctx))
    else:
        # If no songs are left, start the idle timer
        asyncio.run_coroutine_threadsafe(start_idle_timer(ctx), bot.loop)


async def start_idle_timer(ctx):
    """Start a timer to disconnect after idle time."""
    await asyncio.sleep(idle_disconnect_time)
    if ctx.voice_client and not ctx.voice_client.is_playing():
        await ctx.voice_client.disconnect()


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.command(name="leave", help="Bot leaves the voice channel.")
async def leave(ctx):
    if ctx.voice_client:
        queues.pop(ctx.guild.id, None)  # Clear the queue
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("I'm not in a voice channel!")


@bot.command(name="play", help="Plays audio from a YouTube URL or adds it to the queue.")
async def play(ctx, url):
    if not ctx.voice_client:
        if not ctx.author.voice:
          await ctx.send("You need to be in a voice channel to use this command.")
          return
        channel = ctx.author.voice.channel
        await channel.connect()

    vc = ctx.voice_client

    def play_next(ctx):
        """Callback to play the next song in the queue."""
        asyncio.run_coroutine_threadsafe(check_queue(ctx), bot.loop)

    try:
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['formats'][0]['url']
            source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)

            # Add to queue if a song is already playing
            if vc.is_playing() or vc.is_paused():
                if ctx.guild.id not in queues:
                    queues[ctx.guild.id] = []
                queues[ctx.guild.id].append(source)
                await ctx.send(f"Added to queue: {info['title']}")
            else:
                vc.play(source, after=lambda e: play_next(ctx))
                await ctx.send(f"Now playing: {info['title']}")

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")


@bot.command(name="skip", help="Skips the current song.")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the current song.")
    else:
        await ctx.send("No audio is playing to skip!")


@bot.command(name="queue", help="Displays the current song queue.")
async def show_queue(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        queue_list = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(queues[ctx.guild.id])])
        await ctx.send(f"Current Queue:\n{queue_list}")
    else:
        await ctx.send("The queue is empty.")


@bot.command(name="stop", help="Stops playback and clears the queue.")
async def stop(ctx):
    if ctx.voice_client:
        queues.pop(ctx.guild.id, None)  # Clear the queue
        ctx.voice_client.stop()
        await ctx.send("Playback stopped and queue cleared.")
    else:
        await ctx.send("I'm not playing anything!")


# Run the bot
bot.run(sys.argv[1])