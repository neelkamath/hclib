"""Wrapper for the hack.chat API."""

import json
import re
import ssl
import threading
import time

import websocket


class HackChat(object):
    """This receives and sends data from and to hack.chat."""

    def __init__(self, callback, nick, channel, pwd=None,
                 url="wss://hack.chat/chat-ws", require_cert=True):
        """Initializes values.

        Keyword arguments:
        callback -- <function>; name of function to receive data
        nick -- <str>; nickname to use upon connecting
        channel -- <str>; the channel to connect to
        pwd -- <str>; password that generates a tripcode upon
                entering
        url -- <str>; The hack.chat instance. Custom instances may lack
               certain features. If you are connecting to a custom
               instances and are aware of features not implemented in
               the main instance, you can use the <send_custom> method
               to use them.
        require_cert -- <bool>; set to <True> to prevent connecting
                        if the websites' certificate is invalid

        <callback> may recieve one of the following <dict>s sans prior
        usage of a method in this class, such as when a hack.chat sends
        a warning:
        {
            "type": "message",
            "nick": <str>; the senders' nickname,
            "text": <str>; the senders' message,
            "trip": <str>; the senders' tripcode if the sender has one
        },
        {
            "type": "online add",
            "nick": <str>; nickname of user who just joint the channel
        },
        {
            "type": "online remove",
            "nick": <str>; nickname of user who just left the channel
        },
        {
            "type": "invite",
            "nick": <str>; the nickname of user who invited you to a
                    channel (might be your own if you invited someone
                    else),
            "channel": <str>; name of the channel invited to
        },
        {
            "type": "banned",
            "nick": <str>; the nickname of the banned user
        },
        {
            "type": "unbanned",
            "ip": <str>; the IP address of the unbanned user
        },
        {
            "type": "broadcast",
            "text": <str>; the message broadcasted to hack.chat
        },
        {
            "type": "warn",
            "warning": <str>; an explanation of why you have been
                        warned
        },
        {
            "type": "error",
            "error": <str>; the websocket error
        }
        """
        self._callback = callback
        self._nick = nick
        self._channel = channel
        self._pwd = pwd
        self._url = url
        self._onlineUsers = []
        self._ws = websocket.WebSocketApp(self._url,
                                          on_message=self._on_message,
                                          on_error=self._on_error)
        self._ws.on_open = self._on_open
        opt = None if require_cert else {"cert_reqs": ssl.CERT_NONE}
        self._ws.run_forever(sslopt=opt)

    @property
    def nick(self):
        """The nickname being used on <channel>."""
        return self._nick

    @property
    def channel(self):
        """The hack.chat channel connected to."""
        return self._channel

    @property
    def pwd(self):
        """The password used."""
        return self._pwd

    @property
    def url(self):
        """The hack.chat instance connected to."""
        return self._url

    @property
    def onlineUsers(self):
        """"A <list> of nicknames (<str>) of users online."""
        return self._onlineUsers

    def _on_open(self, _):
        """Joins the hack.chat channel and starts pinging."""
        nick = self._format_nick(self._nick, self._pwd)
        data = {"cmd": "join", "channel": self._channel, "nick": nick}
        self._send_packet(data)
        self._thread = True
        threading.Thread(target=self._ping).start()

    def _format_nick(self, nick, pwd=None):
        """Returns the hack.chat nickname (e.g, "neel#my_password").

        Keyword arguments:
        nick -- <str>; the nickname
        pwd -- <str>; optional password
        """
        if pwd:
            nick += "#{}".format(pwd)
        return nick

    def _on_error(self, err):
        """Handles websocket errors."""
        self._callback(self, {"type": "error", "error": err})

    def _ping(self):
        """Pings periodically to retain the websocket connection."""
        while True:
            time.sleep(50)
            if self._thread:
                self._send_packet({"cmd": "ping"})

    def _on_message(self, _, msg):
        """Sends and receives data to the callback function."""
        result = json.loads(msg)
        if result["cmd"] == "chat":
            data = {"type": "message", "nick": result["nick"],
                    "text": result["text"]}
            if "trip" in result:
                data["trip"] = result["trip"]
            self._callback(self, data)
        elif result["cmd"] == "onlineSet":
            self._onlineUsers += result["nicks"]
        elif result["cmd"] == "onlineAdd":
            self._onlineUsers.append(result["nick"])
            self._callback(self, {"type": "online add",
                                 "nick": result["nick"]})
        elif result["cmd"] == "onlineRemove":
            self._onlineUsers.remove(result["nick"])
            self._callback(self, {"type": "online remove",
                                 "nick": result["nick"]})
        elif result["cmd"] == "info" and " invited " in result["text"]:
            if "You invited " in result["text"]:
                name = self._nick
            else:
                space = re.search(r"\s", result["text"])
                name = result["text"][:space.start()]
            link = re.search(r"\?", result["text"])
            channel = result["text"][link.end():]
            self._callback(self, {"type": "invite", "nick": name,
                                 "channel": channel})
        elif result["cmd"] == "info" and " IPs " in result["text"]:
            data = result["text"].split()
            self._callback(self, {"type": "stats", "IPs": data[0],
                                 "channels": data[4]})
        elif result["cmd"] == "info" and "Banned " in result["text"]:
            nick = result["text"][len("Banned "):]
            self._callback(self, {"type": "banned", "nick": nick})
        elif result["cmd"] == "info" and "Unbanned " in result["text"]:
            ip = result["text"][len("Unbanned "):]
            self._callback(self, {"type": "unbanned", "ip": ip})
        elif (result["cmd"] == "info"
              and "Server broadcast: " in result["text"]):
            txt = result["text"][len("Server broadcast: "):]
            self._callback(self, {"type": "broadcast", "text": txt})
        elif result["cmd"] == "info":
            self._callback(self, {"type": "list users",
                                 "text": result["text"]})
        elif result["cmd"] == "warn":
            data = {"type": "warn", "warning": result["text"]}
            if "Could not find " in result["text"]:
                data["warning"] = "user to ban not found"
                data["nick"] = result["text"][len("Could not find "):]
            self._callback(self, data)

    def _send_packet(self, data):
        """Sends <data> (<dict>) to hack.chat."""
        self._ws.send(json.dumps(data))

    def send_custom(self, data):
        """Sends the custom command, <data> (<dict>), to hack.chat.

        This can be used when there isn't a method in this class that
        supports the required feature (such as when a custom instance
        is being used or the library hasn't updated for a brand new
        feature yet).
        """
        self._send_packet(data)

    def chat(self, msg):
        """Send <msg> (<str>) to <channel>.

        The following data may be sent to the callback function.
            {
                "type": "warn",
                "warning": "You are sending too much text. Wait a "
                           + "moment and try again.\nPress the up "
                           + "arrow key to restore your last message."
            }
        """
        self._send_packet({"cmd": "chat", "text": msg})

    def invite(self, nick):
        """Invites <nick> (<str>) to a randomly generated channel.

        This invite will only be visible to <nick>. The callback
        function will receive the data such as the channel.
        A warning having one of the following formats might be sent to
        the callback function.
            {
                "type": "warn",
                "warning": "You are sending invites too fast. Wait a "
                           + "moment before trying again."
            }
            {
                "type": "warn",
                "warning": "Could not find user in channel"
            }
        """
        self._send_packet({"cmd": "invite", "nick": nick})

    def get_stats(self):
        """Sends statistics to the callback function.

        This is the legacy method and <get_more_stats> should be used
        when possible.

        The following data will be sent to the callback function.
            {
                "type": "stats",
                "IPs": <str>; number of unique IPs connected to
                       hack.chat,
                "channels": <str>; number of channels on hack.chat
            }
        """
        self._send_packet({"cmd": "stats"})

    def ban(self, nick):
        """Bans <nick> (<str>) from hack.chat for 24 hours.

        <pwd> must be that of a moderators' or admins' to use this.
        You cannot ban a moderator or admin.
        The callback function will receive one of the following.
            {
                "type": "warn",
                "warning": "user to ban not found",
                "nick": <str>; nickname of user to ban that wasn't found
            }
            {
                "type": "warn",
                "warning": "Cannot ban moderator"
            }
        """
        self._send_packet({"cmd": "ban", "nick": nick})

    def unban(self, data):
        """Unbans a user.

        Keyword arguments:
        data -- <str>; the IP or hash of the user to unban

        <pwd> must be that of a moderators' or admins' to use this.

        The callback function will receive the following data.
            {
                "type": "unbanned"
                "ip": <str>; IP of unbanned user
            }
        """
        self._send_packet({"cmd": "unban", "ip": data})

    def list_users(self):
        """Lists users (<pwd> must be that of an admins' to use this).

        The callback function will receive the following data.
            {
                "type": "list users",
                "text": <str>; online users
            }
        """
        self._send_packet({"cmd": "listUsers"})

    def shout(self, text):
        """Sends <text> (<str>) to hack.chat.

        <pwd> must be that of an admins' to use this.

        The following data will be sent to the callback function.
        {
            "type": "broadcast",
            "text": <str>; the message broadcasted
        }
        """
        self._send_packet({"cmd": "broadcast", "text": text})

    def leave(self):
        """Leaves the channel currently connected to."""
        self._thread = False
        self._ws.close()

    def disconnect(self):
        """Forces a disconnect. Use <leave> whenever possible."""
        self._send_packet({"cmd": "disconnect"})

    def change_nick(self, new_nick):
        """Changes <nick> to <new_nick> (<str>)."""
        self._send_packet({"cmd": "changenick", "nick": new_nick})

    def join(self, new_channel, nick, pwd=None):
        """Joins a new channel.

        Keyword arguments:
        new_channel: <str>; the channel to connect to
        nick: <str>; the nickname to use
        pwd: <str>; the (optional) password to use
        """
        self._send_packet({"cmd": "join", "channel": new_channel,
                           "nick": self._format_nick(nick, pwd)})

    def get_more_stats(self):
        """Sends hack.chat stats to <callback>."""
        self._send_packet({"cmd": "morestats"})

    def move(self, new_channel):
        """Changes <channel> to <new_channel> (<str>)."""
        self._send_packet({"cmd": "move", "channel": new_channel})

    def get_help(self, is_category, item):
        """Sends documentation on <item> to <callback>.

        This can be used for programmatically accessing documentation.

        Keyword arguments:
        is_category -- <bool>; Set this to <True> if <item> is for
                       getting documentation on a permission level and
                       <False> if <item> is for getting documentation on
                       a command.
        item -- <str>; If <is_category> is <True>, this should be one of
                       <"core">, <"mod"> or <"admin"> to get
                       documentation on the commands specific to that
                       permission level. If <is_category> is <False>,
                       this should be the name of the command to get
                       documentation on.
        """
        data = {"cmd": "help"}
        if is_category:
            data["category"] = item
        else:
            data["command"] = item
        self._send_packet(data)

    def kick(self, nick):
        """Kicks <nick> (<str>) to another channel.

        Your <pwd> must be that of a mod's to use this.
        """
        self._send_packet({"cmd": "kick", "nick": nick})

    def add_mod(self, nick):
        """Makes the user with <nick> (<str>) a mod.

        <pwd> must be that of an admin's to use this.

        The user being promoted must also have a trip code.
        """
        self._send_packet({"cmd": "addmod", "nick": nick})

    def reload(self):
        """Reloads hack.chat.

        (Re)loads any new commands into memory and outputs errors, if
        any. You must be an admin to use this.
        """
        self._send_packet({"cmd": "reload"})

    def save_config(self):
        """(For admins only). Saves hack.chat's current config."""
        self._send_packet({"cmd": "saveconfig"})
