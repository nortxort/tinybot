# -*- coding: utf-8 -*-
""" tinybot by nortxort (https://github.com/nortxort) """

import logging
import random
import re
import threading

import pinylib
from apis import youtube, soundcloud, lastfm, other, locals
from utilities import string_utili, media_manager, privacy_settings

CONFIG = {
    'prefix': '!',
    'key': '6348yss',
    'super_key': 'sd78fwetsd4r',
    'bot_msg_to_console': False,
    'auto_message_enabled': False,
    'public_cmds': True,
    'debug_to_file': False,
    'auto_message_interval': 300,
    'nick_bans': 'nick_bans.txt',
    'account_bans': 'account_bans.txt',
    'ban_strings': 'ban_strings.txt',
    'debug_file_name': 'tinybot_debug.log'
}

log = logging.getLogger(__name__)
__version__ = '4.0.2'


class TinychatBot(pinylib.TinychatRTMPClient):
    key = CONFIG['key']
    is_cmds_public = CONFIG['public_cmds']
    is_newusers_allowed = True
    is_broadcasting_allowed = True
    is_guest_entry_allowed = True
    is_guest_nicks_allowed = False
    privacy_settings = object
    # Media related.
    media_manager = media_manager.MediaManager()
    media_timer_thread = None
    search_list = []

    def on_join(self, join_info_dict):
        log.info('User join info: %s' % join_info_dict)
        user = self.add_user_info(join_info_dict)

        if join_info_dict['account']:
            tc_info = pinylib.tinychat.tinychat_user_info(join_info_dict['account'])
            if tc_info is not None:
                user.tinychat_id = tc_info['tinychat_id']
                user.last_login = tc_info['last_active']
            if join_info_dict['own']:
                self.console_write(pinylib.COLOR['red'], 'Room Owner %s:%d:%s' %
                                   (join_info_dict['nick'], join_info_dict['id'], join_info_dict['account']))
            elif join_info_dict['mod']:
                self.console_write(pinylib.COLOR['bright_red'], 'Moderator %s:%d:%s' %
                                   (join_info_dict['nick'], join_info_dict['id'], join_info_dict['account']))
            else:
                self.console_write(pinylib.COLOR['bright_yellow'], '%s:%d has account: %s' %
                                   (join_info_dict['nick'], join_info_dict['id'], join_info_dict['account']))

                badaccounts = pinylib.fh.file_reader(self.config_path(), CONFIG['account_bans'])
                if badaccounts is not None:
                    if join_info_dict['account'] in badaccounts:
                        if self._is_client_mod:
                            self.send_ban_msg(join_info_dict['nick'], join_info_dict['id'])
                            self.send_forgive_msg(join_info_dict['id'])
                            self.send_bot_msg('*Auto-Banned:* (bad account)')
        else:
            if join_info_dict['id'] is not self._client_id:
                if not self.is_guest_entry_allowed:
                    self.send_ban_msg(join_info_dict['nick'], join_info_dict['id'])
                    # remove next line to ban.
                    self.send_forgive_msg(join_info_dict['id'])
                    self.send_bot_msg('*Auto-Banned:* (guests not allowed)')
                else:
                    self.console_write(pinylib.COLOR['cyan'], '%s:%d joined the room.' %
                                       (join_info_dict['nick'], join_info_dict['id']))

    def on_joinsdone(self):
        if not self._is_reconnected:
            if CONFIG['auto_message_enabled']:
                self.start_auto_msg_timer()
        if self._is_client_mod:
            self.send_banlist_msg()
        if self._is_client_owner and self._room_type != 'default':
            threading.Thread(target=self.get_privacy_settings).start()

    def on_avon(self, uid, name):
        if not self.is_broadcasting_allowed:
            self.send_close_user_msg(name)
            self.console_write(pinylib.COLOR['cyan'], 'Auto closed broadcast %s:%s' % (name, uid))
        else:
            self.console_write(pinylib.COLOR['cyan'], '%s:%s is broadcasting.' % (name, uid))

    def on_nick(self, old, new, uid):
        old_info = self.find_user_info(old)
        old_info.nick = new
        if old in self._room_users.keys():
            del self._room_users[old]
            self._room_users[new] = old_info

        if str(old).startswith('guest-'):
            if self._client_id != uid:

                if str(new).startswith('guest-'):
                    if self._is_client_mod:
                        if not self.is_guest_nicks_allowed:
                            self.send_ban_msg(new, uid)
                            # remove next line to ban.
                            self.send_forgive_msg(uid)
                            self.send_bot_msg('*Auto-Banned:* (bot nick detected)')

                if str(new).startswith('newuser'):
                    if self._is_client_mod:
                        if not self.is_newusers_allowed:
                            self.send_ban_msg(new, uid)
                            # remove next line to ban.
                            self.send_forgive_msg(uid)
                            self.send_bot_msg('*Auto-Banned:* (wanker detected)')

                else:
                    bn = pinylib.fh.file_reader(self.config_path(), CONFIG['nick_bans'])
                    if bn is not None and new in bn:
                        if self._is_client_mod:
                            self.send_ban_msg(new, uid)
                            # remove next line to ban.
                            self.send_forgive_msg(uid)
                            self.send_bot_msg('*Auto-Banned:* (bad nick)')

                    else:
                        user = self.find_user_info(new)
                        if user is not None:
                            if user.account:
                                # Greet user with account name.
                                self.send_bot_msg('*Welcome* ' + new + ':' + str(uid) + ':' + user.account)
                            else:
                                self.send_bot_msg('*Welcome* ' + new + ':' + str(uid))

                        if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                            if not self.media_manager.is_mod_playing:
                                self.send_media_broadcast_start(self.media_manager.track().type,
                                                                self.media_manager.track().id,
                                                                time_point=self.media_manager.elapsed_track_time(),
                                                                private_nick=new)
        self.console_write(pinylib.COLOR['bright_cyan'], '%s:%s changed nick to: %s' % (old, uid, new))

    # Media Events.
    def on_media_broadcast_start(self, media_type, video_id, usr_nick):
        """
        A user started a media broadcast.
        :param media_type: str the type of media. youTube or soundCloud.
        :param video_id: str the youtube ID or soundcloud track ID.
        :param usr_nick: str the user name of the user playing media. NOTE: replace with self.user_obj.nick
        """
        if self.user.is_mod:
            self.cancel_media_event_timer()

            if media_type == 'youTube':
                _youtube = youtube.youtube_time(video_id, check=False)
                if _youtube is not None:
                    self.media_manager.mb_start(self.user.nick, _youtube)

            elif media_type == 'soundCloud':
                _soundcloud = soundcloud.soundcloud_track_info(video_id)
                if _soundcloud is not None:
                    self.media_manager.mb_start(self.user.nick, _soundcloud)

            self.media_event_timer(self.media_manager.track().time)
            self.console_write(pinylib.COLOR['bright_magenta'], '%s is playing %s %s' %
                               (usr_nick, media_type, video_id))

    def on_media_broadcast_close(self, media_type, usr_nick):
        """
        A user closed a media broadcast.
        :param media_type: str the type of media. youTube or soundCloud.
        :param usr_nick: str the user name of the user closing the media.
        """
        if self.user.is_mod:
            self.cancel_media_event_timer()
            self.media_manager.mb_close()
            self.console_write(pinylib.COLOR['bright_magenta'], '%s closed the %s' % (usr_nick, media_type))

    def on_media_broadcast_paused(self, media_type, usr_nick):
        """
        A user paused the media broadcast.
        :param media_type: str the type of media being paused. youTube or soundCloud.
        :param usr_nick: str the user name of the user pausing the media.
        """
        if self.user.is_mod:
            self.cancel_media_event_timer()
            self.media_manager.mb_pause()
            self.console_write(pinylib.COLOR['bright_magenta'], '%s paused the %s' % (usr_nick, media_type))

    def on_media_broadcast_play(self, media_type, time_point, usr_nick):
        """
        A user resumed playing a media broadcast.
        :param media_type: str the media type. youTube or soundCloud.
        :param time_point: int the time point in the tune in milliseconds.
        :param usr_nick: str the user resuming the tune.
        """
        if self.user.is_mod:
            self.cancel_media_event_timer()
            new_media_time = self.media_manager.mb_play(time_point)
            self.media_event_timer(new_media_time)

            self.console_write(pinylib.COLOR['bright_magenta'], '%s resumed the %s at: %s' %
                               (usr_nick, media_type, self.format_time(time_point)))

    def on_media_broadcast_skip(self, media_type, time_point, usr_nick):
        """
        A user time searched a tune.
        :param media_type: str the media type. youTube or soundCloud.
        :param time_point: int the time point in the tune in milliseconds.
        :param usr_nick: str the user time searching the tune.
        """
        if self.user.is_mod:
            self.cancel_media_event_timer()
            new_media_time = self.media_manager.mb_skip(time_point)
            if not self.media_manager.is_paused:
                self.media_event_timer(new_media_time)

            self.console_write(pinylib.COLOR['bright_magenta'], '%s time searched the %s at: %s' %
                               (usr_nick, media_type, self.format_time(time_point)))

    # Media Message Method.
    def send_media_broadcast_start(self, media_type, video_id, time_point=0, private_nick=None):
        """
        Starts a media broadcast.
        NOTE: This method replaces play_youtube and play_soundcloud
        :param media_type: str 'youTube' or 'soundCloud'
        :param video_id: str the media video ID.
        :param time_point: int where to start the media from in milliseconds.
        :param private_nick: str if not None, start the media broadcast for this username only.
        """
        mbs_msg = '/mbs %s %s %s' % (media_type, video_id, time_point)
        if private_nick is not None:
            self.send_undercover_msg(private_nick, mbs_msg)
        else:
            self.send_chat_msg(mbs_msg)

    # Message Method.
    def send_bot_msg(self, msg, use_chat_msg=False):
        """
        Send a chat message to the room.

        NOTE: If the client is moderator, send_owner_run_msg will be used.
        If the client is not a moderator, send_chat_msg will be used.
        Setting use_chat_msg to True, forces send_chat_msg to be used.

        :param msg: str the message to send.
        :param use_chat_msg: boolean True, use normal chat messages.
        False, send messages depending on weather or not the client is mod.
        """
        if use_chat_msg:
            self.send_chat_msg(msg)
        else:
            if self._is_client_mod:
                self.send_owner_run_msg(msg)
            else:
                self.send_chat_msg(msg)
        if CONFIG['bot_msg_to_console']:
            self.console_write(pinylib.COLOR['white'], msg)

    # Command Handler.
    def message_handler(self, msg_sender, decoded_msg):
        """
        Custom command handler.

        NOTE: Any method using a API should be started in a new thread.
        :param msg_sender: str the user sending a message
        :param decoded_msg: str the message
        """

        # Is this a custom command?
        if decoded_msg.startswith(CONFIG['prefix']):
            # Split the message in to parts.
            parts = decoded_msg.split(' ')
            # parts[0] is the command..
            cmd = parts[0].lower().strip()
            # The rest is a command argument.
            cmd_arg = ' '.join(parts[1:]).strip()

            # Super mod commands.
            if self.user.is_super:
                if cmd == CONFIG['prefix'] + 'mod':
                    threading.Thread(target=self.do_make_mod, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'rmod':
                    threading.Thread(target=self.do_remove_mod, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'dir':
                    threading.Thread(target=self.do_directory).start()

                elif cmd == CONFIG['prefix'] + 'p2t':
                    threading.Thread(target=self.do_push2talk).start()

                elif cmd == CONFIG['prefix'] + 'gr':
                    threading.Thread(target=self.do_green_room).start()

                elif cmd == CONFIG['prefix'] + 'crb':
                    threading.Thread(target=self.do_clear_room_bans).start()

            # Owner and super mod commands.
            if self.user.is_owner or self.user.is_super:
                if cmd == CONFIG['prefix'] + 'kill':
                    self.do_kill()

                elif cmd == CONFIG['prefix'] + 'reboot':
                    self.do_reboot()

            # Owner and bot controller commands.
            if self.user.is_owner or self.user.is_super or self.user.has_power:
                if cmd == CONFIG['prefix'] + 'mi':
                    self.do_media_info()

            # Mod and bot controller commands.
            if self.user.is_owner or self.user.is_super or self.user.is_mod \
                    or self.user.has_power:

                if cmd == CONFIG['prefix'] + 'rs':
                    self.do_room_settings()

                elif cmd == CONFIG['prefix'] + 'top':
                    threading.Thread(target=self.do_lastfm_chart, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'ran':
                    threading.Thread(target=self.do_lastfm_random_tunes, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'tag':
                    threading.Thread(target=self.search_lastfm_by_tag, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'close':
                    self.do_close_broadcast(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'clear':
                    self.do_clear()

                elif cmd == CONFIG['prefix'] + 'skip':
                    self.do_skip()

                elif cmd == CONFIG['prefix'] + 'del':
                    self.do_delete_playlist_item(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'rpl':
                    self.do_media_replay()

                elif cmd == CONFIG['prefix'] + 'mbpl':  # NEW
                    self.do_play_media()

                elif cmd == CONFIG['prefix'] + 'mbpa':  # NEW
                    self.do_media_pause()

                elif cmd == CONFIG['prefix'] + 'seek':  # NEW
                    self.do_seek_media(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'cm':
                    self.do_close_media()

                elif cmd == CONFIG['prefix'] + 'cpl':
                    self.do_clear_playlist()

                elif cmd == CONFIG['prefix'] + 'nick':
                    self.do_nick(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'topic':
                    self.do_topic(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'kick':
                    self.do_kick(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'ban':
                    self.do_ban(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'bn':
                    self.do_bad_nick(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'rmbn':
                    self.do_remove_bad_nick(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'bs':
                    self.do_bad_string(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'rmbs':
                    self.do_remove_bad_string(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'ba':
                    self.do_bad_account(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'rmba':
                    self.do_remove_bad_account(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'list':
                    self.do_list_info(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'uinfo':
                    self.do_user_info(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'yts':
                    threading.Thread(target=self.do_youtube_search, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'pyts':
                    self.do_play_youtube_search(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'cam':  # NEW
                    threading.Thread(target=self.do_cam_approve).start()

            # Public Commands (if enabled).
            if self.is_cmds_public or self.user.is_owner or self.user.is_super \
                    or self.user.is_mod or self.user.has_power:
                if cmd == CONFIG['prefix'] + 'fs':  # NEW
                    self.do_full_screen(cmd_arg)

                elif cmd == CONFIG['prefix'] + 'wp':  # NEW
                    self.do_who_plays()

                elif cmd == CONFIG['prefix'] + 'v':
                    self.do_version()

                elif cmd == CONFIG['prefix'] + 'help':
                    self.do_help()

                elif cmd == CONFIG['prefix'] + 't':
                    self.do_uptime()

                elif cmd == CONFIG['prefix'] + 'pmme':
                    self.do_pmme()

                elif cmd == CONFIG['prefix'] + 'q':
                    self.do_playlist_status()

                elif cmd == CONFIG['prefix'] + 'n':
                    self.do_next_tune_in_playlist()

                elif cmd == CONFIG['prefix'] + 'np':
                    self.do_now_playing()

                elif cmd == CONFIG['prefix'] + 'yt':
                    threading.Thread(target=self.do_play_youtube, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'pyt':
                    threading.Thread(target=self.do_play_private_youtube, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'sc':
                    threading.Thread(target=self.do_play_soundcloud, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'psc':
                    threading.Thread(target=self.do_play_private_soundcloud, args=(cmd_arg,)).start()

                # Tinychat API commands.
                elif cmd == CONFIG['prefix'] + 'spy':
                    threading.Thread(target=self.do_spy, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'acspy':
                    threading.Thread(target=self.do_account_spy, args=(cmd_arg,)).start()

                # Other API commands.
                elif cmd == CONFIG['prefix'] + 'urb':
                    threading.Thread(target=self.do_search_urban_dictionary, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'wea':
                    threading.Thread(target=self.do_weather_search, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'ip':
                    threading.Thread(target=self.do_whois_ip, args=(cmd_arg,)).start()

                elif cmd == CONFIG['prefix'] + 'm5c':  # NEW
                    threading.Thread(target=self.do_md5_hash_cracker, args=(cmd_arg,)).start()

                # Just for fun.
                elif cmd == CONFIG['prefix'] + 'cn':
                    threading.Thread(target=self.do_chuck_noris).start()

                elif cmd == CONFIG['prefix'] + '8ball':
                    self.do_8ball(cmd_arg)

            # Print command to console.
            self.console_write(pinylib.COLOR['yellow'], msg_sender + ': ' + cmd + ' ' + cmd_arg)
        else:
            #  Print chat message to console.
            self.console_write(pinylib.COLOR['green'], msg_sender + ': ' + decoded_msg)
            # Only check chat msg for bad string if we are mod.
            if self._is_client_mod:
                threading.Thread(target=self.check_msg_for_bad_string, args=(decoded_msg,)).start()

        # add msg to user object last_msg
        self.user.last_msg = decoded_msg

    # == Super Mod Commands Methods. ==
    def do_make_mod(self, account):
        """
        Make a tinychat account a room moderator.
        :param account str the account to make a moderator.
        """
        if self._is_client_owner:
            if len(account) is 0:
                self.send_bot_msg('*Missing account name.*')
            else:
                tc_user = self.privacy_settings.make_moderator(account)
                if tc_user is None:
                    self.send_bot_msg('*The account is invalid.*')
                elif not tc_user:
                    self.send_bot_msg('*The account is already a moderator.*')
                elif tc_user:
                    self.send_bot_msg('*' + account + ' was made a room moderator.*')

    def do_remove_mod(self, account):
        """
        Removes a tinychat account from the moderator list.
        :param account str the account to remove from the moderator list.
        """
        if self._is_client_owner:
            if self.user.is_super:
                if len(account) is 0:
                    self.send_bot_msg('*Missing account name.*')
                else:
                    tc_user = self.privacy_settings.remove_moderator(account)
                    if tc_user:
                        self.send_bot_msg('*' + account + ' is no longer a room moderator.*')
                    elif not tc_user:
                        self.send_bot_msg('*' + account + ' is not a room moderator.*')

    def do_directory(self):
        """ Toggles if the room should be shown on the directory. """
        if self._is_client_owner:
            if self.privacy_settings.show_on_directory():
                self.send_bot_msg('*Room IS shown on the directory.*')
            else:
                self.send_bot_msg('*Room is NOT shown on the directory.*')

    def do_push2talk(self):
        """ Toggles if the room should be in push2talk mode. """
        if self._is_client_owner:
            if self.privacy_settings.set_push2talk():
                self.send_bot_msg('*Push2Talk is enabled.*')
            else:
                self.send_bot_msg('*Push2Talk is disabled.*')

    def do_green_room(self):
        """ Toggles if the room should be in greenroom mode. """
        if self._is_client_owner:
            if self.privacy_settings.set_greenroom():
                self.send_bot_msg('*Green room is enabled.*')
                self._greenroom = True
            else:
                self.send_bot_msg('*Green room is disabled.*')
                self._greenroom = False

    def do_clear_room_bans(self):
        """ Clear all room bans. """
        if self._is_client_owner:
            if self.privacy_settings.clear_bans():
                self.send_bot_msg('*All room bans was cleared.*')

    # == Owner And Super Mod Command Methods. ==
    def do_kill(self):
        """ Kills the bot. """
        self.disconnect()

    def do_reboot(self):
        """ Reboots the bot. """
        self.reconnect()

    # == Owner And Bot Controller Commands Methods. ==
    def do_media_info(self):
        """ Shows basic media info. """
        if self._is_client_mod:
            self.send_owner_run_msg('*Track List Index:* ' + str(self.media_manager.track_list_index))
            self.send_owner_run_msg('*Playlist Length:* ' + str(len(self.media_manager.track_list)))
            self.send_owner_run_msg('*Current Time Point:* ' +
                                    self.format_time(self.media_manager.elapsed_track_time()))
            self.send_owner_run_msg('*Active Threads:* ' + str(threading.active_count()))
            self.send_owner_run_msg('*Is Mod Playing:* ' + str(self.media_manager.is_mod_playing))

    def do_room_settings(self):
        """ Shows current room settings. """
        if self._is_client_owner:
            settings = self.privacy_settings.current_settings()
            self.send_owner_run_msg('*Broadcast Password:* ' + settings['broadcast_pass'])
            self.send_owner_run_msg('*Room Password:* ' + settings['room_pass'])
            self.send_owner_run_msg('*Login Type:* ' + settings['allow_guests'])
            self.send_owner_run_msg('*Directory:* ' + settings['show_on_directory'])
            self.send_owner_run_msg('*Push2Talk:* ' + settings['push2talk'])
            self.send_owner_run_msg('*Greenroom:* ' + settings['greenroom'])

    def do_lastfm_chart(self, chart_items):
        """
        Makes a playlist from the currently most played tunes on last.fm
        :param chart_items: int the amount of tunes we want.
        """
        if self._is_client_mod:
            if chart_items is 0 or chart_items is None:
                self.send_bot_msg('Please specify the amount of tunes you want.')
            else:
                try:
                    _items = int(chart_items)
                except ValueError:
                    self.send_bot_msg('Only numbers allowed.')
                else:
                    if 0 < _items < 30:
                        self.send_bot_msg('Please wait while creating a playlist...')
                        last = lastfm.get_lastfm_chart(_items)
                        if last is not None:
                            if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                                self.media_manager.add_track_list(self.user.nick, last)
                                self.send_bot_msg('*Added:* ' + str(len(last)) + ' *tunes from last.fm chart.*')
                            else:
                                self.media_manager.add_track_list(self.user.nick, last)
                                self.send_bot_msg('*Added:* ' + str(len(last)) + ' *tunes from last.fm chart.*')
                                track = self.media_manager.get_next_track()
                                self.send_media_broadcast_start(track.type, track.id)
                                self.media_event_timer(track.time)
                        else:
                            self.send_bot_msg('Failed to retrieve a result from last.fm.')
                    else:
                        self.send_bot_msg('No more than 30 tunes.')

    def do_lastfm_random_tunes(self, max_tunes):
        """
        Creates a playlist from what other people are listening to on last.fm.
        :param max_tunes: int the max amount of tunes.
        """
        if self._is_client_mod:
            if max_tunes is 0 or max_tunes is None:
                self.send_bot_msg('Please specify the max amount of tunes you want.')
            else:
                try:
                    _items = int(max_tunes)
                except ValueError:
                    self.send_bot_msg('Only numbers allowed.')
                else:
                    if 0 < _items < 50:
                        self.send_bot_msg('Please wait while creating a playlist...')
                        last = lastfm.lastfm_listening_now(max_tunes)
                        if last is not None:
                            if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                                self.media_manager.add_track_list(self.user.nick, last)
                                self.send_bot_msg('*Added:* ' + str(len(last)) + ' *tunes from last.fm*')
                            else:
                                self.media_manager.add_track_list(self.user.nick, last)
                                self.send_bot_msg('*Added:* ' + str(len(last)) + ' *tunes from last.fm*')
                                track = self.media_manager.get_next_track()
                                self.send_media_broadcast_start(track.type, track.id)
                                self.media_event_timer(track.time)
                        else:
                            self.send_bot_msg('Failed to retrieve a result from last.fm.')
                    else:
                        self.send_bot_msg('No more than 50 tunes.')

    def search_lastfm_by_tag(self, search_str):
        """
        Searches last.fm for tunes matching the search term and creates a playlist from them.
        :param search_str: str the search term to search for.
        """
        if self._is_client_mod:
            if len(search_str) is 0:
                self.send_bot_msg('Missing search tag.')
            else:
                self.send_bot_msg('Please wait while creating playlist..')
                last = lastfm.search_lastfm_by_tag(search_str)
                if last is not None:
                    if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                        self.media_manager.add_track_list(self.user.nick, last)
                        self.send_bot_msg('*Added:* ' + str(len(last)) + ' *tunes from last.fm*')
                    else:
                        self.media_manager.add_track_list(self.user.nick, last)
                        self.send_bot_msg('*Added:* ' + str(len(last)) + ' *tunes from last.fm*')
                        track = self.media_manager.get_next_track()
                        self.send_media_broadcast_start(track.type, track.id)
                        self.media_event_timer(track.time)
                else:
                    self.send_bot_msg('Failed to retrieve a result from last.fm.')

    # == Mod And Bot Controller Command Methods. ==
    def do_close_broadcast(self, user_name):
        """
        Close a user broadcasting.
        :param user_name: str the username to close.
        """
        if self._is_client_mod:
            if len(user_name) is 0:
                self.send_bot_msg('Missing username.')
            else:
                user = self.find_user_info(user_name)
                if user is not None:
                    self.send_close_user_msg(user_name)
                else:
                    self.send_bot_msg('No user named: ' + user_name)

    def do_clear(self):
        """ Clears the chat box. """
        if self._is_client_mod:
            for x in range(0, 10):
                self.send_owner_run_msg(' ')
        else:
            clear = '133,133,133,133,133,133,133,133,133,133,133,133,133,133,133'
            self._send_command('privmsg', [clear, u'#262626,en'])

    def do_skip(self):
        """ Play the next item in the playlist. """
        if self.media_manager.is_last_track():
            self.send_bot_msg('*This is the last tune in the playlist.*')
        elif self.media_manager.is_last_track() is None:
            self.send_bot_msg('*No tunes to skip. The playlist is empty.*')
        else:
            self.cancel_media_event_timer()
            track = self.media_manager.get_next_track()
            self.send_media_broadcast_start(track.type, track.id)
            self.media_event_timer(track.time)
            
    def do_delete_playlist_item(self, to_delete):
        """
        Delete item(s) from the playlist by index.
        :param to_delete: str index(es) to delete.
        """
        if len(self.media_manager.track_list) is 0:
            self.send_bot_msg('The track list is empty.')
        elif len(to_delete) is 0:
            self.send_bot_msg('No indexes to delete provided.')
        else:
            indexes = None
            by_range = False

            try:
                if ':' in to_delete:
                    range_indexes = map(int, to_delete.split(':'))
                    temp_indexes = range(range_indexes[0], range_indexes[1] + 1)
                    if len(temp_indexes) > 1:
                        by_range = True
                else:
                    temp_indexes = map(int, to_delete.split(','))
            except ValueError:
                # add logging here?
                self.send_undercover_msg(self.user.nick, 'Wrong format.(ValueError)')
            else:
                indexes = []
                for i in temp_indexes:
                    if i < len(self.media_manager.track_list) and i not in indexes:
                        indexes.append(i)

            if indexes is not None and len(indexes) > 0:
                result = self.media_manager.delete_by_index(indexes, by_range)
                if result is not None:
                    if by_range:
                        self.send_bot_msg('*Deleted from index:* %s *to index:* %s' % (result['from'], result['to']))
                    elif result['deleted_indexes_len'] is 1:
                        self.send_bot_msg('*Deleted* %s' % result['track_title'])
                    else:
                        self.send_bot_msg('*Deleted tracks at index:* %s' % ', '.join(result['deleted_indexes']))
                else:
                    self.send_bot_msg('Nothing was deleted.')
                    
    def do_media_replay(self):
        """ Replays the last played media."""
        if self.media_manager.track() is not None:
            self.cancel_media_event_timer()
            self.media_manager.we_play(self.media_manager.track())
            self.send_media_broadcast_start(self.media_manager.track().type,
                                            self.media_manager.track().id)
            self.media_event_timer(self.media_manager.track().time)

    def do_play_media(self):
        """ Resumes a track in pause mode. """
        track = self.media_manager.track()
        if track is not None:
            if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                self.cancel_media_event_timer()
            if self.media_manager.is_paused:  #
                ntp = self.media_manager.mb_play(self.media_manager.elapsed_track_time())  #
                self.send_media_broadcast_play(track.type, self.media_manager.elapsed_track_time())
                self.media_event_timer(ntp)

    def do_media_pause(self):
        """ Pause the media playing. """
        track = self.media_manager.track()
        if track is not None:
            if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                self.cancel_media_event_timer()
            self.media_manager.mb_pause()
            self.send_media_broadcast_pause(track.type)

    def do_close_media(self):
        """ Closes the active media broadcast."""
        if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
            self.cancel_media_event_timer()
        self.media_manager.mb_close()
        self.send_media_broadcast_close(self.media_manager.track().type)

    def do_seek_media(self, time_point):
        """
        Seek on a media playing.
        :param time_point str the time point to skip to.
        """
        if ('h' in time_point) or ('m' in time_point) or ('s' in time_point):
            mls = string_utili.convert_to_millisecond(time_point)
            if mls is 0:
                self.console_write(pinylib.COLOR['bright_red'], 'invalid seek time.')
            else:
                track = self.media_manager.track()
                if track is not None:
                    if 0 < mls < track.time:
                        if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                            self.cancel_media_event_timer()
                        new_media_time = self.media_manager.mb_skip(mls)
                        if not self.media_manager.is_paused:
                            self.media_event_timer(new_media_time)
                        self.send_media_broadcast_skip(track.type, mls)

    def do_clear_playlist(self):
        """ Clear the playlist. """
        if len(self.media_manager.track_list) > 0:
            pl_length = str(len(self.media_manager.track_list))
            self.media_manager.clear_track_list()
            self.send_bot_msg('*Deleted* ' + pl_length + ' *items in the playlist.*')
        else:
            self.send_bot_msg('*The playlist is empty, nothing to delete.*')

    def do_nick(self, new_nick):
        """
        Set a new nick for the bot.
        :param new_nick: str the new nick.
        """
        if len(new_nick) is 0:
            self.client_nick = string_utili.create_random_string(5, 25)
            self.set_nick()
        else:
            if re.match('^[][{}a-zA-Z0-9_]{1,25}$', new_nick):
                self.client_nick = new_nick
                self.set_nick()

    def do_topic(self, topic):
        """
        Sets the room topic.
        :param topic: str the new topic.
        """
        if self._is_client_mod:
            if len(topic) is 0:
                self.send_topic_msg('')
                self.send_bot_msg('Topic was cleared.')
            else:
                self.send_topic_msg(topic)
                self.send_bot_msg('The room topic was set to: ' + topic)
        else:
            self.send_bot_msg('Command not enabled')

    def do_kick(self, user_name):
        """
        Kick a user out of the room.
        :param user_name: str the username to kick.
        """
        if self._is_client_mod:
            if len(user_name) is 0:
                self.send_bot_msg('Missing username.')
            elif user_name == self.client_nick:
                self.send_bot_msg('Action not allowed.')
            else:
                user = self.find_user_info(user_name)
                if user is None:
                    self.send_bot_msg('No user named: *' + user_name + '*')
                elif user.is_owner or user.is_super:
                    self.send_bot_msg('Not allowed.')
                else:
                    self.send_ban_msg(user_name, user.id)
                    self.send_forgive_msg(user.id)
        else:
            self.send_bot_msg('Command not enabled.')

    def do_ban(self, user_name):
        """
        Ban a user from the room.
        :param user_name: str the username to ban.
        """
        if self._is_client_mod:
            if len(user_name) is 0:
                self.send_bot_msg('Missing username.')
            elif user_name == self.client_nick:
                self.send_bot_msg('Action not allowed.')
            else:
                user = self.find_user_info(user_name)
                if user is None:
                    self.send_bot_msg('No user named: *' + user_name + '*')
                elif user.is_owner or user.is_super:
                    self.send_bot_msg('Not allowed.')
                else:
                    self.send_ban_msg(user_name, user.id)

    def do_bad_nick(self, bad_nick):
        """
        Adds a bad username to the bad nicks file.
        :param bad_nick: str the bad nick to write to file.
        """
        if self._is_client_mod:
            if len(bad_nick) is 0:
                self.send_bot_msg('Missing username.')
            else:
                badnicks = pinylib.fh.file_reader(self.config_path(), CONFIG['nick_bans'])
                if badnicks is None:
                    pinylib.fh.file_writer(self.config_path(), CONFIG['nick_bans'], bad_nick)
                else:
                    if bad_nick in badnicks:
                        self.send_bot_msg(bad_nick + ' is already in list.')
                    else:
                        pinylib.fh.file_writer(self.config_path(), CONFIG['nick_bans'], bad_nick)
                        self.send_bot_msg('*' + bad_nick + '* was added to file.')

    def do_remove_bad_nick(self, bad_nick):
        """
        Removes a bad nick from bad nicks file.
        :param bad_nick: str the bad nick to remove from file.
        """
        if self._is_client_mod:
            if len(bad_nick) is 0:
                self.send_bot_msg('Missing username')
            else:
                rem = pinylib.fh.remove_from_file(self.config_path(), CONFIG['nick_bans'], bad_nick)
                if rem:
                    self.send_bot_msg(bad_nick + ' was removed.')

    def do_bad_string(self, bad_string):
        """
        Adds a bad string to the bad strings file.
        :param bad_string: str the bad string to add to file.
        """
        if self._is_client_mod:
            if len(bad_string) is 0:
                self.send_bot_msg('Bad string can\'t be blank.')
            elif len(bad_string) < 3:
                self.send_bot_msg('Bad string to short: ' + str(len(bad_string)))
            else:
                bad_strings = pinylib.fh.file_reader(self.config_path(), CONFIG['ban_strings'])
                if bad_strings is None:
                    pinylib.fh.file_writer(self.config_path(), CONFIG['ban_strings'], bad_string)
                else:
                    if bad_string in bad_strings:
                        self.send_bot_msg(bad_string + ' is already in list.')
                    else:
                        pinylib.fh.file_writer(self.config_path(), CONFIG['ban_strings'], bad_string)
                        self.send_bot_msg('*' + bad_string + '* was added to file.')

    def do_remove_bad_string(self, bad_string):
        """
        Removes a bad string from the bad strings file.
        :param bad_string: str the bad string to remove from file.
        """
        if self._is_client_mod:
            if len(bad_string) is 0:
                self.send_bot_msg('Missing word string.')
            else:
                rem = pinylib.fh.remove_from_file(self.config_path(), CONFIG['ban_strings'], bad_string)
                if rem:
                    self.send_bot_msg(bad_string + ' was removed.')

    def do_bad_account(self, bad_account_name):
        """
        Adds a bad account name to the bad accounts file.
        :param bad_account_name: str the bad account name to add to file.
        """
        if self._is_client_mod:
            if len(bad_account_name) is 0:
                self.send_bot_msg('Account can\'t be blank.')
            elif len(bad_account_name) < 3:
                self.send_bot_msg('Account to short: ' + str(len(bad_account_name)))
            else:
                bad_accounts = pinylib.fh.file_reader(self.config_path(), CONFIG['account_bans'])
                if bad_accounts is None:
                    pinylib.fh.file_writer(self.config_path(), CONFIG['account_bans'], bad_account_name)
                else:
                    if bad_account_name in bad_accounts:
                        self.send_bot_msg(bad_account_name + ' is already in list.')
                    else:
                        pinylib.fh.file_writer(self.config_path(), CONFIG['account_bans'], bad_account_name)
                        self.send_bot_msg('*' + bad_account_name + '* was added to file.')

    def do_remove_bad_account(self, bad_account):
        """
        Removes a bad account from the bad accounts file.
        :param bad_account: str the badd account name to remove from file.
        """
        if self._is_client_mod:
            if len(bad_account) is 0:
                self.send_bot_msg('Missing account.')
            else:
                rem = pinylib.fh.remove_from_file(self.config_path(), CONFIG['account_bans'], bad_account)
                if rem:
                    self.send_bot_msg(bad_account + ' was removed.')

    def do_list_info(self, list_type):
        """
        Shows info of different lists/files.
        :param list_type: str the type of list to find info for.
        """
        if self._is_client_mod:
            if len(list_type) is 0:
                self.send_bot_msg('Missing list type.')
            else:
                if list_type.lower() == 'bn':
                    bad_nicks = pinylib.fh.file_reader(self.config_path(), CONFIG['nick_bans'])
                    if bad_nicks is None:
                        self.send_bot_msg('No items in this list.')
                    else:
                        self.send_bot_msg(str(len(bad_nicks)) + ' bad nicks in list.')

                elif list_type.lower() == 'bs':
                    bad_strings = pinylib.fh.file_reader(self.config_path(), CONFIG['ban_strings'])
                    if bad_strings is None:
                        self.send_bot_msg('No items in this list.')
                    else:
                        self.send_bot_msg(str(len(bad_strings)) + ' bad strings in list.')

                elif list_type.lower() == 'ba':
                    bad_accounts = pinylib.fh.file_reader(self.config_path(), CONFIG['account_bans'])
                    if bad_accounts is None:
                        self.send_bot_msg('No items in this list.')
                    else:
                        self.send_bot_msg(str(len(bad_accounts)) + ' bad accounts in list.')

                elif list_type.lower() == 'pl':
                    if len(self.media_manager.track_list) > 0:
                        tracks = self.media_manager.get_track_list()
                        if tracks is not None:
                            i = 0
                            for pos, track in tracks:
                                if i == 0:
                                    self.send_owner_run_msg('(%s) *Next track: %s* %s' %
                                                            (pos, track.title, self.format_time(track.time)))
                                else:
                                    self.send_owner_run_msg('(%s) *%s* %s' %
                                                            (pos, track.title, self.format_time(track.time)))
                                i += 1

                elif list_type.lower() == 'mods':
                    if self._is_client_owner and self.user.is_super:
                        if len(self.privacy_settings.room_moderators) is 0:
                            self.send_bot_msg('*There is currently no moderators for this room.*')
                        elif len(self.privacy_settings.room_moderators) is not 0:
                            mods = ', '.join(self.privacy_settings.room_moderators)
                            self.send_bot_msg('*Moderators:* ' + mods)

    def do_user_info(self, user_name):
        """
        Shows user object info for a given user name.
        :param user_name: str the user name of the user to show the info for.
        """
        if self._is_client_mod:
            if len(user_name) is 0:
                self.send_bot_msg('Missing username.')
            else:
                user = self.find_user_info(user_name)
                if user is None:
                    self.send_bot_msg('No user named: ' + user_name)
                else:
                    if user.account and user.tinychat_id is None:
                        user_info = pinylib.tinychat.tinychat_user_info(user.account)
                        if user_info is not None:
                            user.tinychat_id = user_info['tinychat_id']
                            user.last_login = user_info['last_active']
                    self.send_owner_run_msg('*ID:* ' + str(user.id))
                    self.send_owner_run_msg('*Bot Control:* ' + str(user.has_power))
                    self.send_owner_run_msg('*Owner:* ' + str(user.is_owner))
                    if user.tinychat_id is not None:
                        self.send_owner_run_msg('*Account:* ' + str(user.user_account))
                        self.send_owner_run_msg('*Tinychat ID:* ' + str(user.tinychat_id))
                        self.send_owner_run_msg('*Last login:* ' + str(user.last_login))
                    self.send_owner_run_msg('*Last message:* ' + str(user.last_msg))

    def do_youtube_search(self, search_str):
        """
        Searches youtube for a given search term, and adds the results to a list.
        :param search_str: str the search term to search for.
        """
        if self._is_client_mod:
            if len(search_str) is 0:
                self.send_bot_msg('Missing search term.')
            else:
                self.search_list = youtube.youtube_search_list(search_str, results=5)
                if len(self.search_list) is not 0:
                    for i in range(0, len(self.search_list)):
                        v_time = self.format_time(self.search_list[i]['video_time'])
                        v_title = self.search_list[i]['video_title']
                        self.send_owner_run_msg('(%s) *%s* %s' % (i, v_title, v_time))
                else:
                    self.send_bot_msg('Could not find: ' + search_str)

    def do_play_youtube_search(self, int_choice):
        """
        Plays a youtube from the search list.
        :param int_choice: int the index in the search list to play.
        """
        if self._is_client_mod:
            if len(self.search_list) > 0:
                try:
                    index_choice = int(int_choice)
                    if 0 <= index_choice <= 4:
                        if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                            track = self.media_manager.add_track(self.user.nick, self.search_list[index_choice])
                            self.send_bot_msg('(' + str(self.media_manager.last_track_index()) + ') *' +
                                              track.title + '* ' + track.time)
                        else:
                            track = self.media_manager.mb_start(self.user.nick,
                                                                self.search_list[index_choice], mod_play=False)
                            self.send_media_broadcast_start(track.type, track.id)
                            self.media_event_timer(track.time)
                    else:
                        self.send_bot_msg('Please make a choice between 0-4')
                except ValueError:
                    self.send_bot_msg('Only numbers allowed.')

    # == Public Command Methods. ==
    def do_full_screen(self, room_name):
        """ Post a full screen link.
        :param room_name str the room name you want a full screen link for.
        """
        if not room_name:
            self.send_undercover_msg(self.user.nick,
                                     'http://tinychat.com/embed/Tinychat-11.1-1.0.0.' +
                                     pinylib.SETTINGS['swf_version'] + '.swf?'
                                     'target=client&key=tinychat&room=' + self._roomname)
        else:
            self.send_undercover_msg(self.user.nick,
                                     'http://tinychat.com/embed/Tinychat-11.1-1.0.0.' +
                                     pinylib.SETTINGS['swf_version'] + '.swf?'
                                     'target=client&key=tinychat&room=' + room_name)

    def do_who_plays(self):
        """ shows who is playing the track. """
        if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
            track = self.media_manager.track()
            ago = self.format_time(int(pinylib.time.time() - track.rq_time) * 1000)
            self.send_undercover_msg(self.user.nick, '*' + track.nick + '* requested this track: ' + ago + ' ago.')
        else:
            self.send_undercover_msg(self.user.nick, 'No track playing.')

    def do_version(self):
        """ Show version info. """
        self.send_undercover_msg(self.user.nick, '*tinybot version:* %s *pinylib version:* %s' %
                                 (__version__, pinylib.about.__version__))

    def do_help(self):
        """ Posts a link to github readme/wiki or other page about the bot commands. """
        self.send_undercover_msg(self.user.nick, '*Help:* https://github.com/nortxort/pinylib/wiki/commands')

    def do_uptime(self):
        """ Shows the bots uptime. """
        self.send_bot_msg('*Uptime:* ' + self.format_time(self.get_runtime()) +
                          ' *Reconnect Delay:* ' + self.format_time(self._reconnect_delay * 1000))

    def do_pmme(self):
        """ Opens a PM session with the bot. """
        self.send_private_msg('How can i help you *' + self.user.nick + '*?', self.user.nick)

    #  == Media Related Command Methods. ==
    def do_playlist_status(self):
        """ Shows info about the playlist. """
        if self._is_client_mod:
            if len(self.media_manager.track_list) is 0:
                self.send_bot_msg('*The playlist is empty.*')
            else:
                inquee = self.media_manager.queue()
                if inquee is not None:
                    self.send_bot_msg(str(inquee[0]) + ' *items in the playlist.* ' +
                                      str(inquee[1]) + ' *Still in queue.*')
        else:
            self.send_bot_msg('Not enabled right now..')

    def do_next_tune_in_playlist(self):
        """ Shows next item in the playlist. """
        if self._is_client_mod:
            if self.media_manager.is_last_track():
                self.send_bot_msg('*This is the last track in the playlist.*')
            elif self.media_manager.is_last_track() is None:
                self.send_bot_msg('*No tracks in the playlist.*')
            else:
                pos, next_track = self.media_manager.next_track_info()
                if next_track is not None:
                    self.send_bot_msg('(' + str(pos) + ') *' + next_track.title + '* ' +
                                      self.format_time(next_track.time))
        else:
            self.send_bot_msg('Not enabled right now..')

    def do_now_playing(self):
        """ Shows the currently playing media title. """
        if self._is_client_mod:
            if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                track = self.media_manager.track()
                if len(self.media_manager.track_list) > 0:
                    self.send_undercover_msg(self.user.nick, '(' + str(self.media_manager.current_track_index()) +
                                             ') *' + track.title + '* ' + self.format_time(track.time))
                else:
                    self.send_undercover_msg(self.user.nick, '*' + track.title + '* ' +
                                             self.format_time(track.time))
            else:
                self.send_undercover_msg(self.user.nick, '*No track playing.*')

    def do_play_youtube(self, search_str):
        """
        Plays a youtube video matching the search term.
        :param search_str: str the search term.
        """
        log.info('User: %s:%s is searching youtube: %s' % (self.user.nick, self.user.id, search_str))
        if self._is_client_mod:
            if len(search_str) is 0:
                self.send_bot_msg('Please specify youtube title, id or link.')
            else:
                _youtube = youtube.youtube_search(search_str)
                if _youtube is None:
                    log.warning('Youtube request returned: %s' % _youtube)
                    self.send_bot_msg('Could not find video: ' + search_str)
                else:
                    log.info('Youtube found: %s' % _youtube)
                    if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                        track = self.media_manager.add_track(self.user.nick, _youtube)
                        self.send_bot_msg('(' + str(self.media_manager.last_track_index()) + ') *' +
                                          track.title + '* ' + self.format_time(track.time))
                    else:
                        track = self.media_manager.mb_start(self.user.nick, _youtube, mod_play=False)
                        self.send_media_broadcast_start(track.type, track.id)
                        self.media_event_timer(track.time)
        else:
            self.send_bot_msg('Not enabled right now..')

    def do_play_private_youtube(self, search_str):
        """
        Plays a youtube matching the search term privately.
        NOTE: The video will only be visible for the message sender.
        :param search_str: str the search term.
        """
        if self._is_client_mod:
            if len(search_str) is 0:
                self.send_undercover_msg(self.user.nick, 'Please specify youtube title, id or link.')
            else:
                _youtube = youtube.youtube_search(search_str)
                if _youtube is None:
                    self.send_undercover_msg(self.user.nick, 'Could not find video: ' + search_str)
                else:
                    self.send_media_broadcast_start(_youtube['type'], _youtube['video_id'],
                                                    private_nick=self.user.nick)
        else:
            self.send_bot_msg('Not enabled right now..')

    def do_play_soundcloud(self, search_str):
        """
        Plays a soundcloud matching the search term.
        :param search_str: str the search term.
        """
        if self._is_client_mod:
            if len(search_str) is 0:
                self.send_bot_msg('Please specify soundcloud title or id.')
            else:
                _soundcloud = soundcloud.soundcloud_search(search_str)
                if _soundcloud is None:
                    self.send_bot_msg('Could not find soundcloud: ' + search_str)
                else:
                    if self.media_timer_thread is not None and self.media_timer_thread.is_alive():
                        track = self.media_manager.add_track(self.user.nick, _soundcloud)
                        self.send_bot_msg('(' + str(self.media_manager.last_track_index()) + ') *' + track.title +
                                          '* ' + self.format_time(track.time))
                    else:
                        track = self.media_manager.mb_start(self.user.nick, _soundcloud, mod_play=False)
                        self.send_media_broadcast_start(track.type, track.id)
                        self.media_event_timer(track.time)
        else:
            self.send_bot_msg('Not enabled right now..')

    def do_play_private_soundcloud(self, search_str):
        """
        Plays a soundcloud matching the search term privately.
        NOTE: The video will only be visible for the message sender.
        :param search_str: str the search term.
        """
        if self._is_client_mod:
            if len(search_str) is 0:
                self.send_undercover_msg(self.user.nick, 'Please specify soundcloud title or id.')
            else:
                _soundcloud = soundcloud.soundcloud_search(search_str)
                if _soundcloud is None:
                    self.send_undercover_msg(self.user.nick, 'Could not find video: ' + search_str)
                else:
                    self.send_media_broadcast_start(_soundcloud['type'], _soundcloud['video_id'],
                                                    private_nick=self.user.nick)
        else:
            self.send_bot_msg('Not enabled right now..')

    def do_cam_approve(self):  # NEW
        """ Send a cam approve message to a user. """
        if self._is_client_mod:
            if self._b_password is None:
                conf = pinylib.tinychat.get_roomconfig_xml(self._roomname, self.room_pass, proxy=self._proxy)
                self._b_password = conf['bpassword']
                self._greenroom = conf['greenroom']
            if self._greenroom:
                self.send_cam_approve_msg(self.user.id, self.user.nick)

    # == Tinychat API Command Methods. ==
    def do_spy(self, roomname):
        """
        Shows info for a given room.
        :param roomname: str the room name to find info for.
        """
        if self._is_client_mod:
            if len(roomname) is 0:
                self.send_undercover_msg(self.user.nick, 'Missing room name.')
            else:
                spy_info = pinylib.tinychat.spy_info(roomname)
                if spy_info is None:
                    self.send_undercover_msg(self.user.nick, 'The room is empty.')
                elif spy_info == 'PW':
                    self.send_undercover_msg(self.user.nick, 'The room is password protected.')
                else:
                    self.send_undercover_msg(self.user.nick,
                                             '*mods:* ' + spy_info['mod_count'] +
                                             ' *Broadcasters:* ' + spy_info['broadcaster_count'] +
                                             ' *Users:* ' + spy_info['total_count'])
                    if self.user.is_owner or self.user.is_mod or self.user.has_power:
                        users = ', '.join(spy_info['users'])
                        self.send_undercover_msg(self.user.nick, '*' + users + '*')

    def do_account_spy(self, account):
        """
        Shows info about a tinychat account.
        :param account: str tinychat account.
        """
        if self._is_client_mod:
            if len(account) is 0:
                self.send_undercover_msg(self.user.nick, 'Missing username to search for.')
            else:
                tc_usr = pinylib.tinychat.tinychat_user_info(account)
                if tc_usr is None:
                    self.send_undercover_msg(self.user.nick, 'Could not find tinychat info for: ' + account)
                else:
                    self.send_undercover_msg(self.user.nick, 'ID: ' + tc_usr['tinychat_id'] +
                                             ', Last login: ' + tc_usr['last_active'])

    # == Other API Command Methods. ==
    def do_search_urban_dictionary(self, search_str):
        """
        Shows urbandictionary definition of search string.
        :param search_str: str the search string to look up a definition for.
        """
        if self._is_client_mod:
            if len(search_str) is 0:
                self.send_bot_msg('Please specify something to look up.')
            else:
                urban = other.urbandictionary_search(search_str)
                if urban is None:
                    self.send_bot_msg('Could not find a definition for: ' + search_str)
                else:
                    if len(urban) > 70:
                        chunks = string_utili.chunk_string(urban, 70)
                        for i in range(0, 2):
                            self.send_bot_msg(chunks[i])
                    else:
                        self.send_bot_msg(urban)

    def do_weather_search(self, search_str):
        """
        Shows weather info for a given search string.
        :param search_str: str the search string to find weather data for.
        """
        if len(search_str) is 0:
            self.send_bot_msg('Please specify a city to search for.')
        else:
            weather = other.weather_search(search_str)
            if weather is None:
                self.send_bot_msg('Could not find weather data for: ' + search_str)
            else:
                self.send_bot_msg(weather)

    def do_whois_ip(self, ip_str):
        """
        Shows whois info for a given ip address.
        :param ip_str: str the ip address to find info for.
        """
        if len(ip_str) is 0:
            self.send_bot_msg('Please provide an IP address.')
        else:
            whois = other.whois(ip_str)
            if whois is None:
                self.send_bot_msg('No info found for: ' + ip_str)
            else:
                self.send_bot_msg(whois)

    def do_md5_hash_cracker(self, hash_str):  # NEW
        if len(hash_str) is 0:
            self.send_bot_msg('Missing md5 hash.')
        elif len(hash_str) is 32:
            result = other.hash_cracker(hash_str)
            if result is not None:
                if result['status']:
                    self.send_bot_msg(hash_str + ':*' + result['result'] + '*')
                elif not result['status']:
                    self.send_bot_msg(result['message'])
        else:
            self.send_bot_msg('A md5 hash is exactly 32 characters long.')

    # == Just For Fun Command Methods. ==
    def do_chuck_noris(self):
        """ Shows a chuck norris joke/quote. """
        chuck = other.chuck_norris()
        if chuck is not None:
            self.send_bot_msg(chuck)

    def do_8ball(self, question):
        """
        Shows magic eight ball answer to a yes/no question.
        :param question: str the yes/no question.
        """
        if len(question) is 0:
            self.send_bot_msg('Question.')
        else:
            self.send_bot_msg('*8Ball* ' + locals.eight_ball())

    def private_message_handler(self, msg_sender, private_msg):
        """
        Custom private message commands.
        :param msg_sender: str the user sending the private message.
        :param private_msg: str the private message.
        """

        # Is this a custom PM command?
        if private_msg.startswith(CONFIG['prefix']):
            # Split the message in to parts.
            pm_parts = private_msg.split(' ')
            # pm_parts[0] is the command.
            pm_cmd = pm_parts[0].lower().strip()
            # The rest is a command argument.
            pm_arg = ' '.join(pm_parts[1:]).strip()

            # Super mod commands.
            if pm_cmd == CONFIG['prefix'] + 'rp':
                threading.Thread(target=self.do_set_room_pass, args=(pm_arg,)).start()

            elif pm_cmd == CONFIG['prefix'] + 'bp':
                threading.Thread(target=self.do_set_broadcast_pass, args=(pm_arg,)).start()

            # Owner and super mod commands.
            if pm_cmd == CONFIG['prefix'] + 'key':
                self.do_key(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'clrbn':
                self.do_clear_bad_nicks()

            elif pm_cmd == CONFIG['prefix'] + 'clrbs':
                self.do_clear_bad_strings()

            elif pm_cmd == CONFIG['prefix'] + 'clrba':
                self.do_clear_bad_accounts()

            # Mod and bot controller commands.
            elif pm_cmd == CONFIG['prefix'] + 'op':
                self.do_op_user(pm_parts)

            elif pm_cmd == CONFIG['prefix'] + 'deop':
                self.do_deop_user(pm_parts)

            elif pm_cmd == CONFIG['prefix'] + 'up':
                self.do_cam_up(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'down':
                self.do_cam_down(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'nocam':
                self.do_nocam(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'noguest':
                self.do_no_guest(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'guestnick':
                self.do_no_guest_nicks(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'newusers':
                self.do_newusers(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'pub':  # NEW
                self.do_public_cmds(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'skip':
                self.do_skip()

            # Public commands.
            elif pm_cmd == CONFIG['prefix'] + 'sudo':
                self.do_super_user(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'opme':
                self.do_opme(pm_arg)

            elif pm_cmd == CONFIG['prefix'] + 'pm':
                self.do_pm_bridge(pm_parts)

        # Print to console.
        self.console_write(pinylib.COLOR['white'], 'Private message from ' + msg_sender + ':' + str(private_msg)
                           .replace(self.key, '***KEY***')
                           .replace(CONFIG['super_key'], '***SUPER KEY***'))

    # == Super Mod Command Methods. ==
    def do_set_room_pass(self, password):
        """
        Set a room password for the room.
        :param password: str the room password
        """
        if self._is_client_owner:
            if self.user.is_super:
                if not password:
                    self.privacy_settings.set_room_password()
                    self.send_bot_msg('*The room password was removed.*')
                    pinylib.time.sleep(1)
                    self.send_private_msg('The room password was removed.', self.user.nick)
                elif len(password) > 1:
                    self.privacy_settings.set_room_password(password)
                    self.send_private_msg('*The room password is now:* ' + password, self.user.nick)
                    pinylib.time.sleep(1)
                    self.send_bot_msg('*The room is now password protected.*')

    def do_set_broadcast_pass(self, password):
        """
        Set a broadcast password for the room.
        :param password: str the password
        """
        if self._is_client_owner:
            if self.user.is_super:
                if not password:
                    self.privacy_settings.set_broadcast_password()
                    self.send_bot_msg('*The broadcast password was removed.*')
                    pinylib.time.sleep(1)
                    self.send_private_msg('The broadcast password was removed.', self.user.nick)
                elif len(password) > 1:
                    self.privacy_settings.set_broadcast_password(password)
                    self.send_private_msg('*The broadcast password is now:* ' + password, self.user.nick)
                    pinylib.time.sleep(1)
                    self.send_bot_msg('*Broadcast password is enabled.*')

    # == Owner And Super Mod Command Methods. ==
    def do_key(self, new_key):
        """
        Shows or sets a new secret key.
        :param new_key: str the new secret key.
        """
        if self.user.is_owner or self.user.is_super:
            if len(new_key) is 0:
                self.send_private_msg('The current key is: *' + self.key + '*', self.user.nick)
            elif len(new_key) < 6:
                self.send_private_msg('Key must be at least 6 characters long: ' + str(len(self.key)),
                                      self.user.nick)
            elif len(new_key) >= 6:
                self.key = new_key
                self.send_private_msg('The key was changed to: *' + self.key + '*', self.user.nick)

    def do_clear_bad_nicks(self):
        """ Clears the bad nicks file. """
        if self.user.is_owner or self.user.is_super:
            pinylib.fh.delete_file_content(self.config_path(), CONFIG['badnicks'])

    def do_clear_bad_strings(self):
        """ Clears the bad strings file. """
        if self.user.is_owner or self.user.is_super:
            pinylib.fh.delete_file_content(self.config_path(), CONFIG['badstrings'])

    def do_clear_bad_accounts(self):
        """ Clears the bad accounts file. """
        if self.user.is_owner or self.user.is_super:
            pinylib.fh.delete_file_content(self.config_path(), CONFIG['badaccounts'])

    # == Mod And Bot Controller Command Methods. ==
    def do_op_user(self, msg_parts):
        """
        Lets the room owner, a mod or a bot controller make another user a bot controller.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param msg_parts: list the pm message as a list.
        """
        if self.user.is_owner or self.user.is_super:
            if len(msg_parts) == 1:
                self.send_private_msg('Missing username.', self.user.nick)
            elif len(msg_parts) == 2:
                user = self.find_user_info(msg_parts[1])
                if user is not None:
                    user.has_power = True
                    self.send_private_msg(user.nick + ' is now a bot controller.', self.user.nick)
                    # self.send_private_msg('You are now a bot controller.', user.nick)
                else:
                    self.send_private_msg('No user named: ' + msg_parts[1], self.user.nick)

        elif self.user.is_mod or self.user.has_power:
            if len(msg_parts) == 1:
                self.send_private_msg('Missing username.', self.user.nick)
            elif len(msg_parts) == 2:
                self.send_private_msg('Missing key.', self.user.nick)
            elif len(msg_parts) == 3:
                if msg_parts[2] == self.key:
                    user = self.find_user_info(msg_parts[1])
                    if user is not None:
                        user.has_power = True
                        self.send_private_msg(user.nick + ' is now a bot controller.', self.user.nick)
                    else:
                        self.send_private_msg('No user named: ' + msg_parts[1], self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)

    def do_deop_user(self, msg_parts):
        """
        Lets the room owner, a mod or a bot controller remove a user from being a bot controller.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param msg_parts: list the pm message as a list
        """
        if self.user.is_owner or self.user.is_super:
            if len(msg_parts) == 1:
                self.send_private_msg('Missing username.', self.user.nick)
            elif len(msg_parts) == 2:
                user = self.find_user_info(msg_parts[1])
                if user is not None:
                    user.has_power = False
                    self.send_private_msg(user.nick + ' is not a bot controller anymore.', self.user.nick)
                else:
                    self.send_private_msg('No user named: ' + msg_parts[1], self.user.nick)

        elif self.user.is_mod or self.user.has_power:
            if len(msg_parts) == 1:
                self.send_private_msg('Missing username.', self.user.nick)
            elif len(msg_parts) == 2:
                self.send_private_msg('Missing key.', self.user.nick)
            elif len(msg_parts) == 3:
                if msg_parts[2] == self.key:
                    user = self.find_user_info(msg_parts[1])
                    if user is not None:
                        user.has_power = False
                        self.send_private_msg(user.nick + ' is not a bot controller anymore.', self.user.nick)
                    else:
                        self.send_private_msg('No user named: ' + msg_parts[1], self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)

    def do_cam_up(self, key):
        """
        Makes the bot camup.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param key str the key needed for moderators/bot controllers.
        """
        if self.user.is_owner or self.user.is_super:
            self.send_bauth_msg()
            self.send_create_stream()
            self.send_publish()
        elif self.user.is_mod or self.user.has_power:
            if len(key) is 0:
                self.send_private_msg('Missing key.', self.user.nick)
            elif key == self.key:
                self.send_bauth_msg()
                self.send_create_stream()
                self.send_publish()
            else:
                self.send_private_msg('Wrong key.', self.user.nick)

    def do_cam_down(self, key):
        """
        Makes the bot cam down.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param key: str the key needed for moderators/bot controllers.
        """
        if self.user.is_owner or self.user.is_super:
            self.send_close_stream()
        elif self.user.is_mod or self.user.has_power:
            if len(key) is 0:
                self.send_private_msg('Missing key.', self.user.nick)
            elif key == self.key:
                self.send_close_stream()
            else:
                self.send_private_msg('Wrong key.', self.user.nick)

    def do_nocam(self, key):
        """
        Toggles if broadcasting is allowed or not.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param key: str secret key.
        """
        if self.is_broadcasting_allowed or self.user.is_super:
            if self.user.is_owner:
                self.is_broadcasting_allowed = False
                self.send_private_msg('*Broadcasting is NOT allowed.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_broadcasting_allowed = False
                    self.send_private_msg('*Broadcasting is NOT allowed.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)
        else:
            if self.user.is_owner or self.user.is_super:
                self.is_broadcasting_allowed = True
                self.send_private_msg('*Broadcasting is allowed.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_broadcasting_allowed = True
                    self.send_private_msg('*Broadcasting is allowed.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)

    def do_no_guest(self, key):
        """
        Toggles if guests are allowed to join the room or not.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param key: str secret key.
        """
        if self.is_guest_entry_allowed:
            if self.user.is_owner or self.user.is_super:
                self.is_guest_entry_allowed = False
                self.send_private_msg('*Guests are NOT allowed to join the room.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_guest_entry_allowed = False
                    self.send_private_msg('*Guests are NOT allowed to join.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)
        else:
            if self.user.is_owner or self.user.is_super:
                self.is_guest_entry_allowed = True
                self.send_private_msg('*Guests ARE allowed to join the room.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_guest_entry_allowed = True
                    self.send_private_msg('*Guests ARE allowed to join.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)

    def do_no_guest_nicks(self, key):
        """
        Toggles if guest nicks are allowed or not.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param key: str secret key.
        """
        if self.is_guest_nicks_allowed:
            if self.user.is_owner or self.user.is_super:
                self.is_guest_nicks_allowed = False
                self.send_private_msg('*Guests nicks are NOT allowed.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_guest_nicks_allowed = False
                    self.send_private_msg('*Guests nicks are NOT allowed.*', self.user.nick)
                else:
                    self.send_private_msg('wrong key.', self.user.nick)
        else:
            if self.user.is_owner or self.user.is_super:
                self.is_guest_nicks_allowed = True
                self.send_private_msg('*Guests nicks ARE allowed.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_guest_nicks_allowed = True
                    self.send_private_msg('*Guests nicks ARE allowed.*', self.user.nick)
                else:
                    self.send_private_msg('wrong key.', self.user.nick)

    def do_newusers(self, key):
        """
        Toggles if newusers are allowed to join the room or not.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param key: str secret key.
        """
        if self.is_newusers_allowed:
            if self.user.is_owner or self.user.is_super:
                self.is_newusers_allowed = False
                self.send_private_msg('*Newusers are NOT allowed to join the room.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_newusers_allowed = False
                    self.send_private_msg('*Newusers are NOT allowed to join the room.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)
        else:
            if self.user.is_owner or self.user.is_super:
                self.is_newusers_allowed = True
                self.send_private_msg('*Newusers ARE allowed to join the room.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_newusers_allowed = True
                    self.send_private_msg('*Newusers ARE allowed to join the room.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)

    def do_public_cmds(self, key):  # NEW
        """
        Toggles if public commands are public or not.
        NOTE: Mods or bot controllers will have to provide a key, owner and super does not.
        :param key: str secret key.
        """
        if self.is_cmds_public:
            if self.user.is_owner or self.user.is_super:
                self.is_cmds_public = False
                self.send_private_msg('*Public commands are disabled.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_cmds_public = False
                    self.send_private_msg('*Public commands are disabled.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)
        else:
            if self.user.is_owner or self.user.is_super:
                self.is_cmds_public = True
                self.send_private_msg('*Public commands are enabled.*', self.user.nick)
            elif self.user.is_mod or self.user.has_power:
                if len(key) is 0:
                    self.send_private_msg('missing key.', self.user.nick)
                elif key == self.key:
                    self.is_cmds_public = True
                    self.send_private_msg('*Public commands are enabled.*', self.user.nick)
                else:
                    self.send_private_msg('Wrong key.', self.user.nick)

    # == Public PM Command Methods. ==
    def do_super_user(self, super_key):
        """
        Makes a user super mod, the highest level of mod.
        It is only possible to be a super mod if the client is owner.
        :param super_key: str the super key
        """
        if self._is_client_owner:
            if len(super_key) is 0:
                self.send_private_msg('Missing super key.', self.user.nick)
            elif super_key == CONFIG['super_key']:
                self.user.is_super = True
                self.send_private_msg('*You are now a super mod.*', self.user.nick)
            else:
                self.send_private_msg('Wrong super key.', self.user.nick)
        else:
            self.send_private_msg('Client is owner: *' + str(self._is_client_owner) + '*',
                                  self.user.nick)

    def do_opme(self, key):
        """
        Makes a user a bot controller if user provides the right key.
        :param key: str the secret key.
        """
        if len(key) is 0:
            self.send_private_msg('Missing key.', self.user.nick)
        elif key == self.key:
            self.user.has_power = True
            self.send_private_msg('You are now a bot controller.', self.user.nick)
        else:
            self.send_private_msg('Wrong key.', self.user.nick)

    def do_pm_bridge(self, pm_parts):
        """
        Makes the bot work as a PM message bridge between 2 user who are not signed in.
        :param pm_parts: list the pm message as a list.
        """
        if len(pm_parts) == 1:
            self.send_private_msg('Missing username.', self.user.nick)
        elif len(pm_parts) == 2:
            self.send_private_msg('The command is: ' + CONFIG['prefix'] + 'pm username message', self.user.nick)
        elif len(pm_parts) >= 3:
            pm_to = pm_parts[1]
            msg = ' '.join(pm_parts[2:])
            is_user = self.find_user_info(pm_to)
            if is_user is not None:
                if is_user.id == self._client_id:
                    self.send_private_msg('Action not allowed.', self.user.nick)
                else:
                    self.send_private_msg('*<' + self.user.nick + '>* ' + msg, pm_to)
            else:
                self.send_private_msg('No user named: ' + pm_to, self.user.nick)

    # Timed auto functions.
    def media_event_handler(self):
        """ This method gets called whenever a media is done playing. """
        if len(self.media_manager.track_list) > 0:
            if self.media_manager.is_last_track():
                if self.is_connected:
                    self.send_bot_msg('*Resetting playlist.*')
                self.media_manager.clear_track_list()
            else:
                track = self.media_manager.get_next_track()
                if track is not None and self.is_connected:
                    self.send_media_broadcast_start(track.type, track.id)
                self.media_event_timer(track.time)

    def media_event_timer(self, video_time):
        """
        Start a media event timer.
        :param video_time: int the time in milliseconds.
        """
        video_time_in_seconds = video_time / 1000
        self.media_timer_thread = threading.Timer(video_time_in_seconds, self.media_event_handler)
        self.media_timer_thread.start()

    def random_msg(self):
        """
        Pick a random message from a list of messages.
        :return: str random message.
        """
        upnext = 'Use *' + CONFIG['prefix'] + 'yt* youtube title, link or id to add or play youtube.'
        plstat = 'Use *' + CONFIG['prefix'] + 'sc* soundcloud title or id to add or play soundcloud.'
        if self.media_manager.is_last_track() is not None and not self.media_manager.is_last_track():
            pos, next_track = self.media_manager.next_track_info()
            if next_track is not None:
                next_video_time = self.format_time(next_track.time)
                upnext = '*Next is:* (' + str(pos) + ') *' + next_track.title + '* ' + next_video_time
            queue = self.media_manager.queue()
            plstat = str(queue[0]) + ' *items in the playlist.* ' + str(queue[1]) + ' *Still in queue.*'

        messages = ['Reporting for duty..', 'Hello, is anyone here?', 'Awaiting command..', 'Observing behavior..',
                    upnext, plstat, '*Uptime:* ' + self.format_time(self.get_runtime()),
                    'Type: *' + CONFIG['prefix'] + 'help* for a list of commands']

        return random.choice(messages)

    def auto_msg_handler(self):
        """ The event handler for auto_msg_timer. """
        if self.is_connected:
            if CONFIG['auto_message_enabled']:
                self.send_bot_msg(self.random_msg(), use_chat_msg=True)
        self.start_auto_msg_timer()

    def start_auto_msg_timer(self):
        """
        In rooms with less activity, it can be useful to have the client send auto messages to keep the client alive.
        This method can be disabled by setting CONFIG['auto_message_enabled'] to False.
        The interval for when a message should be sent, is set with CONFIG['auto_message_interval']
        """
        threading.Timer(CONFIG['auto_message_interval'], self.auto_msg_handler).start()

    # Helper Methods.
    def get_privacy_settings(self):
        """ Parse the privacy settings page. """
        log.info('Parsing %s\'s privacy page. Proxy %s' % (self.account, self._proxy))
        self.privacy_settings = privacy_settings.TinychatPrivacyPage(self._proxy)
        self.privacy_settings.parse_privacy_settings()

    def config_path(self):
        """ Returns the path to the rooms configuration directory. """
        path = pinylib.SETTINGS['config_path'] + self._roomname + '/'
        return path

    def cancel_media_event_timer(self):
        """
        Cancel the media event timer if it is running.
        :return: True if canceled, else False
        """
        if self.media_timer_thread is not None:
            if self.media_timer_thread.is_alive():
                self.media_timer_thread.cancel()
                self.media_timer_thread = None
                return True
            return False
        return False

    @staticmethod
    def format_time(milliseconds):
        """
        Converts milliseconds or seconds to (day(s)) hours minutes seconds.
        :param milliseconds: int the milliseconds or seconds to convert.
        :return: str in the format (days) hh:mm:ss
        """
        m, s = divmod(milliseconds/1000, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        if d == 0 and h == 0:
            human_time = '%02d:%02d' % (m, s)
        elif d == 0:
            human_time = '%d:%02d:%02d' % (h, m, s)
        else:
            human_time = '%d Day(s) %d:%02d:%02d' % (d, h, m, s)
        return human_time

    def check_msg_for_bad_string(self, msg):
        """
        Checks the chat message for bad string.
        :param msg: str the chat message.
        """
        msg_words = msg.split(' ')
        bad_strings = pinylib.fh.file_reader(self.config_path(), CONFIG['ban_strings'])
        if bad_strings is not None:
            for word in msg_words:
                if word in bad_strings:
                    self.send_ban_msg(self.user.nick, self.user.id)
                    # remove next line to ban.
                    self.send_forgive_msg(self.user.id)
                    self.send_bot_msg('*Auto-banned*: (bad string in message)')


def main():
    room_name = raw_input('Enter room name: ')
    nickname = raw_input('Enter nick name: (optional) ')
    room_password = raw_input('Enter room password: (optional) ')
    login_account = raw_input('Login account: (optional)')
    login_password = raw_input('Login password: (optional)')

    client = TinychatBot(room_name, nick=nickname, account=login_account,
                         password=login_password, room_pass=room_password)

    t = threading.Thread(target=client.prepare_connect)
    t.daemon = True
    t.start()

    while not client.is_connected:
        pinylib.time.sleep(1)
    while client.is_connected:
        chat_msg = raw_input()
        if chat_msg.startswith('/'):
            cmd_parts = chat_msg.split(' ')
            cmd = cmd_parts[0].lower()
            if cmd == '/q':
                client.disconnect()
        else:
            client.send_bot_msg(chat_msg)

if __name__ == '__main__':
    if CONFIG['debug_to_file']:
        formater = '%(asctime)s : %(levelname)s : %(filename)s : %(lineno)d : %(funcName)s() : %(name)s : %(message)s'
        logging.basicConfig(filename=CONFIG['debug_file_name'], level=logging.DEBUG, format=formater)
        log.info('Starting bot_example.py version: %s, pinylib version: %s' %
                 (__version__, pinylib.about.__version__))
    else:
        log.addHandler(logging.NullHandler())
    main()
