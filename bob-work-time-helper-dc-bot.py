import discord
import os
import asyncio
import pytz
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
WORK_TIME_BACKUP_CHANNEL_ID = 1281390847115661424

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
    # Uruchomienie funkcji planującej backup raz w tygodniu
    bot.loop.create_task(schedule_backup())

# Funkcja, która planuje backup raz w tygodniu o określonej godzinie w strefie czasowej
async def schedule_backup():
    """Zaplanuje backup raz w tygodniu o określonej godzinie, uwzględniając strefy czasowe"""
    
    # Ustawienie strefy czasowej, np. Europe/Warsaw
    timezone = pytz.timezone('Europe/Warsaw')
    
    while True:
        # Pobierz aktualny czas w UTC
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # Przekonwertuj czas UTC na wybraną strefę czasową (Europe/Warsaw)
        now_local = now_utc.astimezone(timezone)

        # Określ czas, kiedy ma nastąpić backup (np. 1:00 rano)
        backup_time_local = timezone.localize(datetime.datetime.combine(now_local.date(), datetime.time(hour=8, minute=0)))

        # Jeśli backup miał się odbyć dzisiaj, ale godzina już minęła, ustaw go na następny tydzień
        if now_local > backup_time_local:
            backup_time_local += datetime.timedelta(weeks=1)

        # Oblicz, ile czasu musimy czekać do momentu backupu
        wait_time = (backup_time_local - now_local).total_seconds()
        print(f"Zaplanowano backup na: {backup_time_local} (czeka: {wait_time / 3600:.2f} godzin)")

        # Poczekaj do zaplanowanego czasu
        await asyncio.sleep(wait_time)

        # Wykonaj backup
        await save_worktime_backup()

        # Poczekaj tydzień do następnego backupu
        await asyncio.sleep(7 * 24 * 3600)  # 7 dni w sekundach
        
async def save_worktime_backup():
    """Generuje raport z !worktime i zapisuje go do pliku w folderze backups"""
    folder_path = 'backups'
    
    # Sprawdzenie, czy folder backups istnieje, jeśli nie, to go tworzymy
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    # Generujemy nazwę pliku z datą wykonania backupu
    current_time = datetime.datetime.now()
    backup_filename = f"worktimebackup_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    backup_filepath = os.path.join(folder_path, backup_filename)
    
    # Użycie funkcji generate_worktime_report() do uzyskania raportu
    report = await generate_worktime_report()

    # Zapisanie raportu do pliku
    with open(backup_filepath, 'w') as backup_file:
        backup_file.write(report)
    
    print(f"Backup zapisany do pliku: {backup_filepath}")    

    # Wysłanie pliku na kanał na Discordzie
    backup_channel = bot.get_channel(WORK_CHANNEL_ID)  # Zmień na odpowiedni ID kanału
    if backup_channel:
        await backup_channel.send(f"Backup z daty: {current_time.strftime('%Y-%m-%d %H:%M:%S')}", file=discord.File(backup_filepath))

async def generate_worktime_report():
    """Generuje raport pracy użytkowników jako string"""
    report = "Work Time:\n"
    for user_id, months in work_times.items():
        user = await bot.fetch_user(user_id)
        if user is None or user.bot:
            continue

        user_report = f"{user.name}:\n"
        total_undertime = 0
        total_overtime = 0

        for month, time_spent in months.items():
            if isinstance(time_spent, datetime.datetime):
                time_spent = (datetime.datetime.now(datetime.timezone.utc) - time_spent).total_seconds()

            required_time = 40 * 3600  # 40 godzin to 144000 sekund

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

    return report

@bot.command()
async def worktime(ctx):
    """Komenda, która generuje raport pracy użytkowników i wysyła go na kanał"""
    if ctx.channel.id != WORK_CHANNEL_ID:
        return await ctx.send("Ta komenda działa tylko na wybranym kanale.")
    
    report = await generate_worktime_report()
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
