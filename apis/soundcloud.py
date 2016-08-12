""" Contains functions to fetch info from api.soundcloud.com """
from utilities import web

# Soundcloud API key.
SOUNDCLOUD_API_KEY = '4ce43a6430270a1eea977ff8357a25a3'


def soundcloud_search(search):
    """
    Searches soundcloud's API for a given search term.

    :param search: str the search term to search for.
    :return: dict{'type=soundcloud', 'video_id', 'video_time', 'video_title'} or None on no match or error.
    """
    if search:
        search_url = 'http://api.soundcloud.com/tracks/?' \
                     'filter=streamable&q=%s&limit=25&client_id=%s' % (search, SOUNDCLOUD_API_KEY)

        response = web.http_get(search_url, json=True)
        if response['json'] is not None:
            try:
                track_id = response['json'][0]['id']
                track_time = response['json'][0]['duration']
                track_title = response['json'][0]['title'].encode('ascii', 'ignore')
                return {
                    'type': 'soundCloud',
                    'video_id': track_id,
                    'video_time': track_time,
                    'video_title': track_title
                }
            except (IndexError, KeyError):
                return None
        return None


def soundcloud_track_info(track_id):
    if track_id:
        info_url = 'http://api.soundcloud.com/tracks/%s?client_id=%s' % (track_id, SOUNDCLOUD_API_KEY)
        response = web.http_get(info_url, json=True)

        if response['json'] is not None:
            try:
                user_id = response['json'][0]['user_id']
                track_time = response['json'][0]['duration']
                track_title = response['json'][0]['title'].encode('ascii', 'ignore')
                return {
                    'type': 'soundCloud',
                    'video_id': track_id,
                    'video_time': track_time,
                    'video_title': track_title,
                    'user_id': user_id
                }
            except (IndexError, KeyError):
                return None
        return None
