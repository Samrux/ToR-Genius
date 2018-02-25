# Original work Copyright (c) 2015 Rapptz (https://github.com/Rapptz/RoboDanny)
# Original work Copyright (c) 2017 khazhyk (https://github.com/khazhyk/dango.py)
# Modified work Copyright (c) 2017 Perry Fraser
#
# Licensed under the MIT License. https://opensource.org/licenses/MIT

# All of Admin class except for some formatting and other small details
# from R. Danny

# sh command and run_subprocess from dango.py

import asyncio
import collections
import copy
import datetime
import inspect
import io
import random
import subprocess
import textwrap
import time
import traceback
from contextlib import redirect_stdout

import aiohttp
import discord
from discord.ext import commands
from texttable import Texttable

from cogs.utils.context import Context


async def run_subprocess(cmd, loop=None):
    # https://github.com/khazhyk/dango.py/blob/master/plugins/common/utils.py#L45-L55
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        res = await proc.communicate()
    except NotImplementedError:
        loop = loop or asyncio.get_event_loop()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        res = await loop.run_in_executor(None, proc.communicate)
    return [s.decode('utf8') for s in res]


async def haste_upload(text):
    text = str(text)
    with aiohttp.ClientSession() as session:
        async with session.post('https://hastebin.com/documents/', data=text,
                                headers={'Content-Type': 'text/plain'}) as r:
            r = await r.json()
            return f'https://hastebin.com/{r["key"]}'


async def gist_upload(files, public=False, description=''):
    description = str(description)
    data = {
        'description': description,
        'public': public,
        'files': files
    }
    with aiohttp.ClientSession() as session:
        async with session.post('https://api.github.com/gists', json=data) as r:
            json = await r.json()
            return json['html_url']


class Admin:
    """Admin only commands for the PWNZ"""

    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
        self.sessions = set()
        self.messages = {}

        # The following is for the new repl
        self.repl_sessions = {}
        self.repl_embeds = {}

    @staticmethod
    def cleanup_code(content):
        """
        Automatically removes code blocks from the code. This is for when
        using the eval stuff, you type in a code block, and it removes it for
        you. Magic!
        """
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    async def on_message_edit(self, before, after):
        # Thanks 『 ᴺᵉᵏᵒ 』#0001 for the idea

        result = self.messages.get(before.id)
        if not result:
            return

        trigger, resp = result
        await resp.delete()
        await self.bot.process_commands(after)

    async def send_response(self, ctx, content, inp, extra=None,
                            file_type='py', raw=False):

        if extra:
            self._last_result = extra

        content = str(content) if content is not None else None
        inp = str(inp) if inp is not None else None
        extra = str(extra) if extra is not None else None

        if extra is None:
            if content:
                try:
                    m = await ctx.send(
                        content if raw else f'```{file_type}\n{content}\n```'
                    )
                    self.messages[ctx.message.id] = (ctx.message, m)
                except discord.HTTPException:
                    key = await gist_upload(
                        {f'in.{file_type}': {'content': inp},
                         f'out.{file_type}': {'content': content}})
                    m = await ctx.send(key)
                    self.messages[ctx.message.id] = (ctx.message, m)

        else:
            try:
                m = await ctx.send(
                    content if raw else f'```{file_type}\n{content}{extra}\n```'
                )
                self.messages[ctx.message.id] = (ctx.message, m)
            except discord.HTTPException:
                key = await gist_upload(
                    {f'in.{file_type}': {'content': inp},
                     f'out.{file_type}': {'content': content + extra}})
                m = await ctx.send(key)
                self.messages[ctx.message.id] = (ctx.message, m)

    async def __local_check(self, ctx):
        k = await self.bot.is_owner(ctx.author)
        return k

    @staticmethod
    def get_syntax_error(e):
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}:' \
               f' {e}```'

    @commands.command()
    async def sh(self, ctx, *, cmd):
        # https://github.com/khazhyk/dango.py/blob/master/plugins/debug.py#L144-L153
        await ctx.channel.trigger_typing()
        sout, serr = await run_subprocess(cmd)

        out = ''

        if sout:
            out = f'Stdout: ```{sout}```'

        if serr:
            out = f'Stderr: ```{serr}```\n\n\n' + out

        await self.send_response(ctx, out, cmd, file_type='sh', raw=True)

    @commands.command(hidden=True)
    async def load(self, ctx, *, module):
        """Loads a module."""
        # noinspection PyBroadException
        try:
            self.bot.load_extension(module)
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.auto_react()

    @commands.command(hidden=True)
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        # noinspection PyBroadException
        try:
            self.bot.unload_extension(module)
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.auto_react()

    @commands.command(name='reload', hidden=True, aliases=['r'])
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        if not module.startswith('cogs.'):
            module = f'cogs.{module}'

        # noinspection PyBroadException
        try:
            self.bot.unload_extension(module)
            self.bot.load_extension(module)
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.auto_react()

    @staticmethod
    def format_error(err):
        if not err.text:
            return f'```py\n{err.__class__.__name__}: {err}\n```'

        return f'```py\n{err.text}{"↑":>{err.offset}}\n{type(err).__name__}:' \
               f' {err}```'

    @commands.command(pass_context=True, name='eval')
    async def _eval(self, ctx, *, body: str):
        """Evaluates some code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await self.send_response(
                ctx, self.format_error(e), None, raw=True
            )

        func = env['func']
        # noinspection PyBroadException
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await self.send_response(
                ctx, value, to_compile, extra=traceback.format_exc()
            )
        else:
            value = stdout.getvalue()
            # noinspection PyBroadException
            try:
                await ctx.auto_react(ctx.emojis.check)
            except BaseException:
                pass

            await self.send_response(ctx, value, to_compile, extra=ret)

    @commands.command(pass_context=True)
    async def calc(self, ctx, *, body: str):
        """Evaluates some code with sympy imported"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        body = body.splitlines()
        body[-1] = f'return {body[-1]}'
        body = '\n'.join(body)

        stdout = io.StringIO()

        to_compile = f'from sympy.abc import *\nfrom sympy import *\n' \
                     f'async def func():\n{textwrap.indent(body, "  ")}'

        # noinspection PyBroadException
        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await self.send_response(
                ctx, self.format_error(e), None, raw=True
            )

        func = env['func']
        # noinspection PyBroadException
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await self.send_response(
                ctx, value, to_compile, extra=traceback.format_exc()
            )
        else:
            value = stdout.getvalue()
            # noinspection PyBroadException
            try:
                await ctx.auto_react(ctx.emojis.check)
            except:
                pass

            await self.send_response(ctx, value, to_compile, extra=ret)

    @commands.command(pass_context=True, hidden=True)
    async def old_repl(self, ctx):
        """Launches an interactive REPL session."""
        variables = {
            'ctx': ctx,
            'bot': self.bot,
            'message': ctx.message,
            'guild': ctx.guild,
            'channel': ctx.channel,
            'author': ctx.author,
            '_': None,
        }

        if ctx.channel.id in self.sessions:
            await ctx.send(
                'Already running a REPL session in this channel.'
                ' Exit it with `quit`.'
            )
            return

        self.sessions.add(ctx.channel.id)
        await ctx.send(
            'Enter code to execute or evaluate. `exit()` or `quit` to exit.'
        )

        def check(m):
            return m.author.id == ctx.author.id and \
                   m.channel.id == ctx.channel.id and \
                   m.content.startswith('`')

        while True:
            try:
                response = await self.bot.wait_for('message', check=check,
                                                   timeout=10.0 * 60.0)
            except asyncio.TimeoutError:
                await ctx.send('Exiting REPL session.')
                self.sessions.remove(ctx.channel.id)
                break

            cleaned = self.cleanup_code(response.content)

            if cleaned in ('quit', 'exit', 'exit()', 'stop', 'stop()'):
                await ctx.send('Exiting.')
                self.sessions.remove(ctx.channel.id)
                return

            executor = exec
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as e:
                    await ctx.send(self.get_syntax_error(e))
                    continue

            variables['message'] = response

            fmt = None
            stdout = io.StringIO()

            # noinspection PyBroadException
            try:
                with redirect_stdout(stdout):
                    # noinspection PyUnboundLocalVariable
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
            except Exception:
                value = stdout.getvalue()
                fmt = f'```py\n{value}{traceback.format_exc()}\n```'
            else:
                value = stdout.getvalue()
                if result is not None:
                    fmt = f'```py\n{value}{result}\n```'
                    variables['_'] = result
                elif value:
                    fmt = f'```py\n{value}\n```'

            try:
                if fmt is not None:
                    if len(fmt) > 2000:
                        await ctx.send('Content too big to be printed.')
                    else:
                        await ctx.send(fmt)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await ctx.send(f'Unexpected error: `{e}`')

    @commands.command()
    async def explode(self, ctx):
        await ctx.auto_react()
        await ctx.bot.logout()

    @commands.command(hidden=True)
    async def game(self, ctx, *, game: str = None):
        game = game if game else random.choice(self.bot.game_list)

        if game != 'NONE':
            await self.bot.change_presence(
                game=discord.Game(name=game)
            )
        else:
            await self.bot.change_presence(
                game=None
            )

        await ctx.auto_react()

    @commands.command()
    async def setname(self, ctx, *, nick: str):
        await ctx.guild.me.edit(nick=nick)
        await ctx.auto_react()
        
    @commands.command()
    async def setavatar(self, ctx, *, file: str):
        with open(file, 'rb') as f:
            await self.bot.user.edit(avatar = f.read())


    # from
    # https://github.com/khazhyk/dango.py/blob/master/plugins/debug.py#L155-L166
    @commands.command(name="as")
    async def _as(self, ctx, who: commands.MemberConverter, *, cmd):
        """Run a command impersonating another user."""
        fake_msg = copy.copy(ctx.message)

        # noinspection PyProtectedMember
        fake_msg._update(
            ctx.message.channel,
            dict(
                content=ctx.prefix + cmd
            )
        )
        fake_msg.author = who

        new_ctx = await self.bot.get_context(fake_msg, cls=Context)

        async with new_ctx.acquire(new_ctx, None):
            await self.bot.invoke(new_ctx)

    # the following code is used with permissions from ry00001#3487.
    # https://github.com/ry00001/Erio/blob/master/extensions/eshell.py
    # (modified)
    @commands.group(invoke_without_command=True, hidden=True)
    async def repl(self, ctx, *, name: str = None):
        """New stylish repl command"""
        session = ctx.message.channel.id

        embed = discord.Embed(
            description="_Enter code to execute or evaluate. "
                        "`exit()` or `quit` to exit._",
            timestamp=datetime.datetime.now())

        embed.set_footer(
            text="Interactive Python Shell",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb"
                     "/c/c3/Python-logo-notext.svg/1024px-Python-logo-notext"
                     ".svg.png")

        if name is not None:
            embed.title = name.strip(" ")

        history = collections.OrderedDict()

        variables = {
            'ctx': ctx,
            'bot': self.bot,
            'message': ctx.message,
            'guild': ctx.message.guild,
            'channel': ctx.message.channel,
            'author': ctx.message.author,
            'discord': discord,
            '_': None
        }

        if session in self.repl_sessions:
            return await ctx.send('There already is a repl in this channel.')

        shell = await ctx.send(embed=embed)

        self.repl_sessions[session] = shell
        self.repl_embeds[shell] = embed

        while True:
            response = await self.bot.wait_for(
                'message',
                # formatting hard
                check=lambda m: m.content.startswith(
                    '`') and m.author == ctx.author and m.channel == ctx.channel
            )

            cleaned = self.cleanup_code(response.content)
            shell = self.repl_sessions[session]

            # Regular Bot Method
            try:
                await ctx.message.channel.get_message(
                    self.repl_sessions[session].id)
            except discord.NotFound:
                new_shell = await ctx.send(embed=self.repl_embeds[shell])
                self.repl_sessions[session] = new_shell

                embed = self.repl_embeds[shell]
                del self.repl_embeds[shell]
                self.repl_embeds[new_shell] = embed

                shell = self.repl_sessions[session]

            try:
                await response.delete()
            except discord.Forbidden:
                pass

            if len(self.repl_embeds[shell].fields) >= 7:
                self.repl_embeds[shell].remove_field(0)

            if cleaned in ('quit', 'exit', 'exit()', 'stop', 'stop()'):
                self.repl_embeds[shell].color = 16426522

                if self.repl_embeds[shell].title is not discord.Embed.Empty:
                    history_string = "History for {}\n\n\n".format(
                        self.repl_embeds[shell].title)
                else:
                    history_string = "History for latest session\n\n\n"

                for item in history.keys():
                    history_string += ">>> {}\n{}\n\n".format(
                        item,
                        history[item])

                haste_url = await haste_upload(history_string)
                return_msg = f"[`Leaving shell session. History hosted on " \
                             f"hastebin.`]({haste_url}) "

                self.repl_embeds[shell].add_field(
                    name="`>>> {}`".format(cleaned),
                    value=return_msg,
                    inline=False)

                await self.repl_sessions[session].edit(
                    embed=self.repl_embeds[shell])

                del self.repl_embeds[shell]
                del self.repl_sessions[session]
                return

            executor = exec
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as err:
                    self.repl_embeds[shell].color = 15746887

                    return_msg = self.get_syntax_error(err)

                    history[cleaned] = return_msg

                    if len(cleaned) > 800:
                        cleaned = "<Too big to be printed>"
                    if len(return_msg) > 800:
                        haste_url = await haste_upload(return_msg)
                        return_msg = f'[`SyntaxError too big to be printed. ' \
                                     f'Hosted on hastebin.`]({haste_url}) '

                    self.repl_embeds[shell].add_field(
                        name="`>>> {}`".format(cleaned),
                        value=return_msg,
                        inline=False)

                    await self.repl_sessions[session].edit(
                        embed=self.repl_embeds[shell])
                    continue

            variables['message'] = response

            fmt = None
            stdout = io.StringIO()

            # noinspection PyBroadException
            try:
                with redirect_stdout(stdout):
                    # probably fine
                    # noinspection PyUnboundLocalVariable
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
            except Exception:
                self.repl_embeds[shell].color = 15746887
                value = stdout.getvalue()
                fmt = '```py\n{}{}\n```'.format(
                    value,
                    traceback.format_exc())
            else:
                self.repl_embeds[shell].color = 4437377

                value = stdout.getvalue()

                if result is not None:
                    fmt = '```py\n{}{}\n```'.format(
                        value,
                        result)

                    variables['_'] = result
                elif value:
                    fmt = '```py\n{}\n```'.format(value)

            history[cleaned] = fmt

            if len(cleaned) > 800:
                cleaned = "<Too big to be printed>"

            try:
                if fmt is not None:
                    if len(fmt) >= 800:
                        haste_url = await haste_upload(fmt)
                        self.repl_embeds[shell].add_field(
                            name="`>>> {}`".format(cleaned),
                            value=f"[`Content too big to be printed. Hosted "
                                  f"on hastebin.`]({haste_url})",
                            inline=False)

                        await self.repl_sessions[session].edit(
                            embed=self.repl_embeds[shell])
                    else:
                        self.repl_embeds[shell].add_field(
                            name="`>>> {}`".format(cleaned),
                            value=fmt,
                            inline=False)

                        await self.repl_sessions[session].edit(
                            embed=self.repl_embeds[shell])
                else:
                    self.repl_embeds[shell].add_field(
                        name="`>>> {}`".format(cleaned),
                        value="_`No response`_",
                        inline=False)

                    await self.repl_sessions[session].edit(
                        embed=self.repl_embeds[shell])

            except discord.Forbidden:
                pass

            except discord.HTTPException as err:
                error_embed = discord.Embed(
                    color=15746887,
                    description='**Error**: _{}_'.format(err))
                await ctx.send(embed=error_embed)

    @repl.command(name='jump', aliases=['pull', 'r', 'reload'])
    async def repl_jump(self, ctx):
        """Brings the shell back down so you can see it again."""

        session = ctx.message.channel.id

        if session not in self.repl_sessions:
            return await ctx.send("No shell running in the channel.")

        shell = self.repl_sessions[session]
        embed = self.repl_embeds[shell]

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        try:
            await shell.delete()
        except discord.errors.NotFound:
            pass
        new_shell = await ctx.send(embed=embed)

        self.repl_sessions[session] = new_shell

        del self.repl_embeds[shell]
        self.repl_embeds[new_shell] = embed

    @repl.command(name='clear', aliases=['clean', 'purge'])
    async def repl_clear(self, ctx):
        """Clears the fields of the shell and resets the color."""

        session = ctx.message.channel.id

        if session not in self.repl_sessions:
            return await ctx.send("No shell running in the channel.")

        shell = self.repl_sessions[session]

        self.repl_embeds[shell].color = discord.Color.default()
        self.repl_embeds[shell].clear_fields()

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await shell.edit(embed=self.repl_embeds[shell])

    @commands.command(hidden=True)
    async def sql(self, ctx, *, query: str):
        """Run some SQL."""
        # the imports are here because I imagine some people would want to use
        # this cog as a base for their other cog, and since this one is kinda
        # odd and unnecessary for most people, I will make it easy to remove
        # for those people.
        query = self.cleanup_code(query)

        is_multistatement = query.count(';') > 1
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = ctx.db.execute
        else:
            strategy = ctx.db.fetch

        # noinspection PyBroadException
        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multistatement or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`')

        data = [list(results[0].keys())]
        data.extend([list(r.values()) for r in results])
        table = Texttable()
        table.set_cols_dtype(['t'] * len(data[0]))
        table.add_rows(data)
        render = table.draw()

        fmt = f'```\n{render}\n```\n*Returned {Plural(row=rows)} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            await ctx.send((await haste_upload(fmt)))
        else:
            await ctx.send(fmt)


class Plural:
    def __init__(self, **attr):
        iterator = attr.items()
        self.name, self.value = next(iter(iterator))

    def __str__(self):
        v = self.value
        if v == 0 or v > 1:
            return f'{v} {self.name}s'
        return f'{v} {self.name}'


def setup(bot):
    bot.add_cog(Admin(bot))
    
