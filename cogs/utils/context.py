import asyncio
from collections import namedtuple

import exrex
import raven
from discord.ext import commands

import config


# noinspection PyProtectedMember
class _ContextDBAcquire:
    __slots__ = ('ctx', 'timeout')

    def __init__(self, ctx, timeout):
        self.ctx = ctx
        self.timeout = timeout

    def __await__(self):
        return self.ctx._acquire(self.timeout).__await__()

    async def __aenter__(self):
        await self.ctx._acquire(self.timeout)
        return self.ctx.db

    async def __aexit__(self, *args):
        await self.ctx.release()


class Context(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pool = self.bot.pool
        self.db = None
        self.token = exrex.getone(
            r'([NM][a-zA-Z\d]{23}[.][a-zA-Z\d]{6}[.][a-zA-Z\d]{27})'
        )
        self.sentry = raven.Client(config.sentry)
        self.emojis = namedtuple(
            'Emojis', 'check xmark white_check cross_mark tick_yes') \
            ('<:check:410612082929565696>',
             '<:cross:410612082988285952>',
             '\N{WHITE HEAVY CHECK MARK}',
             '\N{CROSS MARK}',
             '<:tickYes:404815005423501313>')

    async def _acquire(self, timeout):
        if self.db is None:
            self.db = await self.pool.acquire(timeout=timeout)
        return self.db

    @property
    def acquire(self):
        return _ContextDBAcquire

    async def release(self):
        """
        Releases the database connection from the pool.
        Useful if needed for "long" interactive commands where
        we want to release the connection and re-acquire later.
        Otherwise, this is called automatically by the bot.
        """

        if self.db is not None:
            await self.bot.pool.release(self.db)
            self.db = None

    async def auto_react(self, emoji='<:check:410612082929565696>'):
        # noinspection PyBroadException
        try:
            await self.message.add_reaction(emoji.strip('<:>'))
        except:
            # No reaction perms probably
            await self.send(emoji)

    async def show_help(self, command=None):
        """
        Show help for a command
        :param command: String, command name
        :return: None
        """

        cmd = self.bot.get_command('help')
        command = command or self.command.qualified_name
        await self.invoke(cmd, command=command)

    async def run_command(self, command, *args, **kwargs):
        """Run a command from a string"""

        command = self.bot.get_command(command)
        await self.invoke(command, *args, **kwargs)

    async def prompt(self, message, *, timeout=60.0, delete_after=True,
                     reacquire=True, author_id=None, needs_mod=False):
        """An interactive reaction confirmation dialog.
        Parameters
        -----------
        message: str
            The message to show along with the prompt.
        timeout: float
            How long to wait before returning.
        delete_after: bool
            Whether to delete the confirmation message after we're done.
        reacquire: bool
            Whether to release the database connection and then acquire it
            again when we're done.
        author_id: Optional[int]
            The member who should respond to the prompt. Defaults to the author
            of the Context's message.
        needs_mod: bool
            If the person doing the reaction needs mod perms, i.e. for
            something that needs verified
        Returns
        --------
        Optional[bool]
            ``True`` if explicit confirm,
            ``False`` if explicit deny,
            ``None`` if deny due to timeout
        """

        if not self.channel.permissions_for(self.me).add_reactions:
            await self.send(
                'Bot does not have Add Reactions permission.'
            )
            return None

        fmt = f'{message}\n\nReact with {self.emojis.check} to ' \
              f'confirm or {self.emojis.xmark} to deny.'

        author_id = author_id or self.author.id
        msg = await self.send(fmt)

        confirm = None

        def check(reaction, user):
            nonlocal confirm

            # bad bot
            if user.bot:
                return False

            if needs_mod and reaction.message.channel.permissions_for(
                    user).ban_members is False:
                return False

            if reaction.message.id != msg.id:
                if not needs_mod and user.id != author_id:
                    return False

            if str(reaction) == self.emojis.tick_yes:
                confirm = True
                return True
            elif str(reaction) == self.emojis.xmark:
                confirm = False
                return True

            return False

        for emoji in (self.emojis.tick_yes, self.emojis.xmark):
            await msg.add_reaction(emoji.strip('<:>'))

        if reacquire:
            await self.release()

        try:
            await self.bot.wait_for(
                'reaction_add',
                check=check,
                timeout=timeout
            )
        except asyncio.TimeoutError:
            confirm = None

        try:
            if reacquire:
                await self.acquire()

            if delete_after:
                await msg.delete()
        finally:
            return confirm
