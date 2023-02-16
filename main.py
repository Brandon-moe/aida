import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import *
import requests
import discord
import json
import os
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SPOTIFY_TOKEN = os.getenv('SPOTIFY_TOKEN')
REFRESH_TOKEN = os.getenv('REFRESH_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
CODE = os.getenv('CODE')
activity = discord.Game(name="a!help")
client = commands.Bot(command_prefix='a!', activity=activity, help_command=None,intents=discord.Intents.all())
bot_name = "aida"
#Aida's user ID on spotify. All created playlists tied to her account (easier to implement, same functionality)
user_id = "31akqejmk7b76eliw4uqxxybvb7a"

def get_auth_code():
    #url = f"https://accounts.spotify.com/authorize?client_id=b016c3b82e3c461f84f675c6d8c90bbf&response_type=code&redirect_uri=https://www.google.com"
    url = "https://accounts.spotify.com/api/token"
    body = {
    "grant_type":"refresh_token",
    "refresh_token":REFRESH_TOKEN,
    "client_id":CLIENT_ID,
    "client_secret":CLIENT_SECRET,
    "redirect_uri":"https://www.google.com"
    }
    response = requests.post(url,data=body)
    response = json.loads(response.text.encode("utf-8"))
    print(response)
    query = f'''UPDATE AUTH SET token = "{response["access_token"]}"'''
    execute(query)
    # SPOTIFY_TOKEN = response["access_token"]
    return

@client.event
async def on_ready():
    query = f'''CREATE TABLE IF NOT EXISTS PLAYLISTS(
    guild_id VARCHAR PRIMARY KEY,
    playlist_id VARCHAR NOT NULL
    )'''
    execute(query)
    query = f'''CREATE TABLE IF NOT EXISTS AUTH(
    token VARCHAR PRIMARY KEY
    )'''
    execute(query)
    commit()
    print(
        f'{bot_name} has logged on.:\n'
    )
#display embedded help menu
@client.command()
async def help(ctx):
    embedVar = discord.Embed(title="Available Commands", color=0xA020F0)
    embedVar.add_field(name="help",
    value='''Displays this message''',
    inline=False)
    embedVar.add_field(name="createplaylist {name}",
    value='''Create a playlist for this server (if one does not already exist)''',
    inline=False)
    embedVar.add_field(name="renameplaylist {name}",
    value='''Rename the playlist in this server''',
    inline=False)
    embedVar.add_field(name="search {name}",
    value='''Search for a track on Spotify to add to the playlist''',
    inline=False)
    await ctx.send(embed = embedVar)

@client.command()
async def viewplaylist(ctx):
    playlist_id = await get_playlist_id(ctx)
    if playlist_id:
        await ctx.send(f"https://open.spotify.com/playlist/{playlist_id}")
    else:
        await ctx.send(f"There currently is no playlist configured for this server. Please use the createplaylist command")

async def get_token():
    query = f'''SELECT * FROM AUTH'''
    return record(query)[0]

async def get_playlist_id(ctx):
    query = f'''SELECT playlist_id FROM PLAYLISTS WHERE guild_id = {ctx.guild.id}'''
    playlist_id = record(query)
    if playlist_id:
        return playlist_id[0]
    else:
        return 0

@client.command()
@commands.has_permissions(administrator=True)
async def renameplaylist(ctx,name):
    SPOTIFY_TOKEN = await get_token()
    playlist_id = await get_playlist_id(ctx)
    if not playlist_id:
        await createplaylist(ctx,name)
        return
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    body = {
      "name": name,
    }
    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SPOTIFY_TOKEN}"
    }
    response = requests.put(url, headers=headers, data=json.dumps(body))
    #if auth expired, re-gen and try again
    if response.status_code == 401:
        get_auth_code()
        await renameplaylist(ctx,name)
        return
    await ctx.send(f"Playlist name updated to {name}.")
    return

@client.command()
@commands.has_permissions(administrator=True)
async def createplaylist(ctx,name):
    playlist_id = await get_playlist_id(ctx)
    if playlist_id:
        await ctx.send(f"There is already a playlist in this server:")
        await ctx.send(f"https://open.spotify.com/playlist/{playlist_id}")
        return
    SPOTIFY_TOKEN = await get_token()
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SPOTIFY_TOKEN}"
    }
    body = {
    "name": name,
    "description": "",
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    #if auth expired, re-gen and try again
    if response.status_code == 401:
        get_auth_code()
        await createplaylist(ctx,name)
        return
    response = json.loads(response.text.encode('utf8'))
    await ctx.send(f"Playlist {name} created successfully:")
    await ctx.send(response["external_urls"]["spotify"])
    playlist_id = response["external_urls"]["spotify"].split("/")[-1]
    query = f'''INSERT INTO PLAYLISTS VALUES ('{ctx.guild.id}','{playlist_id}')'''
    execute(query)
    commit()

#add selected song to playlist
async def addsong(ctx,id):
    if await checkduplicates(id,ctx):
        await ctx.send("This song is already in the playlist")
        return
    SPOTIFY_TOKEN = await get_token()
    playlist_id = await get_playlist_id(ctx)
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?uris=spotify:track:{id}"
    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SPOTIFY_TOKEN}"
    }
    response = requests.post(url, headers=headers)
    #if auth expired, re-gen and try again
    if response.status_code == 401:
        get_auth_code()
        await addsong(ctx,id)
        return
    response = json.loads(response.text.encode('utf8'))
    await ctx.send(f"Song added successfully:")
    await ctx.send(f"https://open.spotify.com/track/{id}")

#check if song already in playlist before adding it
async def checkduplicates(id,ctx):
    SPOTIFY_TOKEN = await get_token()
    playlist_id = await get_playlist_id(ctx)
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SPOTIFY_TOKEN}"
    }
    response = requests.get(url,headers=headers)
    return id in response.text

#search for track to add to playlist
@client.command()
async def search(ctx,name):
    SPOTIFY_TOKEN = await get_token()
    url = f"https://api.spotify.com/v1/search?q={name}&type=track"
    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SPOTIFY_TOKEN}"
    }
    response = requests.get(url, headers=headers)
    #if auth expired, re-gen and try again
    if response.status_code == 401:
        get_auth_code()
        await search(ctx,name)
        return
    response = json.loads(response.text.encode('utf8'))
    tracks = response["tracks"]["items"]
    #display top 5 search results in embed window
    embedVar = discord.Embed(title="Search Results", color=0xA020F0)
    embedVar.add_field(name="",value="Click a button to add a song to the playlist.")
    track_ids = []
    for idx,elem in enumerate(tracks[:5]):
        embedVar.add_field(name=f'{idx+1}: {elem["name"]}',
        value=f'{elem["artists"][0]["name"]} {elem["album"]["name"]}',
        inline=False)
        track_ids.append(elem["external_urls"]["spotify"].split("/")[-1])
    if len(track_ids) == 0:
        await ctx.send("No search results found")
    else:
        view = SearchMenu(ctx,ctx.author,track_ids)
        await ctx.send(view=view,embed=embedVar)

class SearchMenu(discord.ui.View):
    def __init__(self,ctx,author,track_ids):
        super().__init__()
        self.value = None
        self.author = author
        self.tracks = track_ids
        self.ctx = ctx
    #create buttons menu
    @discord.ui.button(label="1", style=discord.ButtonStyle.grey)
    async def menu1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await addsong(self.ctx,self.tracks[0])
    @discord.ui.button(label="2", style=discord.ButtonStyle.grey)
    async def menu2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await addsong(self.ctx,self.tracks[1])
    @discord.ui.button(label="3", style=discord.ButtonStyle.grey)
    async def menu3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await addsong(self.ctx,self.tracks[2])
    @discord.ui.button(label="4", style=discord.ButtonStyle.grey)
    async def menu4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await addsong(self.ctx,self.tracks[3])
    @discord.ui.button(label="5", style=discord.ButtonStyle.grey)
    async def menu5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await addsong(self.ctx,self.tracks[4])
    #override, only command initializer can interact with buttons
    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.author.id

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
