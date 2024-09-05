import discord
import os
from discord.ext import commands
from datetime import datetime, timedelta

# Token bota
TOKEN = os.getenv('DISCORD_TOKEN')

# Ustawienie prefiksu komend
bot = commands.Bot(command_prefix="!")

# Kanał, w którym bot ma działać (wprowadź odpowiedni ID kanału)
WORK_CHANNEL_ID = 1234567890

# Struktura danych do przechowywania czasu pracy użytkowników
work_times = {}

def time_difference(start, end):
    """Oblicza różnicę czasu pomiędzy dwoma datami"""
    return (end - start).total_seconds()

def format_time(seconds):
    """Konwertuje czas w sekundach na godziny i minuty"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}min"

@bot.event
async def on_ready():
    print(f'Bot zalogowany jako {bot.user}')

@bot.command()
async def worktime(ctx):
    """Komenda, która generuje raport pracy użytkowników"""
    if ctx.channel.id != WORK_CHANNEL_ID:
        return await ctx.send("Ta komenda działa tylko na wybranym kanale.")

    report = "Work Time:\n"
    for user_id, months in work_times.items():
        user = bot.get_user(user_id)
        user_report = f"{user.name}:\n"
        total_undertime = 0
        total_overtime = 0

        for month, time_spent in months.items():
            # Czas wymagany to 40h = 144000 sekund
            required_time = 40 * 3600
            if time_spent < required_time:
                user_report += f"{month} - {format_time(time_spent)} - Not enough!\n"
                total_undertime += required_time - time_spent
            elif time_spent > required_time:
                user_report += f"{month} - {format_time(time_spent)} - Too much!\n"
                total_overtime += time_spent - required_time
            else:
                user_report += f"{month} - {format_time(time_spent)} - OK\n"

        # Kompensacja nadgodzin i niedogodzin
        if total_overtime > total_undertime:
            total_overtime -= total_undertime
            total_undertime = 0
        else:
            total_undertime -= total_overtime
            total_overtime = 0

        user_report += f"Undertime: {format_time(total_undertime)}\n"
        user_report += f"Overtime: {format_time(total_overtime)}\n"
        report += user_report + "\n"

    await ctx.send(report)

@bot.event
async def on_message(message):
    """Obsługa wiadomości i zliczanie czasu pracy"""
    if message.channel.id != WORK_CHANNEL_ID:
        return

    user_id = message.author.id
    content = message.content.lower()
    current_time = message.created_at

    if user_id not in work_times:
        work_times[user_id] = {}

    month_key = f"{current_time.month}.{current_time.year}"
    if month_key not in work_times[user_id]:
        work_times[user_id][month_key] = 0

    # Włączanie/wyłączanie licznika pracy na podstawie wiadomości
    if content == "in":
        work_times[user_id]["start_time"] = current_time
    elif content == "afk" and "start_time" in work_times[user_id]:
        if "afk_start_time" not in work_times[user_id]:
            work_times[user_id]["afk_start_time"] = current_time
    elif content == "back" and "afk_start_time" in work_times[user_id]:
        afk_duration = time_difference(work_times[user_id]["afk_start_time"], current_time)
        work_times[user_id]["afk_duration"] = afk_duration
        del work_times[user_id]["afk_start_time"]
    elif content == "out" and "start_time" in work_times[user_id]:
        if "afk_duration" not in work_times[user_id]:
            work_times[user_id]["afk_duration"] = 0

        work_duration = time_difference(work_times[user_id]["start_time"], current_time) - work_times[user_id]["afk_duration"]
        work_times[user_id][month_key] += work_duration

        # Reset stanu pracy użytkownika
        del work_times[user_id]["start_time"]
        if "afk_duration" in work_times[user_id]:
            del work_times[user_id]["afk_duration"]

    await bot.process_commands(message)

# Uruchomienie bota
bot.run(TOKEN)
