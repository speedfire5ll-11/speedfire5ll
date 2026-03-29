import discord
from discord.ext import commands
from discord import app_commands, Embed, Color, Interaction, ui
from discord.ui import View, Button
import datetime
import json
import os
import asyncio
import aiofiles

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("BOT_TOKEN")
GUILD_ID = 1474846906369966195

# Role and Channel Constants
TICKETS_CATEGORY_ID = 1475983445380436089
TRANSCRIPT_CHANNEL_ID = 1476330542902280366
VOUCH_CHANNEL_ID = 1475983143554125824
INFO_ROLE_ID = 1474846906369966202
MM_ROLE_ID = 1474846906369966203
MANAGER_ROLE_ID = 1474846906449662045
INFO_LOG_CHANNEL_ID = 1469670001228120200
BAN_LOG_CHANNEL_ID = 1476330569507012618
WARN_DATA_FILE = "warns.json"
TICKET_DATA_FILE = "tickets.json"
VOUCH_DATA_FILE = "vouches.json"
TRUSTED_MM_ROLE_ID = 1474846906407452864
MOD_LOG_CHANNEL_ID = 1476330569507012618
EXPERIENCED_MM_ROLE_ID = 1474846906369966204


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.vouch_data = {}
        self.active_tickets = {}

    async def setup_hook(self):
        await self.load_data()
        await self.tree.sync()
        self.add_view(TicketPanel())
        self.add_view(TicketControls())
        self.add_view(IndexTicketPanel())
        self.add_view(IndexTicketControls())
        self.add_view(SupportTicketPanel())
        self.add_view(SupportTicketControls())
        print(f"Logged in as {self.user}. Commands synced globally")

    async def load_data(self):
        try:
            if os.path.exists(VOUCH_DATA_FILE):
                async with aiofiles.open(VOUCH_DATA_FILE, "r") as f:
                    content = await f.read()
                    if content: self.vouch_data = json.loads(content)
            if os.path.exists(TICKET_DATA_FILE):
                async with aiofiles.open(TICKET_DATA_FILE, "r") as f:
                    content = await f.read()
                    if content: self.active_tickets = json.loads(content)
        except Exception as e:
            print(f"Data load error: {e}")

    async def save_data(self):
        async with aiofiles.open(VOUCH_DATA_FILE, "w") as f:
            await f.write(json.dumps(self.vouch_data, indent=4))
        async with aiofiles.open(TICKET_DATA_FILE, "w") as f:
            await f.write(json.dumps(self.active_tickets, indent=4))

bot = MyBot()

# ---------------- PERMISSION HELPERS ----------------
def has_role(member, role_id):
    return any(r.id == role_id for r in member.roles)

def is_manager(interaction: Interaction):
    return has_role(interaction.user, MANAGER_ROLE_ID)

def is_mm(interaction: Interaction):
    return has_role(interaction.user, MM_ROLE_ID)

# ---------------- WARN HELPERS ----------------
async def load_warns():
    try:
        if os.path.exists(WARN_DATA_FILE):
            async with aiofiles.open(WARN_DATA_FILE, "r") as f:
                content = await f.read()
                if content: return json.loads(content)
    except: pass
    return {}

async def save_warns(data):
    async with aiofiles.open(WARN_DATA_FILE, "w") as f:
        await f.write(json.dumps(data, indent=4))

# ---------------- UI COMPONENTS ----------------

class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🎫 Open Ticket", style=discord.ButtonStyle.primary, custom_id="persistent:open_ticket")
    async def open_ticket(self, interaction: Interaction, button: Button):
        category = interaction.guild.get_channel(TICKETS_CATEGORY_ID)
        if not category:
            return await interaction.response.send_message("❌ Ticket category configuration missing.", ephemeral=True)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            interaction.guild.get_role(MM_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        bot.active_tickets[str(channel.id)] = {"owner": interaction.user.id, "claimed": None}
        await bot.save_data()

        embed = Embed(
            title="🔐 Trusted Middleman Service",
            description=(
                "✅ 100% Trusted & Staff-Handled Trades\n\n"
                "• Your trade is handled by verified Middlemen\n"
                "• Funds/items are secured during the trade\n"
                "• If any scam occurs, refunds are available\n\n"
                "📌 Please provide:\n"
                "• Trade details\n"
                "• User involved\n"
                "• Proof/screenshots\n\n"
                "⬇️ A middleman will claim your ticket shortly."
            ),
            color=Color.blurple()
        )

        await channel.send(content=f"{interaction.user.mention} <@&{MM_ROLE_ID}>", embed=embed, view=TicketControls())
        await interaction.response.send_message(f"✅ Your ticket has been created: {channel.mention}", ephemeral=True)


class TicketControls(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛡️ Claim", style=discord.ButtonStyle.success, custom_id="persistent:claim_ticket")
    async def claim(self, interaction: Interaction, button: Button):
        tid = str(interaction.channel.id)
        data = bot.active_tickets.get(tid)
        if not data:
            return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
        if data["claimed"]:
            return await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
        if not is_mm(interaction):
            return await interaction.response.send_message("❌ Only Verified Middlemen can claim this ticket.", ephemeral=True)
        data["claimed"] = interaction.user.id
        await bot.save_data()
        button.label = "✅ Claimed"
        button.disabled = True
        button.style = discord.ButtonStyle.secondary
        await interaction.channel.set_permissions(interaction.user, send_messages=True, attach_files=True)
        embed = interaction.message.embeds[0]
        embed.add_field(name="Claimed By", value=interaction.user.mention, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="persistent:close_ticket")
    async def close(self, interaction: Interaction, button: Button):
        await close_ticket_logic(interaction)


class IndexTicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📋 Open Index Ticket", style=discord.ButtonStyle.primary, custom_id="persistent:open_index_ticket")
    async def open_index_ticket(self, interaction: Interaction, button: Button):
        category = interaction.guild.get_channel(TICKETS_CATEGORY_ID)
        if not category:
            return await interaction.response.send_message("❌ Ticket category configuration missing.", ephemeral=True)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            interaction.guild.get_role(EXPERIENCED_MM_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }

        channel = await interaction.guild.create_text_channel(
            name=f"index-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        bot.active_tickets[str(channel.id)] = {"owner": interaction.user.id, "claimed": None}
        await bot.save_data()

        embed = Embed(
            title="📋 Index Ticket",
            description=(
                "✅ Professional Index MM Service\n\n"
                "• One of our professional Index MMs will be with you shortly\n\n"
                "📌 Available Bases:\n"
                "• Divine Base\n"
                "• Cursed Base\n"
                "• Ying Yang Base\n"
                "• Candy Base\n"
                "• Galaxy Base\n"
                "• Lava Base\n"
                "• Rainbow Base\n"
                "• And more!\n\n"
                "⬇️ An Index MM will claim your ticket shortly."
            ),
            color=Color.gold()
        )

        await channel.send(content=f"{interaction.user.mention} <@&{EXPERIENCED_MM_ROLE_ID}>", embed=embed, view=IndexTicketControls())
        await interaction.response.send_message(f"✅ Your index ticket has been created: {channel.mention}", ephemeral=True)


class IndexTicketControls(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛡️ Claim", style=discord.ButtonStyle.success, custom_id="persistent:claim_index_ticket")
    async def claim(self, interaction: Interaction, button: Button):
        tid = str(interaction.channel.id)
        data = bot.active_tickets.get(tid)
        if not data:
            return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
        if data["claimed"]:
            return await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
        if not has_role(interaction.user, EXPERIENCED_MM_ROLE_ID) and not is_manager(interaction):
            return await interaction.response.send_message("❌ Only Experienced MMs can claim this ticket.", ephemeral=True)
        data["claimed"] = interaction.user.id
        await bot.save_data()
        button.label = "✅ Claimed"
        button.disabled = True
        button.style = discord.ButtonStyle.secondary
        await interaction.channel.set_permissions(interaction.user, send_messages=True, attach_files=True)
        embed = interaction.message.embeds[0]
        embed.add_field(name="Claimed By", value=interaction.user.mention, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="persistent:close_index_ticket")
    async def close(self, interaction: Interaction, button: Button):
        await close_ticket_logic(interaction)


class InfoView(View):
    def __init__(self, target: discord.Member, author: discord.Member):
        super().__init__(timeout=60.0)
        self.target = target
        self.author = author

    @ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Only the targeted user can respond to this.", ephemeral=True)
        role = interaction.guild.get_role(INFO_ROLE_ID)
        if role: await self.target.add_roles(role)
        embed = Embed(
            title="💫 Hitting Tutorial",
            description=(
                "You're a hitter now. A hitter is someone that got scammed by us, and goes out to scam others.\n\n"
                "**What do I do?**\n"
                "Go to other Discord servers and advertise that you're looking to trade. When someone DMs you, "
                "guide the conversation towards using a middleman. Once they agree, invite them to this server and open a ticket.\n\n"
                "**How do I get paid?**\n"
                "Once the trade is complete, you and the middleman split the profit 50/50.\n\n"
                "**Can I rank up?**\n"
                "Yes! Check rank-up-info for requirements.\n\n"
                "**Important Rules**\n"
                "Never advertise in DMs and never use a personal middleman. Both result in an instant ban."
            ),
            color=Color.gold(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text="Seize the opportunity.")
        try:
            await self.target.send(embed=embed)
        except: pass
        await interaction.response.send_message(f"{self.target.mention} has accepted the opportunity and become a hitter.")
        log_ch = interaction.guild.get_channel(INFO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(title="Info Command Used", description=f"**User:** {self.target}\n**Staff:** {self.author}\n**Status:** Accepted", color=Color.green(), timestamp=datetime.datetime.now())
            await log_ch.send(embed=log_embed)
        self.stop()

    @ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Only the targeted user can respond to this.", ephemeral=True)
        await interaction.response.send_message(f"{self.target.mention} has declined the offer.")
        log_ch = interaction.guild.get_channel(INFO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(title="Info Command Used", description=f"**User:** {self.target}\n**Staff:** {self.author}\n**Status:** Declined", color=Color.red(), timestamp=datetime.datetime.now())
            await log_ch.send(embed=log_embed)
        self.stop()


class IndexInfoView(View):
    def __init__(self, target: discord.Member, author: discord.Member):
        super().__init__(timeout=60.0)
        self.target = target
        self.author = author

    @ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Only the targeted user can respond to this.", ephemeral=True)
        embed = Embed(
            title="📋 Index Hitter Tutorial",
            description=(
                "You're now an Index Hitter! Here's how it works:\n\n"
                "**What do I do?**\n"
                "Advertise our bases in other servers. Tell people we sell Divine, Cursed, Galaxy, Lava, Rainbow, Candy, Ying Yang bases and more. "
                "Once they're interested, bring them to our server and open an index ticket. An Index MM will handle the rest.\n\n"
                "**How do I get paid?**\n"
                "Once the trade is complete you and the Index MM split the profit 50/50.\n\n"
                "**Important Rules**\n"
                "• Never advertise in DMs\n"
                "• Never use a personal middleman\n"
                "• Read the staff rules to avoid warnings or demotions\n"
                "• Both offenses above result in an instant ban\n\n"
                "Check rank-up-info for promotion requirements.\n\n"
                "Good luck — crazy profit is waiting!"
            ),
            color=Color.gold(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text="Seize the opportunity.")
        try:
            await self.target.send(embed=embed)
        except: pass
        await interaction.response.send_message(f"{self.target.mention} has accepted the opportunity and become an Index Hitter!")
        log_ch = interaction.guild.get_channel(INFO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(title="Index Info Command Used", description=f"**User:** {self.target}\n**Staff:** {self.author}\n**Status:** Accepted", color=Color.green(), timestamp=datetime.datetime.now())
            await log_ch.send(embed=log_embed)
        self.stop()

    @ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Only the targeted user can respond to this.", ephemeral=True)
        await interaction.response.send_message(f"{self.target.mention} has declined the offer.")
        log_ch = interaction.guild.get_channel(INFO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(title="Index Info Command Used", description=f"**User:** {self.target}\n**Staff:** {self.author}\n**Status:** Declined", color=Color.red(), timestamp=datetime.datetime.now())
            await log_ch.send(embed=log_embed)
        self.stop()


class TradeConfirmView(ui.View):
    def __init__(self, trader1: discord.Member, trader2: discord.Member, trade_info: str):
        super().__init__(timeout=300)
        self.trader1 = trader1
        self.trader2 = trader2
        self.trade_info = trade_info
        self.trader1_confirmed = False
        self.trader2_confirmed = False

    async def update_embed(self, interaction: discord.Interaction):
        awaiting = []
        if not self.trader1_confirmed:
            awaiting.append(f"🔴 {self.trader1.mention}")
        if not self.trader2_confirmed:
            awaiting.append(f"🔴 {self.trader2.mention}")
        if not awaiting:
            embed = Embed(title="✅ Trade Confirmed", color=Color.green())
            embed.description = "Both traders have confirmed this trade. Please proceed with the rest of the trade."
            embed.add_field(name="🧑 Trader 1", value=self.trader1.mention, inline=True)
            embed.add_field(name="🧑 Trader 2", value=self.trader2.mention, inline=True)
            embed.add_field(name="✅ Status", value="Both traders confirmed", inline=False)
            embed.set_footer(text="Powered by Trading Portal • Today")
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(embed=embed, view=self)
        else:
            embed = Embed(title="✅ Trade Confirmation", color=Color.green())
            embed.description = "In order to continue this trade, both traders should confirm the trade."
            embed.add_field(name="📊 Trade Information", value=self.trade_info, inline=False)
            embed.add_field(name="🧑 Trader 1", value=self.trader1.mention, inline=True)
            embed.add_field(name="🧑 Trader 2", value=self.trader2.mention, inline=True)
            embed.add_field(name="⏳ Awaiting Confirmation", value="\n".join(awaiting), inline=False)
            embed.set_footer(text="Powered by Trading Portal • Today")
            await interaction.message.edit(embed=embed, view=self)

    @ui.button(label="✅ Confirm Trade (Trader 1)", style=discord.ButtonStyle.success)
    async def confirm_trader1(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.trader1:
            await interaction.response.send_message("❌ Only Trader 1 can click this button!", ephemeral=True)
            return
        self.trader1_confirmed = True
        button.disabled = True
        await interaction.response.defer()
        await self.update_embed(interaction)

    @ui.button(label="✅ Confirm Trade (Trader 2)", style=discord.ButtonStyle.success)
    async def confirm_trader2(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.trader2:
            await interaction.response.send_message("❌ Only Trader 2 can click this button!", ephemeral=True)
            return
        self.trader2_confirmed = True
        button.disabled = True
        await interaction.response.defer()
        await self.update_embed(interaction)

# ---------------- CORE LOGIC ----------------

async def close_ticket_logic(interaction: Interaction):
    tid = str(interaction.channel.id)
    data = bot.active_tickets.get(tid)
    if not data:
        return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
    if not is_mm(interaction) and not has_role(interaction.user, EXPERIENCED_MM_ROLE_ID) and data["owner"] != interaction.user.id:
        return await interaction.response.send_message("❌ Only the claimed MM or the Ticket Owner can close this ticket.", ephemeral=True)
    await interaction.response.send_message("⌛ Archiving chat and closing channel in 5s...")
    log_ch = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID)
    msgs = []
    async for msg in interaction.channel.history(limit=None, oldest_first=True):
        if msg.content:
            msgs.append(f"{msg.author}: {msg.content}")
    txt = "\n".join(msgs)
    embed = Embed(title="📜 Ticket Transcript", color=Color.dark_gray(), timestamp=datetime.datetime.now())
    embed.add_field(name="Ticket Owner", value=f"<@{data['owner']}>", inline=False)
    embed.add_field(name="Claimed By", value=f"<@{data['claimed']}>" if data["claimed"] else "Unclaimed", inline=False)
    embed.add_field(name="Closed By", value=interaction.user.mention, inline=False)
    if txt:
        embed.description = txt[:4000]
    if log_ch:
        await log_ch.send(embed=embed)
    bot.active_tickets.pop(tid, None)
    await bot.save_data()
    await asyncio.sleep(5)
    await interaction.channel.delete()

# ---------------- SLASH COMMANDS ----------------

@bot.tree.command(name="rules", description="View the official server rules and guidelines")
async def rules(interaction: Interaction):
    embed = Embed(
        title="📚 Server Rules",
        description=(
            "Be Respectful\nNo Spam or Self-Promotion\nKeep Content Appropriate\nUse the Correct Channels\n"
            "No Illegal Activities\nRespect Privacy\nNo Impersonation\nFollow Discord ToS\n"
            "Listen to Staff\nWe Are NOT Responsible\nServer Ads\nNo Death Threats\n"
            "No Toxicity Beyond a Joke\nBe Supportive\nHave Fun & Be Kind\n"
            "Middleman Fees $3 MM fee, $1.50 cancel fee"
        ),
        color=Color.blurple()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setupticket", description="Deploy the Middleman ticket creation panel in this channel")
async def setupticket(interaction: Interaction):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ No permission. Only Managers can use this.", ephemeral=True)
    embed = Embed(
        title="🔐 Trusted Middleman Service",
        description=(
            "✅ 100% Trusted & Staff-Handled Trades\n\n"
            "• Your trade is handled by verified Middlemen\n"
            "• Funds/items are secured during the trade\n"
            "• If any scam occurs, refunds are available\n\n"
            "📌 Please provide:\n"
            "• Trade details\n"
            "• User involved\n"
            "• Proof/screenshots\n\n"
            "⬇️ Request a MM here."
        ),
        color=Color.blurple()
    )
    await interaction.channel.send(embed=embed, view=TicketPanel())
    await interaction.response.send_message("✅ Ticket panel deployed successfully.", ephemeral=True)

@bot.tree.command(name="setupindexticket", description="Deploy the Index ticket panel in this channel")
async def setupindexticket(interaction: Interaction):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ No permission. Only Managers can use this.", ephemeral=True)
    embed = Embed(
        title="📋 Index Ticket",
        description=(
            "✅ Professional Index MM Service\n\n"
            "• One of our professional Index MMs will be with you shortly\n\n"
            "📌 Available Bases:\n"
            "• Divine Base\n"
            "• Cursed Base\n"
            "• Ying Yang Base\n"
            "• Candy Base\n"
            "• Galaxy Base\n"
            "• Lava Base\n"
            "• Rainbow Base\n"
            "• And more!\n\n"
            "⬇️ Request an Index MM here."
        ),
        color=Color.gold()
    )
    await interaction.channel.send(embed=embed, view=IndexTicketPanel())
    await interaction.response.send_message("✅ Index ticket panel deployed successfully.", ephemeral=True)

@bot.tree.command(name="info", description="Send scam notification to a user (MM only)")
@app_commands.describe(user="The user to target with the scam notification")
async def info(interaction: Interaction, user: discord.Member):
    if not is_mm(interaction):
        return await interaction.response.send_message("❌ Only Verified Middlemen can use this command.", ephemeral=True)
    if has_role(user, INFO_ROLE_ID):
        return await interaction.response.send_message("❌ This user is already a verified hitter.", ephemeral=True)
    embed = Embed(
        title="⚠️ Scam Notification",
        description=(
            f"If you're seeing this, you've likely just been scammed — but this doesn't end how you think.\n\n"
            "Most people in this server started out the same way. But instead of taking the loss, they became hitters — and now they're making 3x, 5x, even 10x what they lost.\n\n"
            "This is your chance to turn a setback into serious profit.\n\n"
            "⏰ Every minute you wait is profit missed.\n\n"
            f"{user.mention} do you want to accept this opportunity and become a hitter?\n\n⏳ You have 1 minute to respond. The decision is yours."
        ),
        color=Color.red()
    )
    await interaction.response.send_message(content=user.mention, embed=embed, view=InfoView(user, interaction.user))

@bot.tree.command(name="indexinfo", description="Send index scam notification to a user (Experienced MM only)")
@app_commands.describe(user="The user to target with the index scam notification")
async def indexinfo(interaction: Interaction, user: discord.Member):
    if not has_role(interaction.user, EXPERIENCED_MM_ROLE_ID) and not is_manager(interaction):
        return await interaction.response.send_message("❌ Only Experienced MMs can use this command.", ephemeral=True)
    embed = Embed(
        title="⚠️ Index Scam Notification",
        description=(
            f"If you're seeing this, you most likely just got index-scammed — but this is not how it turns out!\n\n"
            "Most people in this server got index-scammed, which is where you were supposed to get the base, but won't.\n\n"
            "Now you can invite people and do the same to them — and make 3x, 5x, or even 10x of what you lost. "
            "You can flip the switch and start telling people about our bases we sell and split the profits with the Index MMs.\n\n"
            "This is your chance to turn a setback into serious profit.\n\n"
            "You now have access to all scammer/hitter channels. Once you accept you can see everything you need.\n\n"
            "⏰ Every minute you wait is profit missed.\n\n"
            "Need help getting started? Ask in the support channel.\n\n"
            f"{user.mention} do you accept this opportunity and join us as a hitter?\n\n"
            "⏳ Take your time and respond — crazy profit is awaiting. The choice is yours."
        ),
        color=Color.gold()
    )
    await interaction.response.send_message(content=user.mention, embed=embed, view=IndexInfoView(user, interaction.user))

@bot.tree.command(name="faq", description="View frequently asked questions")
async def faq(interaction: Interaction):
    embed = Embed(
        title="📌 Frequently Asked Questions",
        description=(
            "Q1: How do I get a role?\nA: Roles are assigned based on activity, applications, or commands.\n\n"
            "Q2: How do I report someone?\nA: Use support-system to file a report.\n\n"
            "Q3: Why was my message deleted?\nA: It may have violated a server rule.\n\n"
            "Q4: Can I advertise my server?\nA: Only in designated channels with permission."
        ),
        color=Color.blurple()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tos", description="Review the official middleman service Terms of Service")
async def tos(interaction: Interaction):
    embed = Embed(
        title="📋 Middleman Terms of Service",
        description="🚫 No Refunds Once Confirmed\n📸 Proof May Be Required\n⚖️ No Illegal Items\n🛡️ Scams and Disputes\n💰 Fees",
        color=Color.blurple()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch", description="Submit a vouch for a trader or middleman")
@app_commands.describe(user="User to vouch for", reason="Reason for the vouch")
async def vouch(interaction: Interaction, user: discord.Member, reason: str):
    uid = str(user.id)
    if uid not in bot.vouch_data: bot.vouch_data[uid] = {"count": 0, "vouches": []}
    bot.vouch_data[uid]["count"] += 1
    bot.vouch_data[uid]["vouches"].append({"voucher": interaction.user.id, "reason": reason})
    await bot.save_data()
    ch = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if ch:
        embed = Embed(title="📝 New Vouch", description=f"**Voucher:** {interaction.user}\n**Vouched User:** {user}\n**Reason:** {reason}\n**Total Vouches:** {bot.vouch_data[uid]['count']}", color=Color.green(), timestamp=datetime.datetime.now())
        await ch.send(embed=embed)
    await interaction.response.send_message(f"✅ Your vouch for {user.mention} has been recorded.", ephemeral=True)

@bot.tree.command(name="stats", description="Check vouches for a specific user")
@app_commands.describe(user="User to check stats for")
async def stats(interaction: Interaction, user: discord.Member):
    data = bot.vouch_data.get(str(user.id))
    if not data: return await interaction.response.send_message(f"❌ {user} has no vouches recorded.", ephemeral=True)
    description = ""
    for v in data["vouches"][-10:]:
        description += f"**<@{v['voucher']}>:** {v['reason']}\n"
    embed = Embed(title=f"📝 Vouch Stats for {user}", description=description, color=Color.blue())
    embed.set_footer(text=f"Total Vouches: {data['count']}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="add", description="Add a member to the current ticket channel")
@app_commands.describe(user="User to add")
async def add(interaction: Interaction, user: discord.Member):
    if str(interaction.channel.id) not in bot.active_tickets:
        return await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
    await interaction.response.send_message(f"✅ {user.mention} was added to this ticket.")

@bot.tree.command(name="transfer", description="Transfer the ownership of this ticket to another member")
@app_commands.describe(user="New owner")
async def transfer(interaction: Interaction, user: discord.Member):
    tid = str(interaction.channel.id)
    if tid not in bot.active_tickets:
        return await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
    bot.active_tickets[tid]["owner"] = user.id
    await bot.save_data()
    await interaction.response.send_message(f"✅ Ticket ownership transferred to {user.mention}")

@bot.tree.command(name="close", description="Close the current ticket")
async def close(interaction: Interaction):
    await close_ticket_logic(interaction)

@bot.tree.command(name="managerole", description="Add or remove roles from a user (Management only)")
@app_commands.describe(user="User", role="Role", action="add or remove", reason="Reason")
async def managerole(interaction: Interaction, user: discord.Member, role: discord.Role, action: str, reason: str = "No reason provided"):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ Only Managers can use this command.", ephemeral=True)
    ROLE_LOG_CHANNEL_ID = 1487598068114128936
    log_ch = interaction.guild.get_channel(ROLE_LOG_CHANNEL_ID)
    if action.lower() == "add":
        await user.add_roles(role)
        await interaction.response.send_message(f"✅ {role.name} added to {user.mention}")
        if log_ch:
            embed = Embed(title="Role Given ✅", color=Color.green(), timestamp=datetime.datetime.now())
            embed.add_field(name="Actioned By", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            embed.add_field(name="Target User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Role", value=role.name, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
            embed.set_footer(text="Powered by Trading Portal • Today")
            await log_ch.send(embed=embed)
    elif action.lower() == "remove":
        await user.remove_roles(role)
        await interaction.response.send_message(f"✅ {role.name} removed from {user.mention}")
        if log_ch:
            embed = Embed(title="Role Removed ❌", color=Color.red(), timestamp=datetime.datetime.now())
            embed.add_field(name="Actioned By", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            embed.add_field(name="Target User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Role", value=role.name, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
            embed.set_footer(text="Powered by Trading Portal • Today")
            await log_ch.send(embed=embed)
    else:
        await interaction.response.send_message("❌ Action must be 'add' or 'remove'.", ephemeral=True)

@bot.tree.command(name="manageban", description="Ban or unban a user (Management only)")
@app_commands.describe(user="User ID or mention", action="ban or unban")
async def manageban(interaction: Interaction, user: str, action: str):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ Only Managers can use this command.", ephemeral=True)
    try:
        uid_str = user.replace('<@','').replace('>','').replace('!','').replace('&','')
        uid = int(uid_str)
        log_ch = interaction.guild.get_channel(BAN_LOG_CHANNEL_ID)
        if action.lower() == "ban":
            try: target_user = await bot.fetch_user(uid)
            except: target_user = f"Unknown User ({uid})"
            await interaction.guild.ban(discord.Object(id=uid), reason=f"Banned by {interaction.user}")
            await interaction.response.send_message(f"✅ User ID `{uid}` has been banned.")
            if log_ch:
                log_embed = Embed(title="🛡️ Member Banned", color=Color.red(), timestamp=datetime.datetime.now())
                log_embed.add_field(name="Target User", value=f"{target_user}", inline=True)
                log_embed.add_field(name="User ID", value=f"`{uid}`", inline=True)
                log_embed.add_field(name="Staff Member", value=f"{interaction.user.mention}", inline=False)
                await log_ch.send(embed=log_embed)
        elif action.lower() == "unban":
            try: target_user = await bot.fetch_user(uid)
            except: target_user = f"Unknown User ({uid})"
            await interaction.guild.unban(discord.Object(id=uid), reason=f"Unbanned by {interaction.user}")
            await interaction.response.send_message(f"✅ User ID `{uid}` has been unbanned.")
            if log_ch:
                log_embed = Embed(title="🔓 Member Unbanned", color=Color.green(), timestamp=datetime.datetime.now())
                log_embed.add_field(name="Target User", value=f"{target_user}", inline=True)
                log_embed.add_field(name="User ID", value=f"`{uid}`", inline=True)
                log_embed.add_field(name="Staff Member", value=f"{interaction.user.mention}", inline=False)
                await log_ch.send(embed=log_embed)
        else:
            await interaction.response.send_message("❌ Action must be 'ban' or 'unban'.", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("❌ Invalid User ID or mention provided.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="confirm", description="Start a trade confirmation")
@app_commands.describe(trader1="First trader", trader2="Second trader", trade_info="Details of the trade")
async def confirm(interaction: Interaction, trader1: discord.Member, trader2: discord.Member, trade_info: str):
    view = TradeConfirmView(trader1, trader2, trade_info)
    embed = Embed(title="✅ Trade Confirmation", color=Color.green())
    embed.description = "In order to continue this trade, both traders should confirm the trade."
    embed.add_field(name="📊 Trade Information", value=trade_info, inline=False)
    embed.add_field(name="🧑 Trader 1", value=trader1.mention, inline=True)
    embed.add_field(name="🧑 Trader 2", value=trader2.mention, inline=True)
    embed.add_field(name="⏳ Awaiting Confirmation", value=f"🔴 {trader1.mention}\n🔴 {trader2.mention}", inline=False)
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(f"{trader1.mention} {trader2.mention}", embed=embed, view=view)

@bot.tree.command(name="warn", description="Warn a user (Trusted MM only)")
@app_commands.describe(user="User to warn", reason="Reason for the warning")
async def warn(interaction: Interaction, user: discord.Member, reason: str):
    if not has_role(interaction.user, TRUSTED_MM_ROLE_ID) and not is_manager(interaction):
        return await interaction.response.send_message("❌ Only Trusted MM can use this command.", ephemeral=True)
    warn_data = await load_warns()
    uid = str(user.id)
    if uid not in warn_data: warn_data[uid] = []
    warn_data[uid].append({"reason": reason, "by": interaction.user.id, "time": str(datetime.datetime.now())})
    await save_warns(warn_data)
    embed = Embed(title="⚠️ User Warned", color=Color.yellow(), timestamp=datetime.datetime.now())
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Warned By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warns", value=str(len(warn_data[uid])), inline=False)
    log_ch = interaction.guild.get_channel(MOD_LOG_CHANNEL_ID)
    if log_ch: await log_ch.send(embed=embed)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warns", description="Check warns for a user")
@app_commands.describe(user="User to check warns for")
async def warns(interaction: Interaction, user: discord.Member):
    warn_data = await load_warns()
    uid = str(user.id)
    if uid not in warn_data or not warn_data[uid]:
        return await interaction.response.send_message(f"✅ {user.mention} has no warnings.", ephemeral=True)
    description = ""
    for i, w in enumerate(warn_data[uid], 1):
        description += f"**{i}.** {w['reason']} — by <@{w['by']}>\n"
    embed = Embed(title=f"⚠️ Warns for {user}", description=description, color=Color.yellow())
    embed.set_footer(text=f"Total Warns: {len(warn_data[uid])}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearwarns", description="Clear all warns for a user (Manager only)")
@app_commands.describe(user="User to clear warns for")
async def clearwarns(interaction: Interaction, user: discord.Member):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ Only Managers can use this command.", ephemeral=True)
    warn_data = await load_warns()
    uid = str(user.id)
    if uid in warn_data: del warn_data[uid]
    await save_warns(warn_data)
    await interaction.response.send_message(f"✅ All warns cleared for {user.mention}")
@bot.tree.command(name="whatismm", description="Explains what a middleman is")
async def whatismm(interaction: Interaction):
    embed = Embed(
        title="ℹ️ What is a Middleman?",
        description="• A middleman is a **trusted go-between** who holds payment until the seller delivers goods or services.\n\n• The funds are released once the buyer confirms everything is as agreed.\n\n• This process helps **prevent scams, build trust, and resolve disputes**.\n\n• Common in **valuable games, real-life money trades, in-game currency, and collectibles**.\n\n• Only works safely if the middleman is **reputable and verified**.",
        color=Color.blurple()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)
    SUPPORT_STAFF_ROLE_ID = 1487831645603233974

class SupportTicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔵 Open a ticket!", style=discord.ButtonStyle.primary, custom_id="persistent:open_support_ticket")
    async def open_support_ticket(self, interaction: Interaction, button: Button):
        category = interaction.guild.get_channel(TICKETS_CATEGORY_ID)
        if not category:
            return await interaction.response.send_message("❌ Ticket category configuration missing.", ephemeral=True)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            interaction.guild.get_role(SUPPORT_STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)
        }

        channel = await interaction.guild.create_text_channel(
            name=f"support-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        bot.active_tickets[str(channel.id)] = {"owner": interaction.user.id, "claimed": None}
        await bot.save_data()

        embed = Embed(
            title="🔵 Support Ticket",
            description=(
                "✅ A support helper will be with you shortly!\n\n"
                "📌 Please provide:\n"
                "• Your issue or question\n"
                "• Any relevant screenshots or proof\n"
                "• Who was involved if applicable\n\n"
                "⬇️ A support staff member will claim your ticket shortly."
            ),
            color=Color.blue()
        )

        await channel.send(
            content=f"{interaction.user.mention} <@&{SUPPORT_STAFF_ROLE_ID}>",
            embed=embed,
            view=SupportTicketControls()
        )

        await interaction.response.send_message(f"✅ Your support ticket has been created: {channel.mention}", ephemeral=True)


class SupportTicketControls(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛡️ Claim", style=discord.ButtonStyle.success, custom_id="persistent:claim_support_ticket")
    async def claim(self, interaction: Interaction, button: Button):
        tid = str(interaction.channel.id)
        data = bot.active_tickets.get(tid)
        if not data:
            return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
        if data["claimed"]:
            return await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
        if not has_role(interaction.user, SUPPORT_STAFF_ROLE_ID) and not is_manager(interaction):
            return await interaction.response.send_message("❌ Only Support Staff can claim this ticket.", ephemeral=True)
        data["claimed"] = interaction.user.id
        await bot.save_data()
        button.label = "✅ Claimed"
        button.disabled = True
        button.style = discord.ButtonStyle.secondary
        await interaction.channel.set_permissions(interaction.user, send_messages=True, attach_files=True)
        embed = interaction.message.embeds[0]
        embed.add_field(name="Claimed By", value=interaction.user.mention, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="persistent:close_support_ticket")
    async def close(self, interaction: Interaction, button: Button):
        await close_ticket_logic(interaction)


@bot.tree.command(name="setupsupportticket", description="Deploy the Support ticket panel in this channel")
async def setupsupportticket(interaction: Interaction):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ No permission. Only Managers can use this.", ephemeral=True)

    embed = Embed(
        title="💎 Support Ticket",
        description=(
            "By opening a support ticket, a support helper will help you with your problems.\n\n"
            "**If a MM scammed you, or someone scammed you**\n"
            "Any other reasons we will also help you with."
        ),
        color=Color.blue()
    )

    await interaction.channel.send(embed=embed, view=SupportTicketPanel())
       await interaction.response.send_message("✅ Support ticket panel deployed successfully.", ephemeral=True)
if __name__ == "__main__":
    bot.run(os.environ.get("BOT_TOKEN"))
