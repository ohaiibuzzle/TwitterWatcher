import discord
from discord.ext import commands

import twitterwatch.twitterwatch as tw

import configparser

config = configparser.ConfigParser()
config.read("runtime/config.ini")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="t.", intents=intents)


@bot.event
async def on_ready():
    print("Logged in as")
    print(bot.user.name)
    print(bot.user.id)
    print("------")


bot.add_cog(tw.TwitterWatcher(bot))

bot.run(config["Credentials"]["discord_token"])
