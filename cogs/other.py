import io
import re
import textwrap
from math import floor

import aiohttp
import discord
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands

from cogs.utils.paginator import Pages


Black = (0, 0, 0)
White = (255, 255, 255)

# from https://stackoverflow.com/questions/169625/regex-to-check-if-valid-url-that-ends-in-jpg-png-or-gif
imageurl = r'<?(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*\.(?:jpg|png|jpeg))(?:\?([^#]*))?(?:#(.*))?>?'
reimageurl = re.compile(imageurl, re.IGNORECASE)


async def download(url):
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as r:
            return io.BytesIO(await r.read())


def imgbio(img):
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio


def getimgname(url):
    match = re.findall(r'[^/]+(?:png|jpg|jpeg)/?$', url)  # Finds URL end
    match = re.sub(r'\.[^.]+/?$', '', match[0]) if match else 'Image'  # Removes file extension
    return match


def place_centered_text(text, pos, draw, font, wrap, color):
    x, y = pos
    lines = textwrap.wrap(text, width=wrap)
    y -= sum(font.getsize(l)[1] for l in lines) // 2

    for line in lines:
        width, height = font.getsize(line)
        x = pos[0] - width // 2
        draw.text((x, y), line, font=font, fill=color)
        y += height


def place_centered_image(img, pos, base, size=None, rotation=None):
    x, y = pos
    w, h = size

    if size is not None:
        img = img.resize(size)
    if rotation is not None:
        img = img.rotate(rotation, expand=True)
    base.paste(img, (x - w//2, y - h//2), img)


def place_centered_content(content, pos,
                           draw, txtfont, txtwrap, txtcolor,
                           base, imgsize=None, imgrotation=None):
    if isinstance(content, str):
        place_centered_text(content, pos, draw, txtfont, txtwrap, txtcolor)
    else:
        place_centered_image(content, pos, base, imgsize, imgrotation)


# Image link, user avatar, or text
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
            return Image.open(img).convert('RGBA')

        # Text
        else:
            return argument


class Other:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, err):
        if isinstance(err, commands.BadArgument):
            await ctx.send(err)

    @commands.command()
    async def forum(self, ctx, *, search):
        """Search the Swift Discourse Forum for anything."""
        with aiohttp.ClientSession() as s:
            async with s.get(
                    'https://forums.swift.org/search/query.json',
                    params={'term': search}
            ) as r:
                r = await r.json()

                if r['grouped_search_result'] is None:
                    return await ctx.send('No results found.')

                data = []

                # I'm sorry. (Ok not as bad now)

                # idk why, but topics seems to disappear sometimes
                data.extend([(f't/{t["id"]}', t['title'])
                             for t in r.get('topics', [])])

                data.extend([(f'u/{u["username"]}',
                              f'{u["username"]} ({u["name"]})')
                             for u in r['users']])

                data.extend([(f'c/{c.id}', c['name'])
                             for c in r['categories']])

                data.extend([(f'tags/{t["name"]}', t['name'])
                             for t in r['tags']])

                data.extend([(f'p/{p["id"]}', p['blurb'])
                             for p in r['posts']])

                if not data:
                    return await ctx.send('No results found.')

                p = Pages(
                    ctx,
                    entries=[f'[{d[1]}](https://forums.swift.org/{d[0]})'
                             for d in data]
                )

                await p.paginate()

    @commands.command()
    async def blame(self, ctx, *, user=None):
        """Blame a person. Defaults to perryprog"""
        # Hardcoded because I want to be blamed even in forks ;)
        name = (getimgname(user) if re.fullmatch(reimageurl, user) else user) if user else 'perry'
        user = await RichArgument().convert(ctx, user or '280001404020588544')

        if isinstance(user, str):
            return await ctx.send('Invalid username or image URL')

        # :no_entry: emoji
        emoji = 'https://emojipedia-us.s3.amazonaws.com/thumbs/240/twitter/' \
                '120/no-entry-sign_1f6ab.png'
        emoji = await download(emoji)
        emoji = Image.open(emoji)
        emoji = emoji.convert('RGBA')

        # make the image 3 times larger than the avatar
        large_image = Image.new('RGBA', [3 * x for x in user.size], (0,) * 4)
        lW, lH = large_image.size
        W, H = user.size
        # the center box for the avatar
        box = (W, H, W * 2, H * 2)

        # make the emoji 20% bigger than the avatar
        emoji = emoji.resize([floor(x * 1.2) for x in user.size])
        eW, eH = emoji.size

        large_image.paste(user.copy(), box)
        large_image.paste(
            emoji,

            (  # center the emoji
                floor((lW - eW) / 2),

                floor((lH - eH) / 2)
            ),

            emoji
        )

        # make the font size relative to the avatar size
        font = ImageFont.truetype('Arial.ttf', floor(user.size[0] / 4))
        draw = ImageDraw.Draw(large_image)

        message = f'#blame{name}'
        tW, tH = draw.textsize(message, font)

        draw.text(
            (  # center the text
                floor((lW - tW) / 2),
                # make the text somewhat centered (a bit offset so it
                # looks good) in the first "row"
                floor(H / 2) - floor(W / 4)
            ),
            message, font=font, fill=(255,)*4
        )

        await ctx.send(file=discord.File(imgbio(large_image), filename='blame.png'))

    @commands.command(aliases=['thefloor', 'the_floor'])
    async def floor(self, ctx, person: RichArgument, *, thefloor):
        """Generate a the floor is lava meme"""

        meme = Image.open('memes/floor.png')
        font = ImageFont.truetype('Arial.ttf', 30)
        draw = ImageDraw.Draw(meme)

        # Floor is
        place_centered_text("The floor is " + thefloor, (340, 70), draw, font, 70, Black)

        # Person's head
        pos = ((150, 145), (480, 160))
        size = ((20, 20), (40, 40))
        for i in range(2):
            if isinstance(person, str):
                place_centered_text(person, pos[i], draw, font, 20, Black)
            else:
                place_centered_image(person, pos[i], meme, size[i])

        await ctx.send(file=discord.File(imgbio(meme), filename='floor.png'))

    @commands.command(aliases=['highway'])
    async def car(self, ctx, driver: RichArgument,
                  first_option: RichArgument, second_option: RichArgument):
        """Generate a highway exit meme. Use quotes for sentences"""

        meme = Image.open('memes/highway.jpg')
        font = ImageFont.truetype('Arial.ttf', 22)
        draw = ImageDraw.Draw(meme)

        pos = ((365, 465), (210, 150), (420, 150))
        place_centered_content(driver, pos[0], draw, font, 25, White, meme, (50, 50))
        place_centered_content(first_option, pos[1], draw, font, 9, White, meme, (100, 100))
        place_centered_content(second_option, pos[2], draw, font, 12, White, meme, (120, 120))

        await ctx.send(file=discord.File(imgbio(meme), filename='car.png'))

    @commands.command()
    async def wheeze(self, ctx, *, thing: RichArgument):
        """Generate a wheeze meme"""

        meme = Image.open('memes/wheeze.png')
        draw = ImageDraw.Draw(meme)
        font = ImageFont.truetype('Arial.ttf', 20)

        place_centered_content(thing, (90, 490), draw, font, 18, Black, meme, (100, 100))

        await ctx.send(file=discord.File(imgbio(meme), filename='wheeze.png'))

    # noinspection PyUnresolvedReferences
    @commands.command(aliases=['garbage'])
    async def trash(self, ctx, person: RichArgument, *, trash: RichArgument):
        """Generate a taking out the trash meme."""

        meme = Image.open('memes/garbage.jpg').convert('RGBA')
        font = ImageFont.truetype('Arial.ttf', 50)
        draw = ImageDraw.Draw(meme)

        pos = ((485, 90 if isinstance(person, str) else 165), (780, 300))
        place_centered_content(person, pos[0], draw, font, 10, (0, 0, 255), meme, (200, 200), 20)
        place_centered_content(trash, pos[1], draw, font, 15, Black, meme, (250, 250), -10)

        await ctx.send(file=discord.File(imgbio(meme), filename='trash.png'))

    @commands.command()
    async def captcha(self, ctx, img, *, message=None):
        """Generate a select all <blank>"""

        message = message or (getimgname(img) if re.fullmatch(reimageurl, img) else img)
        img = await RichArgument().convert(ctx, img)

        if isinstance(img, str):
            return await ctx.send('Invalid username or image URL')

        meme = Image.open('memes/captcha.png')

        # == Images ==
        img = img.resize((129, 129))
        for x_mul in range(3):
            for y_mul in range(3):
                meme.paste(img, (27 + 129 * x_mul, 173 + 129 * y_mul))

        # == Text ==
        font = ImageFont.truetype('Arial.ttf', 30)
        draw = ImageDraw.Draw(meme)
        draw.text((51, 90), message, font=font, fill=White)

        await ctx.send(file=discord.File(imgbio(meme), filename='captcha.png'))

    @commands.command('spam')
    async def who_did_this(self, ctx, search=3):
        """Find out who spammed a help command.

        Specifically for the dbots server.

        Search is how far to go before hitting a bot."""
        final_results = []

        async for m in ctx.channel.history(limit=search):
            if m.author.bot:
                # We probably found the end of the train
                async for bot_m in ctx.channel.history(before=m):
                    if not bot_m.author.bot:
                        # Start of the train
                        final_results.append((bot_m.author, bot_m.content))
                        async for others_m in ctx.channel.history(
                                limit=5, before=bot_m
                        ):
                            final_results.append(
                                (others_m.author, others_m.content)
                            )
                            return await ctx.send(
                                '\n'.join(
                                    f'**{r[0].display_name}:** {r[1]}'
                                    for r in final_results
                                )
                            )


def setup(bot):
    bot.add_cog(Other(bot))
