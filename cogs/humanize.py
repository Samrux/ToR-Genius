import humanize
from dateutil.parser import parse
from discord.ext import commands


class Humanize:
    """Some utilities for converting things into nice human format."""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, err):
        if isinstance(err, (ValueError, commands.BadArgument)):
            await ctx.send("Couldn't parse input")

    @commands.group(aliases=['human', 'hu', 'humanise'])
    async def humanize(self, ctx):
        """Human-fy stuff."""
        if ctx.invoked_subcommand is None:
            await ctx.show_help('humanize')

    @humanize.command(aliases=['int', 'i', 'n'])
    async def num(self, ctx, *, val: float):
        """Convert a number into a word-like number."""
        await ctx.send(humanize.intword(val))

    # noinspection SpellCheckingInspection
    @humanize.command(aliases=['intc', 'ic', 'nc'])
    async def numcomma(self, ctx, *, val: float):
        """Comma seperate a number."""
        await ctx.send(humanize.intcomma(val))

    @humanize.command(aliases=['da'])
    async def day(self, ctx, *, val):
        """Convert a data into a day, like "tomorrow"."""
        await ctx.send(humanize.naturalday(parse(val)))

    @humanize.command(aliases=['diff', 'de', 'del'])
    async def delta(self, ctx, *, val):
        """Convert a date into a delta date."""
        try:
            await ctx.send(humanize.naturaldelta(parse(val)))
        except TypeError:
            await ctx.send("Couldn't parse delta.")

    @humanize.command(aliases=['dat'])
    async def date(self, ctx, *, val):
        """Convert a date into a more human readable date"""
        await ctx.send(humanize.naturaldate(parse(val)))

    @humanize.command(aliases=['size'])
    async def filesize(self, ctx, *, val: float):
        """Convert a filesize into a more readable """
        await ctx.send(humanize.naturalsize(val))

    @humanize.command(aliases=['bsize'])
    async def binarysize(self, ctx, *, val: float):
        """Convert a filesize into a more human readable binary filesize"""
        await ctx.send(humanize.naturalsize(val, binary=True))

    # noinspection SpellCheckingInspection
    @humanize.command(aliases=['fraction', 'frac', 'fra'])
    async def fractional(self, ctx, *, val: float):
        """Convert a decimal into a more readable fraction"""
        await ctx.send(humanize.fractional(val))


def setup(bot):
    bot.add_cog(Humanize(bot))
