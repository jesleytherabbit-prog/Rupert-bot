"""Rupert Bramble — Magic Chef. Python 3.11+."""
import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger('rupert')
ZONE = ZoneInfo(os.getenv('TIMEZONE', 'America/Argentina/Cordoba'))


def deadline(value):
    try:
        result = datetime.strptime(value, '%Y-%m-%d %H:%M').replace(tzinfo=ZONE)
    except ValueError:
        raise ValueError('Usá el formato AAAA-MM-DD HH:MM, por ejemplo 2026-11-10 21:00.')
    if result.timestamp() <= time.time():
        raise ValueError('El cierre debe estar en el futuro.')
    return int(result.timestamp())


class Rupert(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.none(), allowed_mentions=discord.AllowedMentions.none())
        self.tree = app_commands.CommandTree(self)
        self.lock = asyncio.Lock()

    async def setup_hook(self):
        self.guild_id = int(os.environ['DISCORD_GUILD_ID'])
        self.channel_id = int(os.environ['DISCORD_CHANNEL_ID'])
        self.role_id = int(os.environ['DISCORD_ROLE_ID'])
        path = Path(os.getenv('DATABASE_PATH', 'data/rupert.sqlite3'))
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
            closes INTEGER NOT NULL, hours INTEGER NOT NULL, reminded INTEGER DEFAULT 0,
            closed INTEGER DEFAULT 0, active INTEGER DEFAULT 1)''')
        self.db.commit()
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.watch.start()

    def current(self):
        return self.db.execute('SELECT * FROM turns WHERE active=1 ORDER BY id DESC LIMIT 1').fetchone()

    async def announce(self, title, body):
        channel = await self.fetch_channel(self.channel_id)
        if channel.guild.id != self.guild_id:
            raise ValueError('El canal configurado no pertenece al servidor configurado.')
        embed = discord.Embed(title=title, description=body, color=0xC5A15A)
        embed.set_footer(text='Rupert Bramble · Sabores del Mundo Mágico')
        return await channel.send(content=f'<@&{self.role_id}>', embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=[discord.Object(id=self.role_id)]))

    @tasks.loop(seconds=30)
    async def watch(self):
        async with self.lock:
            row = self.current()
            if not row:
                return
            now = time.time()
            try:
                if now >= row['closes'] and not row['closed']:
                    await self.announce('🔔 ¡Se apagan los fogones!',
                        f'El plazo de **{discord.utils.escape_markdown(row["title"])}** terminó.\n'
                        f'[Consultar el turno]({row["url"]})\nProducción confirmará cómo continúa el concurso.')
                    self.db.execute('UPDATE turns SET closed=1, reminded=1 WHERE id=?', (row['id'],))
                elif row['hours'] and not row['reminded'] and row['closes']-row['hours']*3600 <= now < row['closes']:
                    await self.announce('⏳ ¡Atención, cocineros!',
                        f'El turno **{discord.utils.escape_markdown(row["title"])}** cierra <t:{row["closes"]}:R>.\n'
                        f'[Ir al turno]({row["url"]})\n¡Que no se les enfríe el plato!')
                    self.db.execute('UPDATE turns SET reminded=1 WHERE id=?', (row['id'],))
                self.db.commit()
            except (discord.HTTPException, ValueError):
                log.exception('No se pudo entregar el aviso; se reintentará en 30 segundos.')

    @watch.before_loop
    async def ready(self):
        await self.wait_until_ready()


bot = Rupert()


def producer():
    async def check(i):
        return i.guild_id == bot.guild_id and i.permissions.manage_guild
    return app_commands.check(check)


@bot.tree.command(description='Publica un turno nuevo y programa sus avisos.')
@app_commands.default_permissions(manage_guild=True)
@producer()
@app_commands.describe(cierre='AAAA-MM-DD HH:MM, hora de la zona configurada', recordatorio='Horas antes del cierre; 0 desactiva el recordatorio')
async def turno(i: discord.Interaction, titulo: app_commands.Range[str, 1, 150], enlace: str,
                cierre: str, recordatorio: app_commands.Range[int, 0, 168] = 24):
    end = deadline(cierre)
    parsed = urlsplit(enlace)
    if parsed.scheme != 'https' or not parsed.hostname or any(c in enlace for c in '\n\r<>() '):
        raise ValueError('Usá un enlace HTTPS válido al post del foro, sin espacios.')
    if len(enlace) > 1500:
        raise ValueError('El enlace es demasiado largo.')
    await i.response.defer(ephemeral=True)
    async with bot.lock:
        await bot.announce('📻 ¡Tenemos un nuevo turno!',
            f'**{discord.utils.escape_markdown(titulo)}**\n\n[Leer el turno]({enlace})\n'
            f'⏳ Cierre: <t:{end}:F> · <t:{end}:R>\n\n¡Delantales puestos y varitas preparadas!')
        with bot.db:
            bot.db.execute('UPDATE turns SET active=0')
            bot.db.execute('INSERT INTO turns(title,url,closes,hours) VALUES(?,?,?,?)',
                           (titulo, enlace, end, recordatorio))
    await i.followup.send('Turno publicado y guardado. Los avisos están preparados.', ephemeral=True)


@bot.tree.command(description='Consulta el turno vigente y su cierre.')
async def plazo(i: discord.Interaction):
    if i.guild_id != bot.guild_id:
        return await i.response.send_message('Este comando se usa en el servidor de Magic Chef.', ephemeral=True)
    row = bot.current()
    body = 'Todavía no hay un turno vigente.' if not row else (
        f'**{discord.utils.escape_markdown(row["title"])}**\n{row["url"]}\n'
        f'Cierre: <t:{row["closes"]}:F> · <t:{row["closes"]}:R>')
    await i.response.send_message(body, ephemeral=True)


@bot.tree.command(description='Cambia el cierre y reprograma los avisos del turno.')
@app_commands.default_permissions(manage_guild=True)
@producer()
async def ampliar(i: discord.Interaction, cierre: str):
    end = deadline(cierre)
    await i.response.defer(ephemeral=True)
    async with bot.lock:
        row = bot.current()
        if not row:
            return await i.followup.send('No hay turno vigente.', ephemeral=True)
        await bot.announce('📻 ¡Nuevo plazo para los cocineros!',
            f'**{discord.utils.escape_markdown(row["title"])}**\nNuevo cierre: <t:{end}:F> · <t:{end}:R>\n'
            f'[Consultar el turno]({row["url"]})')
        with bot.db:
            bot.db.execute('UPDATE turns SET closes=?, reminded=0, closed=0 WHERE id=?', (end, row['id']))
    await i.followup.send('Plazo actualizado. El anuncio original conserva la fecha anterior; rige el nuevo aviso.', ephemeral=True)


@bot.tree.command(description='Desactiva los avisos pendientes del turno vigente.')
@app_commands.default_permissions(manage_guild=True)
@producer()
async def cancelar(i: discord.Interaction):
    async with bot.lock:
        with bot.db:
            bot.db.execute('UPDATE turns SET active=0 WHERE active=1')
    await i.response.send_message('Avisos pendientes cancelados. Los mensajes publicados se conservan.', ephemeral=True)


@bot.tree.error
async def errors(i: discord.Interaction, error: app_commands.AppCommandError):
    original = getattr(error, 'original', error)
    if isinstance(original, ValueError):
        message = str(original)
    elif isinstance(error, app_commands.CheckFailure):
        message = 'Necesitás el permiso Gestionar servidor para administrar turnos.'
    elif isinstance(original, discord.Forbidden):
        message = 'Rupert necesita Ver canal, Enviar mensajes e Insertar enlaces en el canal de avisos.'
    else:
        log.error('Falló un comando', exc_info=(type(original), original, original.__traceback__))
        message = 'No pude completar la operación. Revisá el canal de avisos antes de repetirla y consultá los registros.'
    if i.response.is_done():
        await i.followup.send(message, ephemeral=True)
    else:
        await i.response.send_message(message, ephemeral=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    required = ['DISCORD_TOKEN', 'DISCORD_GUILD_ID', 'DISCORD_CHANNEL_ID', 'DISCORD_ROLE_ID']
    if any(not os.getenv(k) for k in required):
        raise SystemExit('Completá las variables de .env siguiendo README.md.')
    bot.run(os.environ['DISCORD_TOKEN'])
