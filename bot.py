import asyncio
import json
import os
import time

import requests
from aiohttp import web
from discord import Client, Intents, Embed, Game
from discord_slash import SlashCommand, SlashContext, SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option

try:
    GUILD_IDS = [int(x) for x in os.getenv('GUILD_IDS').split(',')]
except ValueError:
    GUILD_IDS = None

LOVENSE_DEVELOPER_TOKEN = os.getenv('LOVENSE_DEVELOPER_TOKEN')
TOKEN = os.getenv('TOKEN')
REQUEST_HEADRERS = {
        'User-Agent': 'ToyBot/beep-boop'
    }
API_URL_QR = 'https://api.lovense.com/api/lan/getQrCode'
API_URL_COMMAND = 'https://api.lovense.com/api/lan/v2/command'
CALLBACK_PORT = 8000

bot = Client(intents=Intents.default())
slash = SlashCommand(bot, sync_commands=True, debug_guild=os.getenv('DEBUG_GUILD_ID', None))


async def update_activity():
    while True:
        if bot.is_ready():
            toy_count = sum([len(controller.get_toys(str(x))) for x in GUILD_IDS])
            playing = 'with ' + ('no toys' if toy_count == 0 else '1 toy' if toy_count == 1 else '{} toys'.format(toy_count))
            await bot.change_presence(activity=Game(name=playing))
        await asyncio.sleep(60)


@slash.subcommand(base='lovense', name="connect",
                  description="Connect a toy", guild_ids=GUILD_IDS)
async def connect(ctx: SlashContext):
    url = controller.get_connection_qr(str(ctx.guild_id), str(ctx.author_id))
    if url is None:
        await ctx.send("Sorry, I can't connect to Lovense right now", hidden=True)
        return

    embed = Embed(title='Connect with Lovense Remote', description="Using the Lovense Remote app, press the + button > Scan QR. " +
                                                                   "This is *your* personal QR code, sharing it might prevent the connection from working")
    embed.set_image(url=url)
    await ctx.send(embeds=[embed], hidden=True)


@slash.subcommand(base='lovense', name="status",
                  description="List connected toys", guild_ids=GUILD_IDS)
async def status(ctx: SlashContext):
    embed = Embed(title='Connected Toys')
    toy_count = {}
    for toy in controller.get_toys(str(ctx.guild_id)):
        toy_count[toy] = toy_count+1 if toy in toy_count else 1
    if not toy_count:
        await ctx.send("There are no toys connected")
        return
    for toy, count in toy_count.items():
        embed.add_field(name=toy.title(), value='{} connected'.format(count), inline=True)
    await ctx.send(embeds=[embed])


@slash.subcommand(base='lovense', name="vibrate",
                  description="Vibrate all toys",
                  guild_ids=GUILD_IDS,
                  options=[
                      create_option(
                          name="strength",
                          description="Vibration strength (1-20). Defaults to 10",
                          option_type=SlashCommandOptionType.INTEGER,
                          required=False
                      ),
                      create_option(
                          name="duration",
                          description="Number of seconds it lasts. Defaults to 10 secconds",
                          option_type=SlashCommandOptionType.INTEGER,
                          required=False
                      ),
                  ])
async def vibrate(ctx: SlashContext, strength=10, duration=10):
    if controller.vibrate(str(ctx.guild_id), duration=duration, strength=strength):
        await ctx.send("Buzz buzz!", hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


@slash.subcommand(base='lovense', name="rotate",
                  description="Rotate all toys",
                  guild_ids=GUILD_IDS,
                  options=[
                      create_option(
                          name="strength",
                          description="Rotation strength (1-20). Defaults to 10",
                          option_type=SlashCommandOptionType.INTEGER,
                          required=False
                      ),
                      create_option(
                          name="duration",
                          description="Number of seconds it lasts. Defaults to 10 secconds",
                          option_type=SlashCommandOptionType.INTEGER,
                          required=False
                      ),
                  ])
async def rotate(ctx: SlashContext, strength=10, duration=10):
    if controller.rotate(str(ctx.guild_id), duration=duration, strength=strength):
        await ctx.send("You spin me right round baby...", hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


@slash.subcommand(base='lovense', name="pump",
                  description="Pump all toys",
                  guild_ids=GUILD_IDS,
                  options=[
                      create_option(
                          name="strength",
                          description="Pump strength (1-3). Defaults to 2",
                          option_type=SlashCommandOptionType.INTEGER,
                          required=False
                      ),
                      create_option(
                          name="duration",
                          description="Number of seconds it lasts. Defaults to 10 secconds",
                          option_type=SlashCommandOptionType.INTEGER,
                          required=False
                      ),
                  ])
async def rotate(ctx: SlashContext, strength=2, duration=10):
    if controller.pump(str(ctx.guild_id), duration=duration, strength=strength):
        await ctx.send("Let's get pumped!", hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


@slash.subcommand(base='lovense', name="pattern",
                  description="Send a pattern to all toys. Loops until stopped, or replaced with another vibration or pattern",
                  guild_ids=GUILD_IDS,
                  options=[
                      create_option(
                          name="pattern",
                          description="The pattern to send",
                          option_type=SlashCommandOptionType.STRING,
                          choices=['pulse', 'wave', 'fireworks', 'earthquake'],
                          required=True
                      )
                  ])
async def vibrate_pattern(ctx: SlashContext, pattern):
    if controller.pattern(str(ctx.guild_id), pattern):
        await ctx.send("Here comes the {}!".format(pattern), hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


@slash.subcommand(base='lovense', name="stop",
                  description="Stop all toys", guild_ids=GUILD_IDS)
async def stop(ctx: SlashContext):
    if controller.stop(str(ctx.guild_id)):
        await ctx.send("Break-time!", hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


class ToyController:
    BASE_REQ = {
            'token': LOVENSE_DEVELOPER_TOKEN,
            'apiVer': '1'
        }
    guilds = {}

    def __init__(self):
        try:
            with open('guilds.json', 'r') as f:
                self.guilds = json.loads(f.read())
        except (FileNotFoundError, IOError, json.decoder.JSONDecodeError):
            self.guilds = {}

    def get_connection_qr(self, guild_id: str, uid: str):
        req = {**self.BASE_REQ, **{
            'uid': guild_id+':'+uid,
        }}
        try:
            with requests.post(API_URL_QR, req) as response:
                return response.json().get('message', None)
        except (json.JSONDecodeError, AttributeError):
            return None

    def add_user(self, guild_id: str, uid: str, user):
        if guild_id not in self.guilds:
            print("Adding new guild with GID {}".format(guild_id))
            self.guilds[guild_id] = {}
        if uid not in self.guilds.get(guild_id):
            print("Added new user with GID:UID {}:{}".format(guild_id, uid))
        user['last_updated'] = round(time.time())
        self.guilds[guild_id][uid] = user
        self._save()

    def get_toys(self, guild_id: str):
        self._refresh()
        toys = []
        if guild_id not in self.guilds:
            return []
        for uid, user in self.guilds.get(guild_id).items():
            toys += [y.get('name') for x, y in user.get('toys').items()]
        return toys

    def stop(self, guild_id: str):
        return self._function(guild_id, 'Stop', None, 0, 0)

    def pattern(self, guild_id: str, pattern, uid: str = None):
        self._refresh()
        if self.guilds.get(guild_id) is None:
            return False
        if uid is not None and uid not in self.guilds.get(guild_id):
            return False
        req = {**self.BASE_REQ, **{
            'uid': ','.join(self.guilds.get(guild_id).keys() if uid is None else [guild_id + ':' + uid]),
            'command': 'Preset',
            'name': pattern,
            'timeSec': 0,
        }}
        with requests.post(API_URL_COMMAND, json=req, timeout=5) as response:
            return response.status_code == 200

    def vibrate(self, guild_id: str, uid: str = None, strength: int = 10, duration: int = 10):
        return self._function(guild_id, 'Vibrate', uid, strength, duration)

    def rotate(self, guild_id: str, uid: str = None, strength: int = 10, duration: int = 10):
        return self._function(guild_id, 'Rotate', uid, strength, duration)

    def pump(self, guild_id: str, uid: str = None, strength: int = 10, duration: int = 10):
        return self._function(guild_id, 'Pump', uid, strength, duration)

    # Send a command=Function request
    def _function(self, guild_id: str, action: str, uid: str = None, strength: int = 10, duration: int = 10):
        self._refresh()
        if guild_id not in self.guilds:
            return False
        if uid is not None and uid not in self.guilds.get(guild_id):
            return False
        if strength > 0:
            action += ':{}'.format(strength)
        uids = ['{}:{}'.format(guild_id, x) for x in (self.guilds.get(guild_id).keys() if uid is None else [uid])]
        req = {**self.BASE_REQ, **{
            'uid': ','.join(uids),
            'command': 'Function',
            'action': action,
            'timeSec': duration,
        }}
        with requests.post(API_URL_COMMAND, json=req, timeout=5) as response:
            return response.status_code == 200

    def _refresh(self):
        now = round(time.time())
        old = {**self.guilds}
        for guild_id, users in self.guilds.items():
            self.guilds[guild_id] = {k: v for k, v in users.items() if v.get('last_updated') >= now - 60}
        if self.guilds != old:
            self._save()

    def _save(self):
        try:
            with open('guilds.json', 'w') as f:
                f.write(json.dumps(self.guilds))
            return True
        except IOError:
            return False


class Callbacks:
    def __init__(self, bot, controller: ToyController):
        self.bot = bot
        self.controller = controller
        self.site = None

    async def webserver(self):
        async def handler(request: web.Request):
            if request.body_exists and request.can_read_body:
                body = await request.json()
                pieces = body.get('uid').split(':')
                self.controller.add_user(pieces[0], pieces[1], body)
            return web.Response(body=json.dumps({'status': 'OK'}))

        app = web.Application()
        app.router.add_get('/', handler)
        app.router.add_post('/', handler)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, port=CALLBACK_PORT)
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())


controller = ToyController()
callbacks = Callbacks(bot, controller)
bot.loop.create_task(callbacks.webserver())
bot.loop.create_task(update_activity())
bot.run(TOKEN)
