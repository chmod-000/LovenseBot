import asyncio
import json
import os
import time

import requests
from aiohttp import web
from discord import Client, Intents, Embed
from discord_slash import SlashCommand, SlashContext, SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option

try:
    GUILD_IDS = [int(x) for x in os.getenv('GUILD_IDS').split(',')]
except ValueError:
    GUILD_IDS = []

LOVENSE_DEVELOPER_TOKEN = os.getenv('LOVENSE_DEVELOPER_TOKEN')
TOKEN = os.getenv('TOKEN')
REQUEST_HEADRERS = {
        'User-Agent': 'ToyBot/beep-boop'
    }
API_URL_QR = 'https://api.lovense.com/api/lan/getQrCode'
API_URL_COMMAND = 'https://api.lovense.com/api/lan/v2/command'
CALLBACK_PORT = 8000

bot = Client(intents=Intents.default())
slash = SlashCommand(bot, sync_commands=True)


@slash.subcommand(base='lovense', name="connect",
                  description="Connect a toy")
async def connect(ctx: SlashContext):
    url = controller.get_connection_qr(ctx.author_id)
    if url is None:
        await ctx.send("Sorry, I can't connect to Lovense right now", hidden=True)
        return

    embed = Embed(title='Connect with Lovense Remote', description="Using the Lovense Remote app, press the + button > Scan QR. " +
                                                                   "This is *your* personal QR code, sharing it might prevent the connection from working")
    embed.set_image(url=url)
    await ctx.send(embeds=[embed], hidden=True)


@slash.subcommand(base='lovense', name="status",
                  description="List connected toys")
async def status(ctx: SlashContext):
    embed = Embed(title='Connected Toys')
    toy_count = {}
    for toy in controller.get_toys():
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
    if controller.vibrate(duration=duration, strength=strength):
        await ctx.send("Buzz buzz!", hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


@slash.subcommand(base='lovense', name="pattern",
                  description="Send a pattern to all toys",
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
async def vibrate(ctx: SlashContext, pattern):
    if controller.pattern(pattern):
        await ctx.send("Here comes the {}!".format(pattern), hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


@slash.subcommand(base='lovense', name="stop",
                  description="Stop all toys")
async def stop(ctx: SlashContext):
    if controller.stop():
        await ctx.send("Break-time!", hidden=True)
    else:
        await ctx.send("There aren't any toys connected", hidden=True)


class ToyController:
    BASE_REQ = {
            'token': LOVENSE_DEVELOPER_TOKEN,
            'apiVer': '1'
        }
    users = {}

    def __init__(self):
        try:
            with open('users.json', 'r') as f:
                self.users = json.loads(f.read())
        except (FileNotFoundError, IOError, json.decoder.JSONDecodeError):
            self.users = {}

    def get_connection_qr(self, uid):
        req = {**self.BASE_REQ, **{
            'uid': uid,
        }}
        try:
            with requests.post(API_URL_QR, req) as response:
                return response.json().get('message', None)
        except (json.JSONDecodeError, AttributeError):
            return None

    def add_user(self, uid, user):
        if uid not in self.users:
            print("Added new user with UID {}".format(uid))
        user['last_updated'] = round(time.time())
        self.users[str(uid)] = user
        self._save()

    def get_toys(self):
        self._refresh()
        toys = []
        for uid, user in self.users.items():
            toys += [y.get('name') for x, y in user.get('toys').items()]
        return toys

    def stop(self):
        self._refresh()
        if not self.users:
            return False
        req = {**self.BASE_REQ, **{
            'uid': ','.join(self.users.keys()),
            'command': 'Function',
            'action': 'Stop',
            'timeSec': '0'
        }}
        with requests.post(API_URL_COMMAND, json=req, timeout=5) as response:
            return response.status_code == 200

    def pattern(self, pattern, uid: str = None):
        self._refresh()
        if not self.users:
            return False
        if uid is not None and uid not in self.users:
            return False
        req = {**self.BASE_REQ, **{
            'uid': ','.join(self.users.keys() if uid is None else [uid]),
            'command': 'Preset',
            'name': pattern,
            'timeSec': 0,
        }}
        with requests.post(API_URL_COMMAND, json=req, timeout=5) as response:
            return response.status_code == 200

    def vibrate(self, uid: str = None, strength: int = 10, duration: int = 10):
        self._refresh()
        if not self.users:
            return False
        if uid is not None and uid not in self.users:
            return False
        req = {**self.BASE_REQ, **{
            'uid': ','.join(self.users.keys() if uid is None else [uid]),
            'command': 'Function',
            'action': 'Vibrate:{}'.format(strength),
            'timeSec': duration,
        }}
        with requests.post(API_URL_COMMAND, json=req, timeout=5) as response:
            return response.status_code == 200

    def _refresh(self):
        now = round(time.time())
        old = self.users
        self.users = {k: v for k, v in self.users.items() if v.get('last_updated') >= now-60}
        if self.users != old:
            self._save()

    def _save(self):
        try:
            with open('users.json', 'w') as f:
                f.write(json.dumps(self.users))
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
                self.controller.add_user(body.get('uid'), body)
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
bot.run(TOKEN)
