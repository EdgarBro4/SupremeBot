import discord
from discord.ext import tasks, commands
import requests
from supabase import create_client, Client

# --- CONFIGURATION ---
STEAM_API_KEY = "714AA0D0A53DC80E953D17CBF8BC1C66"
SUPABASE_URL = "https://ocageyxddltmspdjceni.supabase.co"
SUPABASE_KEY = "sb_secret_xycmCXu_lH5vjM__wwDAzQ_vm3NftEb"
DISCORD_TOKEN = "MTUwMjU3NjMzNzg0NjY2OTM2Mg.GHfP0I.IS77FoIkhqpTLFqmimHiqddFYB-HsjC_Xaxm94"
CHANNEL_ID = 1468152284671377436

# Game Configuration Mapping
# Note: Rust has multiple product IDs in a list
GAMES = {
    "730": {
        "name": "Counter-Strike 2",
        "prod_ids": ["036024ab-b8e2-4326-967b-62ef35a4cda9"]
    },
    "252490": {
        "name": "Rust",
        "prod_ids": [
            "36b164c8-46ff-49ff-935e-d5efdc65af98",  # Rust Internal
            "cbf3668e-b3ff-416c-a3af-df785b3e9118"  # Rust External
        ]
    }
}

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class SupremeMultiBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.last_updates = {app_id: None for app_id in GAMES.keys()}

    async def setup_hook(self):
        self.check_updates_loop.start()

    @tasks.loop(minutes=2)
    async def check_updates_loop(self):
        for app_id, info in GAMES.items():
            url = f"http://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/?appid={app_id}&count=1&maxlength=1&format=json"
            try:
                response = requests.get(url).json()
                latest_news = response['appnews']['newsitems'][0]
                news_id = latest_news['gid']
                news_title = latest_news['title']

                if self.last_updates[app_id] is None:
                    self.last_updates[app_id] = news_id
                    print(f"Monitoring started for {info['name']}")
                    continue

                if news_id != self.last_updates[app_id]:
                    # Filter for actual game updates
                    if "update" in news_title.lower() or "patch" in news_title.lower() or "devblog" in news_title.lower():
                        self.last_updates[app_id] = news_id
                        await self.handle_freeze(info['name'], info['prod_ids'], news_title)
                    else:
                        self.last_updates[app_id] = news_id  # Still skip so we don't re-check news
            except Exception as e:
                print(f"Error checking {info['name']}: {e}")

    async def handle_freeze(self, game_name, prod_ids, title):
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"🚨 {game_name.upper()} UPDATE DETECTED",
                description=f"**Update:** {title}\n\n**Action:** All {game_name} products and keys are now **FROZEN**.",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

        for p_id in prod_ids:
            supabase.table("products").update({"purchase_available": False}).eq("id", p_id).execute()
            supabase.table("user_keys").update({"is_frozen": True}).eq("product_id", p_id).execute()
        print(f"Database: All {game_name} entries frozen.")


bot = SupremeMultiBot()


@bot.command(name="unfreeze")
@commands.has_permissions(administrator=True)
async def unfreeze(ctx, game: str, version: str = None):
    """
    Usage:
    !unfreeze cs2
    !unfreeze rust alkad
    !unfreeze rust steam
    """
    game = game.lower()
    print(f"Unfreeze command triggered for {game} {version if version else ''} by {ctx.author}")

    # Define the mapping for all products
    product_mapping = {
        "cs2": ["036024ab-b8e2-4326-967b-62ef35a4cda9"],
        "rust_alkad": ["36b164c8-46ff-49ff-935e-d5efdc65af98"],
        "rust_steam": ["cbf3668e-b3ff-416c-a3af-df785b3e9118"]
    }

    # Determine which IDs to target
    target_ids = []
    if game == "cs2":
        target_ids = product_mapping["cs2"]
    elif game == "rust":
        if version == "alkad":
            target_ids = product_mapping["rust_alkad"]
        elif version == "steam":
            target_ids = product_mapping["rust_steam"]
        else:
            await ctx.send("❌ Please specify which Rust version: `!unfreeze rust alkad` or `!unfreeze rust steam`")
            return
    else:
        await ctx.send(f"❌ '{game}' is not a valid game choice.")
        return

    # Execute the database updates
    for p_id in target_ids:
        supabase.table("products").update({"purchase_available": True}).eq("id", p_id).execute()
        supabase.table("user_keys").update({"is_frozen": False}).eq("product_id", p_id).execute()

    display_name = f"Rust {version.capitalize()}" if game == "rust" else "CS2"
    await ctx.send(f"✅ **{display_name}** products and keys have been unfreezed!")


bot.run(DISCORD_TOKEN)