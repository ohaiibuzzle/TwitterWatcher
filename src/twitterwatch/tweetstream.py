import asyncio
import tweepy
import tweepy.errors
from tweepy.asynchronous import AsyncStreamingClient


class TweetStreamer(AsyncStreamingClient):
    def __init__(self, bearer_token, on_tweet_handler):
        super().__init__(bearer_token=bearer_token)
        self.users = []
        self.on_tweet_handler = on_tweet_handler

    async def update_rules(self):
        # Remove all rules
        ids=[rule_ids.id for rule_ids in (await self.get_rules()).data]
        if len(ids) > 0:
            try:
                await self.delete_rules(
                    ids=[rule_ids.id for rule_ids in (await self.get_rules()).data]
                )
            except Exception as e:
                print(e)
                # Empty rules list, ignore
                pass

        if self.users is None or len(self.users) == 0:
            return

        # Filter for users: (from: user1 OR from: user2 OR from: user3)
        user_filter = " OR ".join(f"from:{user}" for user in self.users)

        await self.add_rules(tweepy.StreamRule(value=user_filter))

        # dump the rule from the API
        rules = await self.get_rules()
        print(rules)
        print("Rules updated")
        return

    async def on_data(self, raw_data):
        # print(raw_data)
        await super().on_data(raw_data)

    async def on_tweet(self, tweet):
        # print(tweet)
        await self.on_tweet_handler(tweet)
