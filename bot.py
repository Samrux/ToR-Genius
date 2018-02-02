# Original work Copyright (c) 2015 Rapptz (https://github.com/Rapptz/RoboDanny)
# Modified work Copyright (c) 2017 Perry Fraser
#
# Licensed under the MIT License. https://opensource.org/licenses/MIT
#
# This copyright template is copied from @iwearapot#5464


import copy
import logging
import random
import sys
import traceback

import discord
from discord.ext import commands

import config
from cogs.utils.config import Config
from cogs.utils.context import Context

description = "I'm a bot that does stuff"

log = logging.getLogger(__name__)

initial_extensions = [
    'cogs.fun',
    'cogs.admin',
    'cogs.meta',
    'cogs.reddit',
    'cogs.github',
    'cogs.mod',
    'cogs.timezone',
    'cogs.info',
    'cogs.other',
    'cogs.discrim',
    'cogs.search',
    'cogs.humanize',
    'cogs.jokes',
    'cogs.bostonlib'
]


def _prefix(bot, msg):
    user_id = bot.user.id

    base = [f'<@{user_id}> ', f'<@!{user_id}> ']

    if msg.guild is None:
        base.append('-')
    else:
        base.extend(bot.prefixes.get(msg.guild.id, ['-']))

    return base


class TorGenius(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=_prefix,
            description=description,
            pm_help=None,
            help_attrs=dict(hidden=True)
        )

        _ = self.is_owner(discord.User)

        self.client_id = config.client_id

        # noinspection SpellCheckingInspection
        self.game_list = ['corn', 'k', 'never gonna...', 'serdeff',
                          'lauye9r v7&^*^*111', 'no', 'no u', 'farts r funny']

        self.add_command(self.do)

        self.prefixes = Config('prefixes.json')

        for extension in initial_extensions:
            # noinspection PyBroadException
            try:
                self.load_extension(extension)
            except Exception:
                print(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send(
                'This command cannot be used in private messages.'
            )
        elif isinstance(error, commands.DisabledCommand):
            await ctx.author.send(
                'Sorry. This command is disabled and cannot be used.'
            )
        elif isinstance(error, commands.CommandInvokeError):
            print(
                f'In {ctx.command.qualified_name}:',
                file=sys.stderr
            )

            traceback.print_tb(error.original.__traceback__)
            print(
                f'{error.original.__class__.__name__}: {error.original}',
                file=sys.stderr
            )

    def get_guild_prefixes(self, guild):
        # top kek (https://github.com/Rapptz/RoboDanny/blob/rewrite/bot.py#L87)
        fake_msg = discord.Object(None)
        fake_msg.guild = guild
        # not sure why lol
        # noinspection PyTypeChecker
        return _prefix(self, fake_msg)

    def get_other_prefixes(self, guild):
        """
        This is just so I can get prefixes that aren't the @bot ones
        """
        guild_id = guild.id
        return self.prefixes.get(guild_id, [';'])

    async def set_guild_prefixes(self, guild, prefixes):
        if len(prefixes) == 0:
            # No prefixes yet
            await self.prefixes.put(guild.id, [])
        elif len(prefixes) >= 10:
            # Why would anyone even do this
            # Should be caught in prefix command
            raise RuntimeError(
                "A server can't have more than 10 custom prefixes."
            )
        else:
            await self.prefixes.put(
                guild.id,
                sorted(set(prefixes), reverse=True)
            )

    async def on_ready(self):
        print(f'Ready: {self.user} (ID: {self.user.id})')

        game = random.choice(self.game_list)

        await self.change_presence(
            game=(discord.Game(name=game))
        )

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)

        if ctx.command is None:
            return

        async with ctx.acquire(ctx, None):
            await self.invoke(ctx)

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)

    def run(self):
        super().run(config.token, reconnect=True)

    @property
    def config(self):
        return __import__('config')

    # Not important, will fix later
    @commands.command(hidden=True, enabled=False)
    @commands.is_owner()
    async def do(self, ctx, times: int, *, command):
        """Repeats a command a specified number of times."""
        msg = copy.copy(ctx.message)
        msg.content = command

        new_ctx = await self.get_context(msg, cls=Context)
        new_ctx.db = ctx.db

        for i in range(times):
            await new_ctx.reinvoke()
