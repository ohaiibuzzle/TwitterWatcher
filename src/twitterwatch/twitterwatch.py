import asyncio
import configparser
import sqlite3

import aiosqlite
import tweepy
from discord.ext import commands, tasks

from . import tweetstream

config = configparser.RawConfigParser()
config.read("runtime/config.ini")


class TwitterWatcher(commands.Cog):

    def __init__(self, client):
        self.client = client

        self.api = tweepy.API(
            auth=tweepy.OAuth2BearerHandler(
                config["Credentials"]["twitter_bearer_token"]
            )
        )
        self.tweetstream = tweetstream.TweetStreamer(
            config["Credentials"]["twitter_bearer_token"], self.on_tweet
        )

        # Initializing database
        database = sqlite3.connect("runtime/server_data.db")
        cursor = database.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tweetwatch (
                twitter_id INTEGER PRIMARY KEY,
                twitter_account TEXT UNIQUE,
                watching_channels TEXT
            )
            """
        )

        # Load the watching list from the database
        cursor.execute("SELECT twitter_account FROM tweetwatch")
        self.tweetstream.users = [row[0] for row in cursor.fetchall()]
        database.commit()
        pass

    @commands.Cog.listener()
    async def on_ready(self):
        # Do an initial update of the rules
        await self.tweetstream.update_rules()
        self.tweetstream_task = self.tweetstream.filter(expansions="author_id")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def tweetwatch(self, ctx, *, twitter_account):
        channel = ctx.channel.id
        # Check if the account is already being watched
        async with aiosqlite.connect("runtime/server_data.db") as db:
            cursor = await db.execute(
                "SELECT * FROM tweetwatch WHERE twitter_account = ?", (twitter_account,)
            )
            row = await cursor.fetchone()
            if row:
                # pull out the channel list
                channels = row[2].split(",")
                if str(channel) in channels:
                    await ctx.send(
                        f"{twitter_account} is already being watched in this channel."
                    )
                    return await db.commit()

                else:
                    # add the channel to the list
                    channels.append(str(channel))
                    await db.execute(
                        "UPDATE tweetwatch SET watching_channels = ? WHERE twitter_account = ?",
                        (",".join(channels), twitter_account),
                    )
                    self.tweetstream.users.append(twitter_account)
                    await self.tweetstream.update_rules()
                    await ctx.send(
                        f"{twitter_account} is now being watched in this channel."
                    )

                    return await db.commit()
            else:
                # resolves the twitter account id
                user = self.api.get_user(screen_name=twitter_account)
                # add the account to the database
                await db.execute(
                    "INSERT INTO tweetwatch (twitter_id, twitter_account, watching_channels) VALUES (?, ?, ?)",
                    (user.id, twitter_account, str(channel)),
                )
                self.tweetstream.users.append(twitter_account)
                await self.tweetstream.update_rules()
                await ctx.send(
                    f"{twitter_account} is now being watched in this channel."
                )
                return await db.commit()

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def tweetunwatch(self, ctx, *, twitter_account):
        """
        Stop watching a twitter account
        """
        channel = ctx.channel.id
        # Check if the account is already being watched
        async with aiosqlite.connect("runtime/server_data.db") as db:
            cursor = await db.execute(
                "SELECT * FROM tweetwatch WHERE twitter_account = ?", (twitter_account,)
            )
            row = await cursor.fetchone()
            if row:
                # pull out the channel list
                channels = row[2].split(",")
                if str(channel) in channels:
                    # remove the channel from the list
                    channels.remove(str(channel))
                    # if the list is empty, delete the row
                    if not channels:
                        await db.execute(
                            "DELETE FROM tweetwatch WHERE twitter_account = ?",
                            (twitter_account,),
                        )
                        self.tweetstream.users.remove(twitter_account)
                        await self.tweetstream.update_rules()
                    else:
                        await db.execute(
                            "UPDATE tweetwatch SET watching_channels = ? WHERE twitter_account = ?",
                            (",".join(channels), twitter_account),
                        )
                    await db.commit()
                    await ctx.send(
                        f"{twitter_account} is no longer being watched in this channel."
                    )
                    return
                else:
                    await ctx.send(
                        f"{twitter_account} is not being watched in this channel."
                    )
                    return
            else:
                await ctx.send(f"{twitter_account} is not being watched.")
                return

    async def on_tweet(self, tweet: tweepy.Tweet):
        async with aiosqlite.connect("runtime/server_data.db") as db:
            cursor = await db.execute(
                "SELECT * FROM tweetwatch WHERE twitter_id = ?", (tweet.author_id,)
            )
            # send messages to the appropriate channels
            for row in await cursor.fetchall():
                author_name = row[1]
                channels = row[2].split(",")
                for channel in channels:
                    channel = self.client.get_channel(int(channel))
                    # Spawn a temporary discord.Webhook on the channel
                    webhook = await channel.create_webhook(name=f"@{author_name}")
                    # Send the url to the tweet to the webhook
                    await webhook.send(
                        f"https://twitter.com/{author_name}/status/{tweet.id}"
                    )
                    # Delete the webhook
                    await webhook.delete()
        pass


def setup(client):
    print("Loading Twitter Watcher...")
    client.add_cog(TwitterWatcher(client))
