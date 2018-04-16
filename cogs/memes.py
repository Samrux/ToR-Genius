import io
import re
import textwrap
from math import floor

import aiohttp
import discord
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands


# Meme commands improved by Samrux :)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)

# from https://stackoverflow.com/questions/169625/regex-to-check-if-valid-url-that-ends-in-jpg-png-or-gif
image_url = re.compile(
    r'<?(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*\.(?:jpg|png|jpeg))(?:\?([^#]*))?(?:#(.*))?>?',
    re.IGNORECASE
)


async def download(url):
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as r:
            return io.BytesIO(await r.read())


def img_bio(img):
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio


def get_img_name(url):
    match = re.findall(r'[^/]+(?:png|jpg|jpeg)/?', url)  # Finds URL end
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
        if re.fullmatch(image_url, argument):
            img = await download(argument.strip('<>'))
            return Image.open(img).convert('RGBA')

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

    @commands.command()
    async def blame(self, ctx, *, user=None):
        """Blame a person. Defaults to this bot's original author perryprog"""
        # Hardcoded because I want to be blamed even in forks ;)
        name = (get_img_name(user) if re.fullmatch(image_url, user) else user) if user else 'perry'
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

        await ctx.send(file=discord.File(img_bio(large_image), filename='blame.png'))

    @commands.command(aliases=['thefloor', 'the_floor'])
    async def floor(self, ctx, person: RichArgument, *, thefloor):
        """Generate a the floor is lava meme"""

        meme = Image.open('memes/floor.png')
        font = ImageFont.truetype('Arial.ttf', 30)
        draw = ImageDraw.Draw(meme)

        # Floor is
        place_centered_text("The floor is " + thefloor, (340, 65), draw, font, 45, BLACK)

        # Person's head
        pos = ((150, 145), (480, 160))
        size = ((20, 20), (40, 40))
        for i in range(2):
            place_centered_content(person, pos[i], draw, font, 20, BLUE, meme, size[i])

        await ctx.send(file=discord.File(img_bio(meme), filename='floor.png'))

    @commands.command(aliases=['highway'])
    async def car(self, ctx, driver: RichArgument,
                  first_option: RichArgument, second_option: RichArgument):
        """Generate a highway exit meme. Use quotes for sentences"""

        meme = Image.open('memes/highway.jpg')
        font = ImageFont.truetype('Arial.ttf', 22)
        draw = ImageDraw.Draw(meme)

        pos = ((365, 465), (210, 150), (420, 150))
        place_centered_content(driver, pos[0], draw, font, 25, WHITE, meme, (50, 50))
        place_centered_content(first_option, pos[1], draw, font, 9, WHITE, meme, (100, 100))
        place_centered_content(second_option, pos[2], draw, font, 12, WHITE, meme, (120, 120))

        await ctx.send(file=discord.File(img_bio(meme), filename='car.png'))

    @commands.command()
    async def wheeze(self, ctx, *, thing: RichArgument):
        """Generate a wheeze meme"""

        meme = Image.open('memes/wheeze.png')
        draw = ImageDraw.Draw(meme)
        font = ImageFont.truetype('Arial.ttf', 20)

        place_centered_content(thing, (90, 490), draw, font, 18, BLACK, meme, (100, 100))

        await ctx.send(file=discord.File(img_bio(meme), filename='wheeze.png'))

    # noinspection PyUnresolvedReferences
    @commands.command(aliases=['garbage'])
    async def trash(self, ctx, person: RichArgument, *, trash: RichArgument):
        """Generate a taking out the trash meme."""

        meme = Image.open('memes/garbage.jpg').convert('RGBA')
        font = ImageFont.truetype('Arial.ttf', 50)
        draw = ImageDraw.Draw(meme)

        pos = ((485, 90 if isinstance(person, str) else 140), (780, 300))
        place_centered_content(person, pos[0], draw, font, 10, BLUE, meme, (200, 200), 20)
        place_centered_content(trash, pos[1], draw, font, 15, BLACK, meme, (250, 250), -10)

        await ctx.send(file=discord.File(img_bio(meme), filename='trash.png'))

    @commands.command()
    async def captcha(self, ctx, img, *, message=None):
        """Generate a select all <blank>"""

        message = message or (get_img_name(img) if re.fullmatch(image_url, img) else img)
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
        draw.text((51, 90), message, font=font, fill=WHITE)

        await ctx.send(file=discord.File(img_bio(meme), filename='captcha.png'))


def setup(bot):
    bot.add_cog(Memes(bot))

