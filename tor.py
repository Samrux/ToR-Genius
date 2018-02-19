# Original work Copyright (c) 2015 Rapptz (https://github.com/Rapptz/RoboDanny)
# Modified work Copyright (c) 2017 Perry Fraser
#
# Licensed under the MIT License. https://opensource.org/licenses/MIT

import asyncio
import importlib
import logging
import sys
import traceback
from contextlib import contextmanager

import asyncpg
import click

import config
from bot import TorGenius, initial_extensions
from cogs.utils.db import Table


@contextmanager
def setup_logging():
    global log
    try:
        logging.getLogger('discord').setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.WARNING)

        log = logging.getLogger()
        log.setLevel(logging.INFO)
        handler = logging.FileHandler(
            filename='torgenius.log',
            encoding='utf-8',
            mode='w'
        )

        dt_fmt = '%Y-%m-%d %H:%M:%S'
        fmt = logging.Formatter(
            '[{asctime}] [{levelname:<7}] {name}: {message}',
            dt_fmt,
            style='{'
        )
        handler.setFormatter(fmt)
        log.addHandler(handler)

        yield

    finally:
        handlers = log.handlers[:]
        for each_handler in handlers:
            each_handler.close()
            log.removeHandler(each_handler)


def run_bot():
    # who knows at this point
    # noinspection PyShadowingNames
    log = logging.getLogger()
    loop = asyncio.get_event_loop()

    # noinspection PyBroadException
    try:
        pool = loop.run_until_complete(
            asyncpg.create_pool(config.postgresql, command_timeout=60)
        )
    except Exception:
        click.echo('Could not set up PostgreSQL. Exiting.', file=sys.stderr)
        log.exception('Could not set up PostgreSQL. Exiting.')
        return

    bot = TorGenius()
    bot.pool = pool
    bot.run()


@click.group(invoke_without_command=True, options_metavar='[options]')
@click.pass_context
def main(ctx):
    """Launches the bot"""
    if ctx.invoked_subcommand is None:
        with setup_logging():
            run_bot()


@main.group(short_help='database stuff', options_metavar='[options]')
def db():
    pass


@db.command(short_help='initialises the databases for the bot',
            options_metavar='[options]')
@click.argument('cogs', nargs=-1, metavar='[cogs]')
@click.option('-q', '--quiet', help='less verbose output', is_flag=True)
def init(cogs, quiet):
    run = asyncio.get_event_loop().run_until_complete

    # noinspection PyBroadException
    try:
        run(Table.create_pool(config.postgresql))
    except Exception:
        click.echo(
            f'Could not create PostgreSQL connection pool.\n'
            f'{traceback.format_exc()}',
            err=True
        )
        return

    if not cogs:
        cogs = initial_extensions
    else:
        cogs = [f'cogs.{e}' if not e.startswith('cogs.') else e for e in cogs]

    for ext in cogs:
        # noinspection PyBroadException
        try:
            importlib.import_module(ext)
        except Exception:
            click.echo(
                f'Could not load {ext}.\n{traceback.format_exc()}',
                err=True
            )
            return

    for table in Table.all_tables():
        # noinspection PyBroadException
        try:
            run(table.create(verbose=not quiet))
        except Exception:
            click.echo(
                f'Could not create {table.__tablename__}.\n'
                f'{traceback.format_exc()}',
                err=True
            )
        else:
            click.echo(
                f'[{table.__module__}] Created {table.__tablename__}.'
            )


if __name__ == '__main__':
    main()
