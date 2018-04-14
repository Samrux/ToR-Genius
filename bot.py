# Original work Copyright (c) 2015 Rapptz (https://github.com/Rapptz/RoboDanny)
# Modified work Copyright (c) 2017 Perry Fraser
#
# Licensed under the MIT License. https://opensource.org/licenses/MIT
#
# This copyright template is copied from @iwearapot#5464


import asyncio
import datetime
import logging
import random
import re
import sys
import traceback

import discord
import exrex
from discord.ext import commands
from discord.ext.commands.view import StringView

import config
from cogs.utils.config import Config
from cogs.utils.context import Context
from cogs.utils.paginator import CannotPaginate

description = "I'm a bot that does stuff"

log = logging.getLogger(__name__)

initial_extensions = [
    'cogs.fun',
    'cogs.admin',
    'cogs.meta',
    'cogs.mod',
    'cogs.info',
    'cogs.memes',
    'cogs.search',
    'cogs.humanize',
    'cogs.jokes',
    'cogs.custom',
    'cogs.logging',
]


def _prefix(bot, msg):
    user_id = bot.user.id

    base = [f'<@{user_id}> ', f'<@!{user_id}> ']

    if msg.guild is None:
        base.extend(['-', ';', 'tor ', ''])
    else:
        base.extend(bot.prefixes.get(msg.guild.id, ['-']))

    # None of these are regexs
    base = [p if isinstance(p, list) else [p, False] for p in base]

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

        # noinspection SpellCheckingInspection
        self.game_list = ['corn', 'k', 'never gonna...', 'serdeff',
                          'lauye9r v7&^*^*111', 'no', 'no u', 'farts r funny']

        self.token = exrex.getone(
            r'([NM][a-zA-Z\d]{23}[.][a-zA-Z\d]{6}[.][a-zA-Z\d]{27})'
        )

        self.lockdown = {}

        self.prefixes = Config('prefixes.json')

        for extension in initial_extensions:
            # noinspection PyBroadException
            try:
                self.load_extension(extension)
            except Exception:
                print(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()

    # convenience prop
    @property
    def config(self):
        return __import__('config')

    async def on_command_error(self, ctx, error):

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send(
                'This command cannot be used in private messages.'
            )
        elif isinstance(error, commands.DisabledCommand):
            await ctx.author.send(
                'Sorry. This command is disabled and cannot be used.'
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(error)
        elif isinstance(error, commands.TooManyArguments):
            await ctx.send('You passed too many parameters for that command.')
        elif isinstance(error, commands.CommandInvokeError):
            log.warning(f'Command error on command {ctx.command.qualified_name}'
                        f' from {ctx.author}: \n {error.original.__traceback__}'
                        f'.See stdout/err for more details.')
            print(
                f'In {ctx.command.qualified_name}:',
                file=sys.stderr
            )

            traceback.print_tb(error.original.__traceback__)
            print(
                f'{error.original.__class__.__name__}: {error.original}',
                file=sys.stderr
            )
        elif isinstance(error, CannotPaginate):
            await ctx.send(error)
        elif isinstance(error, commands.CheckFailure):
            if self.lockdown.get(ctx.channel, None):
                return
            if ctx.command.name == 'calc':
                return await ctx.send(f'You are not allowed to use this '
                                      f'command. If you want to do some math, '
                                      f'try `{ctx.prefix}quick <question or '
                                      f'math>`.')
            await ctx.send('You are not allowed to use this command.')

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
        elif len(prefixes) >= 40:
            # Why would anyone even do this
            # Should be caught in prefix command
            raise RuntimeError(
                "A server can't have more than 40 custom prefixes."
            )
        else:
            await self.prefixes.put(
                guild.id,
                # maybe a bad idea not to set this anymore. eh.
                sorted(prefixes, reverse=True, key=lambda p: p[0])
            )

    async def on_ready(self):
        print(f'Ready: {self.user} (ID: {self.user.id})')

        if not hasattr(self, 'uptime'):
            # noinspection PyAttributeOutsideInit
            self.uptime = datetime.datetime.now()

        game = random.choice(self.game_list)

        await self.change_presence(
            activity=(discord.Game(name=game))
        )

    async def get_context(self, message, *, cls=Context):
        view = StringView(message.content)
        ctx = cls(prefix=None, view=view, bot=self, message=message)

        if self._skip_check(message.author.id, self.user.id):
            return ctx

        prefix = await self.get_prefix(message)
        invoked_prefix = prefix

        if isinstance(prefix, str):
            if not view.skip_string(prefix):
                return ctx
        elif isinstance(prefix, list) \
                and any([isinstance(p, list) for p in prefix]):
            # Regex time
            for p in prefix:
                if isinstance(p, list):
                    if p[1]:
                        # regex prefix parsing
                        reg = re.match(p[0], message.content)
                        if reg:

                            if message.content == reg.groups()[0]:
                                # ignore * prefixes
                                continue

                            # Matches, this is the prefix
                            invoked_prefix = p

                            # redo the string view with the capture group
                            view = StringView(reg.groups()[0])

                            invoker = view.get_word()
                            ctx.invoked_with = invoker
                            ctx.prefix = invoked_prefix
                            ctx.command = self.all_commands.get(invoker)
                            ctx.view = view
                            return ctx
                    else:
                        # regex has highest priority or something idk
                        # what I'm doing help
                        continue

            # No prefix found, use the branch below
            prefix = [p[0] for p in prefix if not p[1]]
            invoked_prefix = discord.utils.find(view.skip_string, prefix)
            if invoked_prefix is None:
                return ctx
        else:
            invoked_prefix = discord.utils.find(view.skip_string, prefix)
            if invoked_prefix is None:
                return ctx

        invoker = view.get_word()
        ctx.invoked_with = invoker
        ctx.prefix = invoked_prefix
        ctx.command = self.all_commands.get(invoker)
        return ctx

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)

        if ctx.command is None:
            if "just monika" in message.content.lower():
                await ctx.send('Just Monika')
            elif message.content == 'neat':
                await ctx.send('neat')
            return

        async with ctx.acquire(ctx, None):
            await self.invoke(ctx)

    async def get_prefix(self, message):
        prefix = ret = self.command_prefix
        if callable(prefix):
            ret = prefix(self, message)
            if asyncio.iscoroutine(ret):
                ret = await ret

        return ret

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)

    def run(self):
        super().run(config.token, reconnect=True)

    # ur face is a redeclaration
    # noinspection PyRedeclaration
    @property
    def config(self):
        return __import__('config')

