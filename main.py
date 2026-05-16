import os
from dotenv import load_dotenv
import discord
from discord.ext import tasks, commands
import requests
from supabase import create_client, Client

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

# These now pull from your .env file instead of being visible in the code
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1468152284671377436 # This is safe to keep as it's just a channel ID

# Game Configuration Mapping
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

# Initialize Supabase
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
                    title_lower = news_title.lower()
                    if any(word in title_lower for word in ["update", "patch", "devblog"]):
                        self.last_updates[app_id] = news_id
                        print(f"UPDATE DETECTED for {info['name']}: {news_title}")
                        await self.handle_freeze(info['name'], info['prod_ids'], news_title)
                    else:
                        self.last_updates[app_id] = news_id
            except Exception as e:
                print(f"Error checking {info['name']}: {e}")

    async def handle_freeze(self, game_name, prod_ids, title):
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"🚨 {game_name.upper()} UPDATE DETECTED",
                description=f"**Update:** {title}\n\n**Action:** All {game_name} products are **FROZEN** and set to **On Update**.",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

        # Freezes purchases, changes status to "On Update", and freezes user keys
        for p_id in prod_ids:
            supabase.table("products").update({
                "purchase_available": False,
                "status": "On Update"
            }).eq("id", p_id).execute()
            
            supabase.table("user_keys").update({"is_frozen": True}).eq("product_id", p_id).execute()
        print(f"Database: All {game_name} entries frozen and set to 'On Update'.")


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

    # Unfreezes purchases, sets status back to "Undetected", and unfreezes keys
    for p_id in target_ids:
        supabase.table("products").update({
            "purchase_available": True,
            "status": "Undetected"
        }).eq("id", p_id).execute()
        
        supabase.table("user_keys").update({"is_frozen": False}).eq("product_id", p_id).execute()

    display_name = f"Rust {version.capitalize()}" if game == "rust" else "CS2"
    await ctx.send(f"✅ **{display_name}** products are now **Undetected**, keys unfrozen, and store opened!")


bot.run(DISCORD_TOKEN)
