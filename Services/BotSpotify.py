from os import getcwd, environ

from nonebot.adapters.onebot.v11 import MessageSegment
from spotipy import Spotify, SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

from Services.util.common_util import OptionalDict, html_to_image
from model.common_model import Status


class BotSpotify:
    def __init__(self):
        self.scope = "user-library-read,user-read-playback-state,user-modify-playback-state"
        self.spotify_client_id = environ.get('SPOTIFY_CLIENT_ID', '')
        self.spotify_client_secret = environ.get('SPOTIFY_CLIENT_SECRET', '')

        self.spotify_api = None
        if self.spotify_client_id and self.spotify_client_secret:
            self.spotify_api = Spotify(auth_manager=SpotifyClientCredentials(
                client_id=self.spotify_client_id,
                client_secret=self.spotify_client_secret))

    async def what_ya_listening(self) -> Status:
        devices = await self._fetch_active_device()

        if not devices:
            return Status(False, '没有在听歌哦')

        track_id = OptionalDict(self.spotify_api.current_playback()).map('item').map('id').or_else('')
        return Status(True, MessageSegment.image(html_to_image(
            await self.generate_embed_html(track_id), run_hljs=False, render_spotify_iframe='spotify')))

    async def _fetch_active_device(self) -> dict:
        try:
            devices = self.spotify_api.devices().get('devices', [])
        except (SpotifyException, ConnectionError):
            self.spotify_api = Spotify(auth_manager=SpotifyOAuth(
                scope=self.scope,
                client_id=self.spotify_client_id,
                client_secret=self.spotify_client_secret,
                redirect_uri='http://localhost:3100'))
            devices = self.spotify_api.devices().get('devices', [])

        for device in devices:
            if device.get('is_active', False):
                return device

        return {}

    async def search_and_add_to_queue(self, search_term: str) -> Status:
        devices = await self._fetch_active_device()
        if devices:
            device_id = devices.get('id', None)
            if device_id:
                result_list = OptionalDict(self.spotify_api.search(search_term)).map('tracks').map('items').or_else([])
                first_item = result_list[0]
                uri = first_item.get('uri', None)
                track_id = first_item.get('id', None)
                if uri:
                    self.spotify_api.add_to_queue(uri, device_id)

                if track_id:
                    return Status(True, MessageSegment.image(html_to_image(
                        await self.generate_embed_html(track_id), run_hljs=False, render_spotify_iframe='spotify')))

        return Status(False, '主人好像没在听歌所以我没法添加歌进去哦')

    @staticmethod
    async def generate_embed_html(track_id: str):
        payload = f"""
<html lang="en">
<head>
    <title></title>
<body>
<div class="container">
    <iframe id="spotify" style="border-radius:12px"
            src="https://open.spotify.com/embed/track/{track_id}?utm_source=generator" width="100%" height="352"
            frameBorder="0" allowfullscreen=""
            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
    </body>
</div>
</html>
        """
        file_name = f'{getcwd()}/data/bot/response/{track_id}.html'
        with open(file_name, 'w+', encoding='utf-8-sig') as file:
            file.write(payload)

        return file_name


if __name__ == '__main__':
    a = BotSpotify()
    print(a.search_and_add_to_queue('pity party'))
