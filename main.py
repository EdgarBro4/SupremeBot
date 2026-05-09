import discord
from discord.ext import tasks, commands
import requests
from supabase import create_client, Client

# --- SECURE CONFIGURATION ---
STEAM_API_KEY = "714AA0D0A53DC80E953D17CBF8BC1C66"
APP_ID = "730"  # CS2 App ID
SUPABASE_URL = "https://ocageyxddltmspdjceni.supabase.co"
SUPABASE_KEY = "sb_secret_xycmCXu_lH5vjM__wwDAzQ_vm3NftEb"
DISCORD_TOKEN = "MTUwMjU3NjMzNzg0NjY2OTM2Mg.GHfP0I.IS77FoIkhqpTLFqmimHiqddFYB-HsjC_Xaxm94"
CHANNEL_ID = 1468152284671377436

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class CS2UpdateBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read !unfreeze
        super().__init__(command_prefix="!", intents=intents)
        self.last_update_id = None
        # Add the command to the bot manually
        self.add_command(self.unfreeze)

    async def setup_hook(self):
        self.check_for_updates.start()

    @tasks.loop(minutes=2)
    async def check_for_updates(self):
        url = f"http://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/?appid={APP_ID}&count=1&maxlength=1&format=json"
        try:
            response = requests.get(url).json()
            latest_news = response['appnews']['newsitems'][0]
            news_id = latest_news['gid']
            news_title = latest_news['title']

            if self.last_update_id is None:
                self.last_update_id = news_id
                print(f"Bot started. Monitoring CS2 updates. Current News ID: {news_id}")
                return

            if news_id != self.last_update_id:
                self.last_update_id = news_id
                print(f"NEW UPDATE DETECTED: {news_title}")
                await self.handle_freeze_sequence(news_title)

        except Exception as e:
            print(f"Error fetching Steam updates: {e}")

    async def handle_freeze_sequence(self, update_title):
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🚨 CS2 UPDATE DETECTED",
                description=f"**Update:** {update_title}\n\n**Action:** All CS2 products have been **FROZEN**.",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

        supabase.table("products").update({"purchase_available": False}).eq("id",
                                                                            "036024ab-b8e2-4326-967b-62ef35a4cda9").execute()
        supabase.table("licence_keys").update({"is_frozen": True}).eq("product_id",
                                                                      "036024ab-b8e2-4326-967b-62ef35a4cda9").execute()
        print("Update applied to Supabase: Products/Keys Frozen.")

    @commands.command(name="unfreeze")
    @commands.has_permissions(administrator=True)
    async def unfreeze(self, ctx):
        """Manual command to resume sales and unfreeze keys"""
        print("Unfreeze command triggered in Discord!")

        # Update Products
        supabase.table("products").update({"purchase_available": True}).eq("id",
                                                                           "036024ab-b8e2-4326-967b-62ef35a4cda9").execute()

        # Update Keys
        supabase.table("licence_keys").update({"is_frozen": False}).eq("product_id",
                                                                       "036024ab-b8e2-4326-967b-62ef35a4cda9").execute()

        await ctx.send("✅ **Supreme Internal CS2** has been unfreezed. Sales are back online!")


# Start the bot
bot = CS2UpdateBot()
bot.run(DISCORD_TOKEN)