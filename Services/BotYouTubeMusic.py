import asyncio
from asyncio import get_running_loop
from dataclasses import dataclass
from os import environ, getcwd
from typing import Any, Optional

from dotenv import load_dotenv
from httpx import AsyncClient, HTTPStatusError, RequestError, Timeout
from loguru import logger
from nonebot.adapters.onebot.v11 import MessageSegment

from Services.util.common_util import html_to_image_async, OptionalDict
from Services.util.file_utils import delete_file_after
from model.common_model import Status
from util.helper_util import construct_message_chain


@dataclass(frozen=True)
class YouTubeMusicTrack:
    video_id: str
    title: str
    artists: list[str]
    album: Optional[str]
    artwork_url: Optional[str]
    elapsed_seconds: Optional[float] = None
    song_duration: Optional[float] = None


@dataclass(frozen=True)
class YouTubeMusicPlayback:
    track: Optional[YouTubeMusicTrack]
    is_playing: bool


class BotYouTubeMusic:
    def __init__(self) -> None:
        load_dotenv('.env')

        self.api_version = environ.get("YTM_COMPANION_API_VERSION", "v1")
        base_url_raw = environ.get("YTM_COMPANION_BASE_URL", "").strip()

        if base_url_raw and not base_url_raw.startswith(("http://", "https://")):
            base_url_raw = f"http://{base_url_raw}"

        self.base_url = base_url_raw.rstrip("/")
        self.api_key = environ.get("YTM_COMPANION_API_KEY", "").strip()
        self.timeout_seconds = float(environ.get("YTM_COMPANION_TIMEOUT", "8"))
        self._operation_lock = asyncio.Lock()

        if not self.base_url:
            logger.warning("YouTube Music companion base URL is not set")

    async def cut_song(self) -> Status:
        if self._operation_lock.locked():
            logger.warning("cut_song: Operation already in progress, discarding request")
            return Status(False, "操作进行中，请稍后再试")

        async with self._operation_lock:
            # First, switch to next song
            ok = await self._request_no_content("POST", f"/api/{self.api_version}/next")
            if not ok:
                return Status(False, "切歌失败了")

            await asyncio.sleep(2.5)

            payload = await self._request_json("GET", f"/api/{self.api_version}/song-info")
            if payload is None:
                return Status(False, "搞不来喵")

            track = self._parse_track_from_song_info(payload)
            if track is None:
                return Status(False, "搞不来喵")

            image_path = await self._render_track_card_html(track)
            if image_path is not None:
                return Status(True, MessageSegment.image(image_path))

            artists = ", ".join(track.artists) if track.artists else "未知"
            return Status(True, f"已切歌: {track.title}\n{artists}")

    async def next_song_info(self) -> Status:
        if self._operation_lock.locked():
            logger.warning("next_song_info: Operation already in progress, discarding request")
            return Status(False, "操作进行中，请稍后再试")

        async with self._operation_lock:
            ok = await self._request_no_content("POST", f"/api/{self.api_version}/next")
            if not ok:
                return Status(False, "切歌失败了")

            await asyncio.sleep(2.5)

            payload = await self._request_json("GET", f"/api/{self.api_version}/song-info")
            if payload is None:
                return Status(False, "没有下一首哦")

            track = self._parse_track_from_song_info(payload)
            if track is None:
                return Status(False, "没有下一首哦")

            image_path = await self._render_track_card_html(track)
            if image_path is not None:
                return Status(True, MessageSegment.image(image_path))

            artists = ", ".join(track.artists) if track.artists else "未知"
            return Status(True, f"下一首: {track.title}\n{artists}\nhttps://music.youtube.com/watch?v={track.video_id}")

    async def what_ya_listening(self) -> Status:
        if self._operation_lock.locked():
            logger.warning("what_ya_listening: Operation already in progress, discarding request")
            return Status(False, "操作进行中，请稍后再试")

        async with self._operation_lock:
            payload = await self._request_json("GET", f"/api/{self.api_version}/song-info")
            if payload is None:
                return Status(False, "没有在听歌哦")

            track = self._parse_track_from_song_info(payload)
            if track is None:
                return Status(False, "没有在听歌哦")

            image_path = await self._render_track_card_html(track)
            if image_path is not None:
                return Status(True, MessageSegment.image(image_path))

            artists = ", ".join(track.artists) if track.artists else "未知"
            return Status(True, f"{track.title}\n{artists}\nhttps://music.youtube.com/watch?v={track.video_id}")

    async def search_and_add_to_next_queue(self, search_term: str) -> Status:
        if self._operation_lock.locked():
            logger.warning("search_and_add_to_next_queue: Operation already in progress, discarding request")
            return Status(False, "操作进行中，请稍后再试")

        async with self._operation_lock:
            track = await self._search_first_track(search_term)
            if track is None:
                return Status(False, "没有找到符合的歌曲哦")

            ok = await self._add_song_to_queue(track.video_id, insert_after_current=True)
            if not ok:
                return Status(False, "添加失败了")

            image_path = await self._render_track_card_html(track)
            if image_path is not None:
                return Status(True, construct_message_chain('已添加到下一首', MessageSegment.image(image_path)))

            artists = ", ".join(track.artists) if track.artists else "未知"
            return Status(True,
                          f"已添加到下一首: {track.title}\n{artists}\nhttps://music.youtube.com/watch?v={track.video_id}")

    async def _render_track_card_html(self, track: YouTubeMusicTrack) -> Optional[str]:
        try:
            track_with_local_artwork = await self._ensure_local_artwork(track)
            html_file = await self.generate_now_playing_html(track_with_local_artwork)
            image_path = await html_to_image_async(html_file, run_hljs=False)
            get_running_loop().create_task(delete_file_after(image_path, 20))
            return image_path
        except BaseException as err:
            logger.exception(f"HTML render failed ({err.__class__.__name__})")
            return None

    @staticmethod
    async def _ensure_local_artwork(track: YouTubeMusicTrack) -> YouTubeMusicTrack:
        if not track.artwork_url:
            return track

        if track.artwork_url.startswith("file://"):
            return track

        artwork_url = track.artwork_url
        if not artwork_url.startswith(("http://", "https://")):
            artwork_url = f"https://{artwork_url}"

        try:
            from hashlib import md5
            url_hash = md5(artwork_url.encode()).hexdigest()[:16]
            local_path = f"{getcwd()}/data/bot/response/ytm_artwork_{url_hash}.jpg"

            from os.path import exists
            if not exists(local_path):
                logger.info(f"Downloading artwork: {artwork_url}")
                timeout = Timeout(10.0)
                async with AsyncClient(timeout=timeout) as client:
                    response = await client.get(artwork_url)
                    response.raise_for_status()

                    with open(local_path, "wb") as f:
                        f.write(response.content)

            file_url = f"file:///{local_path}"
            return YouTubeMusicTrack(
                video_id=track.video_id,
                title=track.title,
                artists=track.artists,
                album=track.album,
                artwork_url=file_url,
                elapsed_seconds=track.elapsed_seconds,
                song_duration=track.song_duration,
            )
        except BaseException as err:
            logger.error(f"Failed to download artwork ({err.__class__.__name__}): {artwork_url}")
            return track

    async def _get_now_playing(self) -> Optional[YouTubeMusicPlayback]:
        payload = await self._request_json("GET", f"/api/{self.api_version}/song-info")
        if payload is None:
            return None

        track = self._parse_track_from_song_info(payload)
        return YouTubeMusicPlayback(track=track, is_playing=True)

    async def _search_first_track(self, search_term: str) -> Optional[YouTubeMusicTrack]:
        payload = await self._request_json(
            "POST",
            f"/api/{self.api_version}/search",
            json={"query": search_term},
        )
        if payload is None:
            return None

        return self._parse_track_from_search_payload(payload)

    async def _add_song_to_queue(self, video_id: str, insert_after_current: bool) -> bool:
        insert_position = "INSERT_AFTER_CURRENT_VIDEO" if insert_after_current else "INSERT_AT_END"
        ok = await self._request_no_content(
            "POST",
            f"/api/{self.api_version}/queue",
            json={"videoId": video_id, "insertPosition": insert_position},
        )
        return ok

    @staticmethod
    def _parse_track_from_song_info(payload: dict[str, Any]) -> Optional[YouTubeMusicTrack]:
        opt = OptionalDict(payload)

        video_id = opt.map("videoId").or_else(None)
        if not isinstance(video_id, str) or not video_id:
            return None

        title = opt.map("alternativeTitle").or_else(None) or opt.map("title").or_else(video_id)

        artist = opt.map("artist").or_else(None)
        artists = [artist.strip()] if isinstance(artist, str) and artist.strip() else []

        album = opt.map("album").or_else(None)
        album = album if isinstance(album, str) else None

        artwork_url = opt.map("imageSrc").or_else(None)
        artwork_url = artwork_url if isinstance(artwork_url, str) and artwork_url else None

        elapsed_seconds = opt.map("elapsedSeconds").or_else(None)
        elapsed_seconds = float(elapsed_seconds) if isinstance(elapsed_seconds, (int, float)) else None

        song_duration = opt.map("songDuration").or_else(None)
        song_duration = float(song_duration) if isinstance(song_duration, (int, float)) else None

        return YouTubeMusicTrack(
            video_id=video_id,
            title=title,
            artists=artists,
            album=album,
            artwork_url=artwork_url,
            elapsed_seconds=elapsed_seconds,
            song_duration=song_duration,
        )

    def _parse_track_from_search_payload(self, payload: dict[str, Any]) -> Optional[YouTubeMusicTrack]:
        hit = self._find_first_song_renderer(payload)
        if hit is not None:
            video_id = hit.get("videoId")
            title = self._extract_title_text(hit.get("title"))
            artists = self._extract_artists(hit)
            artwork_url = self._extract_artwork_from_search_renderer(hit)
            album = None
            if not isinstance(video_id, str) or not video_id:
                return None

            title = title if title else video_id
            return YouTubeMusicTrack(
                video_id=video_id, title=title, artists=artists, album=album, artwork_url=artwork_url)

        video_id = self._find_first_string_value(payload, "videoId")
        title = self._find_first_string_value(payload, "title")
        if not isinstance(video_id, str) or not video_id:
            return None

        title = title if isinstance(title, str) and title else video_id
        return YouTubeMusicTrack(video_id=video_id, title=title, artists=[], album=None, artwork_url=None)

    def _find_all_song_renderers(self, payload: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        if isinstance(payload, dict):
            opt = OptionalDict(payload)
            renderer = opt.map("musicResponsiveListItemRenderer").or_else(None)

            if isinstance(renderer, dict):
                renderer_opt = OptionalDict(renderer)
                playlist_data = renderer_opt.map("playlistItemData").or_else(None)

                if isinstance(playlist_data, dict):
                    video_id = OptionalDict(playlist_data).map("videoId").or_else(None)
                    if isinstance(video_id, str):
                        results.append({
                            "videoId": video_id,
                            "title": renderer_opt.map("flexColumns").or_else(None),
                            "renderer": renderer,
                        })

            for v in payload.values():
                results.extend(self._find_all_song_renderers(v))

        elif isinstance(payload, list):
            for item in payload:
                results.extend(self._find_all_song_renderers(item))

        return results

    def _find_first_song_renderer(self, payload: Any) -> Optional[dict[str, Any]]:
        all_renderers = self._find_all_song_renderers(payload)
        return all_renderers[0] if all_renderers else None

    def _find_most_played_song_renderer(self, payload: Any) -> Optional[dict[str, Any]]:
        all_renderers = self._find_all_song_renderers(payload)
        if not all_renderers:
            return None

        best_renderer = None
        best_score = -1

        for index, renderer_data in enumerate(all_renderers):
            play_count = self._extract_play_count(renderer_data)

            relevance_score = 1.0 / (index + 1)

            play_count_score = play_count / 1_000_000 if play_count > 0 else 0

            combined_score = (relevance_score * 0.6) + (play_count_score * 0.4)

            if combined_score > best_score:
                best_score = combined_score
                best_renderer = renderer_data

        return best_renderer if best_renderer else all_renderers[0]

    @staticmethod
    def _extract_play_count(hit: dict[str, Any]) -> int:
        renderer_opt = OptionalDict(hit).map("renderer")
        flex_columns = renderer_opt.map("flexColumns").or_else(None)

        if not isinstance(flex_columns, list):
            return 0

        for col in flex_columns:
            if not isinstance(col, dict):
                continue

            col_opt = OptionalDict(col)
            flex = col_opt.map("musicResponsiveListItemFlexColumnRenderer").or_else(None)

            if not isinstance(flex, dict):
                continue

            text_obj = OptionalDict(flex).map("text").or_else(None)
            runs = OptionalDict(text_obj).map("runs").or_else(None)

            if not isinstance(runs, list):
                continue

            for run in runs:
                text = OptionalDict(run).map("text").or_else(None)
                if not isinstance(text, str):
                    continue

                text_lower = text.lower().strip()
                if "view" in text_lower or "play" in text_lower or "次" in text_lower or "watching" in text_lower:
                    from re import search

                    match = search(r'([\d,.]+)\s*([kmb])?', text_lower)
                    if match:
                        try:
                            number_str = match.group(1).replace(',', '')
                            suffix = match.group(2)

                            base_number = float(number_str)

                            if suffix == 'k':
                                return int(base_number * 1_000)
                            elif suffix == 'm':
                                return int(base_number * 1_000_000)
                            elif suffix == 'b':
                                return int(base_number * 1_000_000_000)
                            else:
                                return int(base_number)
                        except (ValueError, AttributeError):
                            pass

        return 0

    def _extract_title_text(self, maybe_flex_columns: Any) -> Optional[str]:
        if not isinstance(maybe_flex_columns, list):
            return None

        for col in maybe_flex_columns:
            if not isinstance(col, dict):
                continue

            col_opt = OptionalDict(col)
            flex = col_opt.map("musicResponsiveListItemFlexColumnRenderer").or_else(None)

            if isinstance(flex, dict):
                text = OptionalDict(flex).map("text").or_else(None)
                title = self._extract_runs_text(text)
                if title:
                    return title

        return None

    @staticmethod
    def _extract_runs_text(payload: Any) -> Optional[str]:
        if not isinstance(payload, dict):
            return None

        runs = OptionalDict(payload).map("runs").or_else(None)
        if not isinstance(runs, list) or not runs:
            return None

        text = OptionalDict(runs[0]).map("text").or_else(None)
        return text.strip() if isinstance(text, str) and text.strip() else None

    @staticmethod
    def _extract_artists(hit: dict[str, Any]) -> list[str]:
        renderer_opt = OptionalDict(hit).map("renderer")
        flex_columns = renderer_opt.map("flexColumns").or_else(None)

        if not isinstance(flex_columns, list) or len(flex_columns) < 2:
            return []

        second_column_opt = OptionalDict(flex_columns[1])
        flex_opt = second_column_opt.map("musicResponsiveListItemFlexColumnRenderer")
        text_opt = flex_opt.map("text")
        runs = text_opt.map("runs").or_else(None)

        if not isinstance(runs, list):
            return []

        artists: list[str] = []
        for run in runs:
            text = OptionalDict(run).map("text").or_else(None)
            if isinstance(text, str) and text.strip() and text.strip() != "•":
                artists.append(text.strip())

        return artists

    @staticmethod
    def _extract_artwork_from_search_renderer(hit: dict[str, Any]) -> Optional[str]:
        renderer_opt = OptionalDict(hit).map("renderer")
        thumbnail_obj = renderer_opt.map("thumbnail").or_else(None)

        if not isinstance(thumbnail_obj, dict):
            return None

        music_thumbnail = OptionalDict(thumbnail_obj).map("musicThumbnailRenderer").or_else(None)
        if isinstance(music_thumbnail, dict):
            thumbnail_obj = OptionalDict(music_thumbnail).map("thumbnail").or_else(None)

        if not isinstance(thumbnail_obj, dict):
            return None

        thumbnails = OptionalDict(thumbnail_obj).map("thumbnails").or_else(None)
        if not isinstance(thumbnails, list) or not thumbnails:
            return None

        last_thumbnail = OptionalDict(thumbnails[-1])
        url = last_thumbnail.map("url").or_else(None)

        return url if isinstance(url, str) and url else None

    def _parse_track_from_queue_payload(self, payload: dict[str, Any]) -> Optional[YouTubeMusicTrack]:
        video_renderer = self._extract_video_renderer(payload)
        if not video_renderer:
            return None

        video_id = self._extract_video_id(video_renderer)
        if not video_id:
            return None

        title = self._extract_title(video_renderer) or video_id
        artists = self._extract_artists_from_video_renderer(video_renderer)
        artwork_url = self._extract_artwork_url(video_renderer)

        return YouTubeMusicTrack(
            video_id=video_id,
            title=title,
            artists=artists,
            album=None,
            artwork_url=artwork_url,
        )

    @staticmethod
    def _extract_video_renderer(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        opt = OptionalDict(payload)
        items = opt.map("items").or_else(None)

        if not isinstance(items, list) or not items:
            return None

        first_item_opt = OptionalDict(items[0])
        wrapper_opt = first_item_opt.map("playlistPanelVideoWrapperRenderer")
        primary_opt = wrapper_opt.map("primaryRenderer")
        video_renderer = primary_opt.map("playlistPanelVideoRenderer").or_else(None)

        return video_renderer if isinstance(video_renderer, dict) else None

    @staticmethod
    def _extract_video_id(video_renderer: dict[str, Any]) -> Optional[str]:
        video_id = OptionalDict(video_renderer).map("videoId").or_else(None)
        return video_id if isinstance(video_id, str) and video_id else None

    @staticmethod
    def _extract_title(video_renderer: dict[str, Any]) -> Optional[str]:
        opt = OptionalDict(video_renderer)
        title_obj = opt.map("title").or_else(None)

        if not isinstance(title_obj, dict):
            return None

        runs = OptionalDict(title_obj).map("runs").or_else(None)
        if not isinstance(runs, list) or not runs:
            return None

        text = OptionalDict(runs[0]).map("text").or_else(None)
        return text if isinstance(text, str) and text else None

    @staticmethod
    def _extract_artists_from_video_renderer(video_renderer: dict[str, Any]) -> list[str]:
        opt = OptionalDict(video_renderer)
        byline = opt.map("longBylineText").or_else(None)

        if not isinstance(byline, dict):
            return []

        runs = OptionalDict(byline).map("runs").or_else(None)
        if not isinstance(runs, list):
            return []

        artists = []
        for run in runs:
            text = OptionalDict(run).map("text").or_else(None)
            if isinstance(text, str) and text.strip():
                artists.append(text.strip())

        return artists

    @staticmethod
    def _extract_artwork_url(video_renderer: dict[str, Any]) -> Optional[str]:
        opt = OptionalDict(video_renderer)
        thumb = opt.map("thumbnail").or_else(None)

        if not isinstance(thumb, dict):
            return None

        thumbnails = OptionalDict(thumb).map("thumbnails").or_else(None)
        if not isinstance(thumbnails, list) or not thumbnails:
            return None

        last_thumbnail = OptionalDict(thumbnails[-1])
        url = last_thumbnail.map("url").or_else(None)

        return url if isinstance(url, str) and url else None

    def _find_first_string_value(self, payload: Any, key: str) -> Optional[str]:
        if isinstance(payload, dict):
            for k, v in payload.items():
                if k == key and isinstance(v, str):
                    return v
                found = self._find_first_string_value(v, key)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = self._find_first_string_value(item, key)
                if found is not None:
                    return found

        return None

    async def _request_no_content(
            self,
            method: str,
            api_path: str,
            json: Optional[dict[str, Any]] = None,
    ) -> bool:
        url = f"{self.base_url}{api_path}"
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            timeout = Timeout(self.timeout_seconds)
            async with AsyncClient(timeout=timeout, headers=headers) as client:
                response = await client.request(method=method, url=url, json=json)

            return response.status_code == 204
        except (RequestError, ConnectionError) as err:
            logger.error(f"YouTube Music companion request failed: {url} ({err.__class__.__name__})")
            return False
        except BaseException as err:
            logger.exception(f"YouTube Music companion unexpected error: {url} ({err.__class__.__name__})")
            return False

    async def _request_json(
            self,
            method: str,
            api_path: str,
            params: Optional[dict[str, Any]] = None,
            json: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        url = f"{self.base_url}{api_path}"
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            timeout = Timeout(self.timeout_seconds)
            async with AsyncClient(timeout=timeout, headers=headers) as client:
                response = await client.request(method=method, url=url, params=params, json=json)

            if response.status_code == 204:
                return None

            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, dict):
                return payload

            return None
        except HTTPStatusError as err:
            status_code = err.response.status_code
            if status_code in {401, 403}:
                logger.error(f"YouTube Music companion auth failed: {status_code} {url}")
            else:
                logger.error(f"YouTube Music companion http error: {status_code} {url}")
            return None
        except (RequestError, ConnectionError) as err:
            logger.error(f"YouTube Music companion request failed: {url} ({err.__class__.__name__})")
            return None
        except ValueError as err:
            logger.error(f"YouTube Music companion invalid json: {url} ({err.__class__.__name__})")
            return None
        except BaseException as err:
            logger.exception(f"YouTube Music companion unexpected error: {url} ({err.__class__.__name__})")
            return None

    @staticmethod
    async def generate_now_playing_html(track: YouTubeMusicTrack) -> str:
        template_path = f"{getcwd()}/data/util/ytm_now_playing_template.html"

        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        artists = ", ".join(track.artists) if track.artists else "未知"
        artwork_url = track.artwork_url or ""
        album_html = f'<div class="album">{track.album}</div>' if track.album else ''

        progress_html = ''
        if track.elapsed_seconds is not None and track.song_duration is not None and track.song_duration > 0:
            progress_percentage = (track.elapsed_seconds / track.song_duration) * 100
            progress_percentage = min(100.0, max(0.0, progress_percentage))

            elapsed_minutes = int(track.elapsed_seconds // 60)
            elapsed_seconds = int(track.elapsed_seconds % 60)
            duration_minutes = int(track.song_duration // 60)
            duration_seconds = int(track.song_duration % 60)

            elapsed_time_str = f"{elapsed_minutes}:{elapsed_seconds:02d}"
            duration_time_str = f"{duration_minutes}:{duration_seconds:02d}"

            progress_html = f'''
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {progress_percentage:.1f}%"></div>
                </div>
                <div class="time-labels">
                    <span class="time-elapsed">{elapsed_time_str}</span>
                    <span class="time-duration">{duration_time_str}</span>
                </div>
            </div>
            '''

        html_content = template.format(
            title=track.title,
            artists=artists,
            artwork_url=artwork_url,
            album_html=album_html,
            progress_html=progress_html
        )

        file_name = f"{getcwd()}/data/bot/response/ytm_{track.video_id}.html"
        with open(file_name, "w+", encoding="utf-8-sig") as file:
            file.write(html_content)

        return file_name

    async def _get_next_track_preview(self) -> Optional[YouTubeMusicTrack]:
        payload = await self._request_json("GET", f"/api/{self.api_version}/song-info", params={"index": 1})
        track = self._parse_track_from_song_info(payload) if isinstance(payload, dict) else None
        if track is not None:
            return track

        queue_payload = await self._request_json("GET", f"/api/{self.api_version}/queue", params={"index": 1})
        if isinstance(queue_payload, dict):
            return self._parse_track_from_queue_payload(queue_payload)

        return None
