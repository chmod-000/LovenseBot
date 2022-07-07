# <img src="https://user-images.githubusercontent.com/105820491/177657922-648adf47-f1c8-49c1-a2a5-5040b16bd7ff.png" width="80px" height="80px"> LovenseBot
Discord bot for controlling Lovense toys. Requires a Lovense developer account with callback URL set

## User Flow
1. The `/lovense connect` command will generate a QR code, which the user scans with their Lovense Remote app and confirms they want to connect
2. The user's toys are then added into a per-guild pool of toys, a summary of which can be displayed with `/lovense status`
3. Commands such as `/lovense vibrate` and `/lovense pattern` will activate all toys in the guild's pool
4. When the user wants to disconnect, they press the Stop button in their Lovense Remote app

## Technical flow
1. When the user scans the QR code and confirms they want to connect, a POST request is sent from their app to the callback URL defined at https://www.lovense.com/user/developer/info, in the format:
      ```
      {
        uid: User ID
        utoken: xxx, // User token on your application
        domain: 192-168-0-11.lovense.club, // the domain name of the Lovense Connect app
        httpPort: 34567, // HTTP server port
        wsPort: 34567, // HTTP server port
        httpsPort: 34568, //HTTPS server port
        wssPort: 34568, // HTTPS server port
        platform: 'ios', // the Lovense Connect platform e.g. Android/iOS
        appVersion: '2.3.6', //the Lovense Connect version
        version: 101, // the protocol version e.g. 101
        toys:{
            toyId:{
              id: xxxxxx, // Toy's ID
              name:"lush", // toy's name
              nickName: "nickName"
              status: 1 // e.g. 1/0
            }
          }
      }
      ```
      If heartbeats are enabled in the developer dashboard, this request will be repeated every heartbeat interval. In this instance, the uid is generated as {GUILD_ID}:{USER_ID}

2. Until the user cancels control, their toys are be controlled with POST requests to https://api.lovense.com/api/lan/v2/command, specifying their UID (or a comma-separated list of UIDs to control multiple at once), the type of action (e.g vibrate, rotate), the strength and the duration. This is handled by the ToyController class. 
3. If a toy has been disconnected (i.e not sending heartbeat requests) for 60 seconds or more (see ToyController.\_refresh()), it will be removed from the pool.

## Setup
1. Create a developer account at https://www.lovense.com. Configure the callback URL so it can be served by the Callbacks class
2. Create a developer account at https://discord.com/developers, create a bot and invite it to a server with the `bot` and `application.commands` scopes
3. Install dependencies from requirements.txt (virtualenv optional but helpful)
4. Run `bot.py`, supplying environment variables `LOVENSE_DEVELOPER_TOKEN` and `TOKEN` (your Discord bot's authentication token). Optionally also supply `GUILD_IDS` (a comma-separated list of guild IDs for commands to be registered against) and `DEBUG_GUILD_ID` (commands which would otherwise be set globally will instead be registered to this guild)
