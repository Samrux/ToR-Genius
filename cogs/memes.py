import io
import re
import textwrap
from math import floor

import aiohttp
import discord
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands


# from https://stackoverflow.com/questions/169625/regex-to-check-if-valid-url-that-ends-in-jpg-png-or-gif
imageurl = r'<?(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*\.(?:jpg|png|jpeg))(?:\?([^#]*))?(?:#(.*))?>?'
reimageurl = re.compile(imageurl, re.IGNORECASE)


async def download(url):
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as r:
            return io.BytesIO(await r.read())


async def place_centered(content, image, draw, font, pos, wrap, color, imgsize=None, imgrot=None):
    x, y = pos

    if isinstance(content, str):
        print('whee')
        lines = textwrap.wrap(content, width=wrap)
        y -= sum(font.getsize(l)[1] for l in lines) // 2

        for line in lines:
            width, height = font.getsize(line)
            x -= width // 2
            draw.text((x, y), line, font=font, fill=color)
            y += height

    else:
        if imgsize is not None:
            content = content.resize(imgsize)
        if imgrot is not None:
            content = content.rotate(imgrot, expand=True)
        image.paste(content, (x-imgsize[0]//2, y-imgsize[1]//2))


# Image link, username as avatar, or text
class RichArgument(commands.Converter):
    async def convert(self, ctx, argument):
        # Avatar
        try:
            possible_member = await commands.MemberConverter().convert(ctx, argument)
            url = possible_member.avatar_url_as(format='png')
            url = url.replace('gif', 'png').strip('<>')
            img = await download(url)
            return Image.open(img).convert('RGBA')

        except commands.BadArgument:
            pass

        # Image
        if re.fullmatch(reimageurl, argument):
            img = await download(argument.strip('<>'))
            img = Image.open(img)

            return img.convert('RGBA')

        # Text
        else:
            return argument


class Memes:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, err):
        if isinstance(err, commands.BadArgument):
            await ctx.send(err)

    # noinspection PyUnresolvedReferences,PyPep8Naming
    @commands.command()
    async def blame(self, ctx, *, arg: RichArgument = None):
        """Blame everyone! Defaults to perryprog.

        Will also accept image urls ending in jpg, png, and jpeg."""
        # hardcoded because I want to be blamed even in forks ;)
        arg, name = arg or await RichArgument.convert(ctx, '280001404020588544')
        # special cases for usernames
        special_cases = {
            'perryprog': 'perry',
            'itsthejoker': 'joker'
        }

        # :no_entry: emoji
        emoji = 'https://emojipedia-us.s3.amazonaws.com/thumbs/240/twitter/' \
                '120/no-entry-sign_1f6ab.png'
        emoji = await download(emoji)
        emoji = Image.open(emoji)
        emoji = emoji.convert('RGBA')

        # make the image 3 times larger than the avatar
        large_image = Image.new('RGBA', [3 * x for x in arg.size], (0,) * 4)
        lW, lH = large_image.size
        W, H = arg.size
        # the center box for the avatar
        box = (W, H, W * 2, H * 2)

        # make the emoji 20% bigger than the avatar
        emoji = emoji.resize([floor(x * 1.2) for x in arg.size])
        eW, eH = emoji.size

        large_image.paste(arg.copy(), box)
        large_image.paste(
            emoji,

            (  # center the emoji
                floor((lW - eW) / 2),

                floor((lH - eH) / 2)
            ),

            emoji
        )

        # make the font size relative to the avatar size
        fnt = ImageFont.truetype('Arial.ttf', floor(arg.size[0] / 4))
        d = ImageDraw.Draw(large_image)

        name = special_cases.get(
            name,
            re.sub(r'\W', '', name).lower()
        )

        message = f'#blame{name}'
        tW, tH = d.textsize(message, fnt)

        d.text(
            (  # center the text
                floor((lW - tW) / 2),
                # make the text somewhat centered (a bit offset so it
                # looks good) in the first "row"
                floor(H / 2) - floor(W / 4)
            ),
            message,
            font=fnt,
            fill=(255,) * 4
        )

        bio = io.BytesIO()
        large_image.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='blame.png'))

    # noinspection PyPep8Naming,PyUnresolvedReferences
    @commands.command(aliases=['thefloor', 'the_floor'])
    async def floor(self, ctx, person: RichArgument, *, thefloor):
        """Generate a the floor is lava meme"""

        meme = Image.open('memes/floor.png')
        font = ImageFont.truetype('Arial.ttf', 30)
        draw = ImageDraw.Draw(meme)

        place_centered(thefloor, meme, draw, font, 200, 25, 65, (0,)*3)

        # == Avatars ==
        first = person.resize((20, 20))
        second = person.resize((40, 40))
        meme.paste(first, (143, 135))
        meme.paste(second, (465, 133))

        # == Sending ==
        bio = io.BytesIO()
        meme.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='floor.png'))

    @commands.command(aliases=['highway'])
    async def car(self, ctx, driver: RichArgument, first_option, second_option):
        """Generate a highway exit meme. Use quotes for sentences"""

        meme = Image.open('memes/highway.jpg')
        font = ImageFont.truetype('Arial.ttf', 22)
        draw = ImageDraw.Draw(meme)
        color = (255, 255, 255)

        place_centered(first_option, meme, draw, font, (210, 150), 9, color)
        place_centered(second_option, meme, draw, font, (420, 150), 12, color)
        place_centered(driver, meme, draw, font, (365, 465), 25, color, (50, 50))

        # == Sending ==
        bio = io.BytesIO()
        meme.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='car.png'))

    @commands.command()
    async def wheeze(self, ctx, *, message: str):
        """Generate a wheeze meme."""

        meme = Image.open('memes/wheeze.png')
        draw = ImageDraw.Draw(meme)
        font = ImageFont.truetype('Arial.ttf', 20)

        draw.text((34, 483), message, font=font, fill=(0, 0, 0))

        # == Sending ==
        bio = io.BytesIO()
        meme.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='wheeze.png'))

    # noinspection PyUnresolvedReferences
    @commands.command(aliases=['garbage'])
    async def trash(self, ctx, first: RichArgument, *, second: RichArgument):
        """Generate a taking out the trash meme."""

        meme = Image.open('memes/garbage.jpg').convert('RGBA')
        font = ImageFont.truetype('Arial.ttf', 50)
        draw = ImageDraw.Draw(meme)

        place_centered(first, meme, draw, font, (485, 65), 10, (255, 255, 255), (180, 180), 20)
        place_centered(second, meme, draw, font, (780, 290), 10, (0, 0, 0), (250, 250), -10)

        # == Sending ==
        bio = io.BytesIO()
        meme.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='trash.png'))

    @commands.command()
    async def captcha(self, ctx, img: RichArgument, *, message=None):
        """Generate a select all <blank>"""

        img, name = img
        name = re.sub(r'\W', '', name).lower()
        name = message or name

        meme = Image.open('memes/captcha.png')

        # == Images ==
        img = img.resize((129, 129))

        for x_mul in range(3):
            for y_mul in range(3):
                meme.paste(img, (27 + 129 * x_mul, 173 + 129 * y_mul))

        # == Text ==
        fnt = ImageFont.truetype('Arial.ttf', 30)
        d = ImageDraw.Draw(meme)

        d.text((51, 90), name, font=fnt, fill=(255,) * 3)

        # == Sending ==
        bio = io.BytesIO()
        meme.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='captcha.png'))


def setup(bot):
    bot.add_cog(Memes(bot))

