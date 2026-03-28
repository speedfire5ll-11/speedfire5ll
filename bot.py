import discord
from discord.ext import commands
from discord import app_commands, Embed, Color, Interaction, Object, ui
from discord.ui import View, Button
import datetime
import json
import os
import asyncio
import aiofiles

# ---------------- CONFIG ----------------
# It is recommended to use environment variables for the token in production.
TOKEN = os.environ.get("BOT_TOKEN")
GUILD_ID = 1474846906369966195

# Role and Channel Constants
TICKETS_CATEGORY_ID = 1469421492231208992
TRANSCRIPT_CHANNEL_ID = 1469395437344526589
VOUCH_CHANNEL_ID = 1469095057780117617
INFO_ROLE_ID = 1469085194098180333
MM_ROLE_ID = 1469099833016062116
MANAGER_ROLE_ID = 1469101376054362245
INFO_LOG_CHANNEL_ID = 1469670001228120200
BAN_LOG_CHANNEL_ID = 1470054668129276049

VOUCH_DATA_FILE = "vouches.json"
TICKET_DATA_FILE = "tickets.json"

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
        
        # Register persistent views so buttons work after bot restarts
        self.add_view(TicketPanel())
        self.add_view(TicketControls())
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
                "⬇️ a middle man will claim ur ticket shortly."
            ),
            color=Color.blurple()
        )

        await channel.send(
            content=f"{interaction.user.mention} <@&{MM_ROLE_ID}>",
            embed=embed,
            view=TicketControls()
        )

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
                "You're a hitter now. A hitter is someone that got scammed by us, and goes out to scam others. "
                "In other words, you're now a scammer."
            ),
            color=Color.gold(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(
            name=":question: What should I do?",
            value=(
                "You need to go and advertise trades on other servers. Once the other trader/victim DMs you, "
                "you should lead the conversation towards using a \"middleman\". Once they agree, you'd send "
                "them our server, and create a ticket. Once you create the ticket, a random middleman will come to assist you."
            ),
            inline=False
        )
        embed.add_field(
            name=":moneybag: How do I get profit?",
            value=(
                "After you hit/scam for an item, you and the Middleman will split the item 50/50. If the hit was "
                "two items, you get one and the middleman gets one. The Middleman gets to decide the split "
                "as long as it's 50/50."
            ),
            inline=False
        )
        embed.add_field(
            name=":thinking: Can I become a middleman?",
            value="Absolutely, you can become a Middleman but it does not come free. Check rank-up-info to know the requirements to rank up.",
            inline=False
        )
        embed.set_footer(text="Seize the opportunity.")

        try:
            await self.target.send(embed=embed)
        except: pass

        await interaction.response.send_message(f"{self.target.mention} has accepted the opportunity and become a hitter.")
        
        log_ch = interaction.guild.get_channel(INFO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(
                title="Info Command Used",
                description=f"**User:** {self.target}\n**Staff:** {self.author}\n**Status:** Accepted",
                color=Color.green(),
                timestamp=datetime.datetime.now()
            )
            await log_ch.send(embed=log_embed)
        self.stop()

    @ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Only the targeted user can respond to this.", ephemeral=True)
        
        await interaction.response.send_message(f"{self.target.mention} has declined the offer.")
        
        log_ch = interaction.guild.get_channel(INFO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(
                title="Info Command Used",
                description=f"**User:** {self.target}\n**Staff:** {self.author}\n**Status:** Declined",
                color=Color.red(),
                timestamp=datetime.datetime.now()
            )
            await log_ch.send(embed=log_embed)
        self.stop()

# ---------------- CORE LOGIC ----------------

async def close_ticket_logic(interaction: Interaction):
    tid = str(interaction.channel.id)
    data = bot.active_tickets.get(tid)
    
    if not data:
        return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)

    if not is_mm(interaction) and data["owner"] != interaction.user.id:
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

@bot.tree.command(name="info", description="shows middle man info")
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
            "Most people in this server started out the same way. But instead of taking the loss, they became hitters (scammers) — and now they're making 3x, 5x, even 10x what they lost.\n\n"
            "This is your chance to turn a setback into serious profit.\n\n"
            "You now have access to the staff chat and other hitter channels. Head to the main guide channel to learn how to start.\n\n"
            "⏰ Every minute you wait is profit missed.\n\n"
            "Need help getting started? Ask in the support system channel.\n\n"
            f"@{user.mention} do you want to accept this opportunity and become a hitter?\n\n⏳ You have 1 minute to respond. The decision is yours. Make it count."
        ),
        color=Color.red()
    )

    await interaction.response.send_message(content=user.mention, embed=embed, view=InfoView(user, interaction.user))

@bot.tree.command(name="faq", description="View frequently asked questions and community support info")
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
        description=(
            "🚫 No Refunds Once Confirmed\n📸 Proof May Be Required\n⚖️ No Illegal Items\n🛡️ Scams and Disputes\n💰 Fees"
        ),
        color=Color.blurple()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch", description="Submit a professional vouch for a trader or middleman")
@app_commands.describe(user="User to vouch for", reason="Reason for the vouch")
async def vouch(interaction: Interaction, user: discord.Member, reason: str):
    uid = str(user.id)
    if uid not in bot.vouch_data: bot.vouch_data[uid] = {"count": 0, "vouches": []}
    bot.vouch_data[uid]["count"] += 1
    bot.vouch_data[uid]["vouches"].append({"voucher": interaction.user.id, "reason": reason})
    await bot.save_data()
    
    ch = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if ch:
        embed = Embed(
            title="📝 New Vouch",
            description=(f"**Voucher:** {interaction.user}\n**Vouched User:** {user}\n**Reason:** {reason}\n**Total Vouches:** {bot.vouch_data[uid]['count']}"),
            color=Color.green(),
            timestamp=datetime.datetime.now()
        )
        await ch.send(embed=embed)
    await interaction.response.send_message(f"✅ Your vouch for {user.mention} has been recorded.", ephemeral=True)

@bot.tree.command(name="stats", description="Check the total vouches and history for a specific user")
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
@app_commands.describe(user="User", role="Role", action="add or remove")
async def managerole(interaction: Interaction, user: discord.Member, role: discord.Role, action: str):
    if not is_manager(interaction): 
        return await interaction.response.send_message("❌ Only Managers can use this command.", ephemeral=True)
    if action.lower() == "add":
        await user.add_roles(role)
        await interaction.response.send_message(f"✅ {role.name} added to {user.mention}")
    elif action.lower() == "remove":
        await user.remove_roles(role)
        await interaction.response.send_message(f"✅ {role.name} removed from {user.mention}")
    else:
        await interaction.response.send_message("❌ Action must be 'add' or 'remove'.", ephemeral=True)

@bot.tree.command(name="manageban", description="Ban or unban a user from the guild (Management only)")
@app_commands.describe(user="User ID or mention", action="ban or unban")
async def manageban(interaction: Interaction, user: str, action: str):
    if not is_manager(interaction): 
        return await interaction.response.send_message("❌ Only Managers can use this command.", ephemeral=True)
    
    try:
        uid_str = user.replace('<@','').replace('>','').replace('!','').replace('&','')
        uid = int(uid_str)
        
        log_ch = interaction.guild.get_channel(BAN_LOG_CHANNEL_ID)
        
        if action.lower() == "ban":
            try:
                target_user = await bot.fetch_user(uid)
            except:
                target_user = f"Unknown User ({uid})"

            await interaction.guild.ban(discord.Object(id=uid), reason=f"Banned by {interaction.user}")
            await interaction.response.send_message(f"✅ User ID `{uid}` has been banned.")
            
            if log_ch:
                log_embed = Embed(title="🛡️ Member Banned", color=Color.red(), timestamp=datetime.datetime.now())
                log_embed.add_field(name="Target User", value=f"{target_user}", inline=True)
                log_embed.add_field(name="User ID", value=f"`{uid}`", inline=True)
                log_embed.add_field(name="Staff Member", value=f"{interaction.user.mention}", inline=False)
                log_embed.set_footer(text="Ban Management System")
                await log_ch.send(embed=log_embed)

        elif action.lower() == "unban":
            try:
                target_user = await bot.fetch_user(uid)
            except:
                target_user = f"Unknown User ({uid})"

            await interaction.guild.unban(discord.Object(id=uid), reason=f"Unbanned by {interaction.user}")
            await interaction.response.send_message(f"✅ User ID `{uid}` has been unbanned.")
            
            if log_ch:
                log_embed = Embed(title="🔓 Member Unbanned", color=Color.green(), timestamp=datetime.datetime.now())
                log_embed.add_field(name="Target User", value=f"{target_user}", inline=True)
                log_embed.add_field(name="User ID", value=f"`{uid}`", inline=True)
                log_embed.add_field(name="Staff Member", value=f"{interaction.user.mention}", inline=False)
                log_embed.set_footer(text="Ban Management System")
                await log_ch.send(embed=log_embed)
        else:
            await interaction.response.send_message("❌ Action must be 'ban' or 'unban'.", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("❌ Invalid User ID or mention provided.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

if __name__ == "__main__":
    bot.run(os.environ.get("BOT_TOKEN"))
