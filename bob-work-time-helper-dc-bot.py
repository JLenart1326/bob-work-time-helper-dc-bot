import discord
import os
from discord.ext import commands
import datetime

# Token bota
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.messages = True  # Umożliwia botowi odczytywanie wiadomości
intents.message_content = True  # Pozwala botowi na odczytywanie treści wiadomości (od wersji 2.0)

# Ustawienie prefiksu komend
bot = commands.Bot(command_prefix="!", intents=intents)

# Kanał, w którym bot ma działać (wprowadź odpowiedni ID kanału)
WORK_CHANNEL_ID = 1280152686737494027

# Lista wariantów słów oznaczających rozpoczęcie pracy
IN_VARIANTS = ["in", "IN", "In", "iN"]

# Lista wariantów słów oznaczających przerwę
AFK_VARIANTS = ["afk", "AFK", "Afk", "aFk", "afK", "AFk", "AfK", "aFK"]

# Lista wariantów słów oznaczających powrót z przerwy
BACK_VARIANTS = ["back", "BACK", "Back", "bAck", "baCk", "bacK"]

# Lista wariantów słów oznaczających zakończenie pracy
OUT_VARIANTS = ["out", "OUT", "Out", "oUt", "ouT", "OUt", "OuT", "oUT"]

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
        user = await bot.fetch_user(user_id)

         # Ignorowanie bota przy wypisywaniu raportu
        if user is None or user.bot:
            print(f"Zignorowano użytkownika bota o ID: {user_id}")
            continue

        user_report = f"{user.name}:\n"
        total_undertime = 0
        total_overtime = 0

        for month, time_spent in months.items():
            # Jeśli time_spent jest obiektem datetime, zamień go na liczbę sekund
            if isinstance(time_spent, datetime.datetime):
                # Zakładam, że jeśli `time_spent` to datetime, to jest to czas rozpoczęcia pracy,
                # więc obliczamy różnicę do teraz, aby uzyskać liczbę sekund.
                time_spent = (datetime.datetime.now(datetime.timezone.utc) - time_spent).total_seconds()

            # Czas wymagany to 40h = 144000 sekund
            required_time = 40 * 3600

            # Porównanie z required_time (które jest w sekundach)
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

 # Sprawdzanie słów kluczowych
    if any(variant in content for variant in IN_VARIANTS):
        work_times[user_id]["start_time"] = current_time
    elif any(variant in content for variant in AFK_VARIANTS) and "start_time" in work_times[user_id]:
        if "afk_start_time" not in work_times[user_id]:
            work_times[user_id]["afk_start_time"] = current_time
    elif any(variant in content for variant in BACK_VARIANTS) and "afk_start_time" in work_times[user_id]:
        afk_duration = time_difference(work_times[user_id]["afk_start_time"], current_time)
        work_times[user_id]["afk_duration"] = afk_duration
        del work_times[user_id]["afk_start_time"]
    elif any(variant in content for variant in OUT_VARIANTS) and "start_time" in work_times[user_id]:
        if "afk_duration" not in work_times[user_id]:
            work_times[user_id]["afk_duration"] = 0

        work_duration = time_difference(work_times[user_id]["start_time"], current_time) - work_times[user_id]["afk_duration"]
        work_times[user_id][month_key] += work_duration

        # Reset stanu pracy użytkownika
        del work_times[user_id]["start_time"]
        if "afk_duration" in work_times[user_id]:
            del work_times[user_id]["afk_duration"]

    await bot.process_commands(message)

# Użytkownik z odpowiednimi uprawnieniami (zmień ID na prawidłowe)
AUTHORIZED_USER_ID = 726528438701391972  # Zmień na ID użytkownika, który ma uprawnienia

@bot.command()
async def addtime(ctx, user: discord.Member, hours: int, minutes: int):
    """Dodaje czas pracy dla wybranego użytkownika"""
    if ctx.author.id != AUTHORIZED_USER_ID:
        return await ctx.send("Nie masz uprawnień do użycia tej komendy.")
    
    current_time = datetime.datetime.now(datetime.timezone.utc)  # Użyj UTC-aware datetime
    month_key = f"{current_time.month}.{current_time.year}"
    
    # Upewnij się, że użytkownik ma zapisaną strukturę czasu pracy
    if user.id not in work_times:
        work_times[user.id] = {}
    
    if month_key not in work_times[user.id]:
        work_times[user.id][month_key] = 0

    # Dodaj czas (w sekundach) do aktualnie naliczonego czasu
    additional_time = (hours * 3600) + (minutes * 60)
    work_times[user.id][month_key] += additional_time

    await ctx.send(f"Dodano {hours}h {minutes}min do czasu pracy użytkownika {user.name}.")

@bot.command()
async def removetime(ctx, user: discord.Member, hours: int, minutes: int):
    """Usuwa czas pracy dla wybranego użytkownika"""
    if ctx.author.id != AUTHORIZED_USER_ID:
        return await ctx.send("Nie masz uprawnień do użycia tej komendy.")
    
    current_time = datetime.datetime.now(datetime.timezone.utc)  # Używamy datetime.datetime.now() po imporcie całego modułu
    month_key = f"{current_time.month}.{current_time.year}"
    
    # Upewnij się, że użytkownik ma zapisaną strukturę czasu pracy
    if user.id not in work_times:
        work_times[user.id] = {}

    if month_key not in work_times[user.id]:
        work_times[user.id][month_key] = 0

    # Usuń czas (w sekundach) z aktualnie naliczonego czasu
    removed_time = (hours * 3600) + (minutes * 60)
    work_times[user.id][month_key] -= removed_time

    await ctx.send(f"Usunięto {hours}h {minutes}min z czasu pracy użytkownika {user.name}.")



# Uruchomienie bota
bot.run(TOKEN)
