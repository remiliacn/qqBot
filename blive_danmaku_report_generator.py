import asyncio
import codecs
import http.cookies
import pickle
import re
import sys
import time
from functools import lru_cache
from os import getpid, getcwd, stat
from random import randint
from typing import Optional, List, Dict, Tuple

import aiohttp
import numpy as np
from dateutil import parser
from matplotlib import font_manager, rc, rcParams, ticker
from nonebot.log import logger

import blivedm.models.web as web_models
from Services import live_notification
from Services.live_notification import LivestreamDanmakuData
from Services.util.common_util import OptionalDict, find_repeated_substring, construct_timestamp_string, gradient_fill
from blivedm import BaseHandler, BLiveClient
from blivedm.clients import ws_base
from config import BILI_SESS_DATA

FIVE_MINUTES = 60 * 5
TWENTY_FIVE_MINUTES = 60 * 25
# Make it random because it is funny lol
TOP_TIMESTAMP_LIMIT = randint(5, 7)

_GRAPH_BUCKET_SECONDS = 60

_DANMAKU_SPLIT_PATTERN = re.compile(r'[\s+,，。、?？！!]+')
_DANMAKU_ONLY_SEPARATORS_PATTERN = re.compile(r'^[\s+,，。、?？！!]+$')

_DANMAKU_STRIP_TRANSLATION_TABLE = str.maketrans({
    '（': None,
    '）': None,
    '(': None,
    ')': None,
})

_DANMAKU_INFO_LOG_SAMPLE_RATE = 1

font_path = f'{getcwd()}/Services/util/SourceHanSansSC-Bold.otf'
font_manager.fontManager.addfont(font_path)
prop = font_manager.FontProperties(fname=font_path)

rc('font', family='sans-serif')
rcParams.update({
    'font.size': 12,
    'font.sans-serif': prop.get_name()
})


def _get_log_filename() -> str:
    return f'log_{int(time.time())}_{getpid()}.log'


logger.add(f'./logs/{_get_log_filename()}', level='INFO', colorize=False, backtrace=True, diagnose=True,
           rotation='50MB', retention='3 days')


class MyDanmakuHandler(BaseHandler):
    def __init__(self):
        self.BLACKLIST_DANMAKU_FILE = f'{getcwd()}/data/live/utils/danmaku_blacklist.txt'
        self.danmaku_frequency_dict: Dict[str, int] = {}

        self.highest_rank = 99999
        self.like_received_count = self.danmaku_count = 0
        self.gift_received_count = self.new_captains = self.gift_price = 0
        self.room_id = self.group_ids = ''

        self.stream_start_time = time.time()
        self.stream_danmaku_bucket_counts: Dict[float, int] = {}
        self.captain_purchase_bucket_counts: Dict[float, int] = {}
        self.stop_event = asyncio.Event()

    @lru_cache(maxsize=None)
    def _get_blacklist_danmaku(self, _cache_time: Optional[float] = None) -> List[str]:
        with open(self.BLACKLIST_DANMAKU_FILE, 'r', encoding='utf-8-sig') as f:
            return [x.strip().lower() for x in f.readlines() if x.strip()]

    def set_room_id(self, parsed_in_room_id: str) -> None:
        self.room_id = parsed_in_room_id

    def set_group_ids(self, group_ids_dumped: str) -> None:
        self.group_ids = group_ids_dumped

    def set_start_time(self, start_time: int) -> None:
        self.stream_start_time = start_time

    def add_danmaku_into_frequency_dict(self, message: web_models.DanmakuMessage) -> None:
        msg = message.msg
        if not msg:
            return

        msg = msg.lower().translate(_DANMAKU_STRIP_TRANSLATION_TABLE)

        if msg.startswith('['):
            return

        if self._is_blacklist_word(msg):
            return

        self.danmaku_count += 1
        if self.danmaku_count % _DANMAKU_INFO_LOG_SAMPLE_RATE == 0:
            logger.info(f'Message received: {message.msg}, name: {message.uname}, receive_time: {message.timestamp}')

        time_elapsed_time = time.time() - self.stream_start_time
        if time_elapsed_time > FIVE_MINUTES:
            bucket = float(int(time_elapsed_time // _GRAPH_BUCKET_SECONDS) * _GRAPH_BUCKET_SECONDS)
            self.stream_danmaku_bucket_counts[bucket] = self.stream_danmaku_bucket_counts.get(bucket, 0) + 1

        if _DANMAKU_ONLY_SEPARATORS_PATTERN.fullmatch(msg) is not None:
            message_list = [msg]
        else:
            seen: set[str] = set()
            message_list: List[str] = []
            for token in _DANMAKU_SPLIT_PATTERN.split(msg):
                token = token.strip()
                if not token or token in seen:
                    continue
                seen.add(token)
                message_list.append(token)

        for token in message_list:
            token = find_repeated_substring(token)
            if not token or len(token) > 9:
                continue
            self.danmaku_frequency_dict[token] = self.danmaku_frequency_dict.get(token, 0) + 1

    _CMD_CALLBACK_DICT = BaseHandler._CMD_CALLBACK_DICT.copy()

    @lru_cache(maxsize=800)
    def _is_blacklist_word(self, message: str) -> bool:
        try:
            mtime = stat(self.BLACKLIST_DANMAKU_FILE).st_mtime
        except OSError:
            mtime = None

        for blacklist in self._get_blacklist_danmaku(mtime):
            if blacklist and blacklist in message:
                logger.debug(f'Blacklist hit: {blacklist} in {message}')
                return True

        return False

    def _like_info_v3_callback(self, client: BLiveClient, command: dict):
        self.like_received_count += 1
        logger.debug(
            f'收到点赞， {client.room_id}, 点赞人：{OptionalDict(command).map("data").map("uname").or_else("?")}')

    # noinspection PyUnusedLocal
    def _popularity_change(self, client: BLiveClient, command: dict):
        rank = OptionalDict(command).map("data").map("rank").or_else(999)
        logger.debug(f'人气榜变动，目前人气档位：{rank}')
        if rank > 0:
            self.highest_rank = min(self.highest_rank, rank)

    # noinspection PyUnusedLocal
    def _user_toast_msg(self, client: BLiveClient, command: dict):
        captain_price = 0
        captain_count = 0

        if command['cmd'] == 'USER_TOAST_MSG_V2':
            if OptionalDict(command).map("guard_info").or_else(None) is not None:
                captain_data = OptionalDict(command).map("data").map("pay_info").or_else({})
                captain_price = OptionalDict(captain_data).map("price").or_else(0)
                captain_count = OptionalDict(captain_data).map("num").or_else(0)
        else:
            if OptionalDict(command).map("data").or_else(None) is not None:
                captain_price = OptionalDict(command).map("data").map("price").or_else(0)
                captain_count = OptionalDict(command).map("data").map("num").or_else(0)
                uid = OptionalDict(command).map("data").map("uid").or_else(-1)
                guard_level = OptionalDict(command).map("data").map("guard_level").or_else(0)
                username = OptionalDict(command).map("data").map("username").or_else('?')
                logger.info(command)
                logger.info(f'有新舰长？：{OptionalDict(command).map("data").map("role_name").or_else("未知数据")}'
                            f' x {captain_count} -> 价格：{captain_price} ->'
                            f' {uid}')

                live_notification.insert_sail_data(uid, guard_level, self.room_id, username)
        if captain_price > 0:
            self.gift_price += (captain_price / 1000) * captain_count

        self.new_captains += captain_count
        if captain_count > 0:
            time_elapsed_time = time.time() - self.stream_start_time
            bucket = float(int(time_elapsed_time // _GRAPH_BUCKET_SECONDS) * _GRAPH_BUCKET_SECONDS)
            self.captain_purchase_bucket_counts[bucket] = (
                    self.captain_purchase_bucket_counts.get(bucket, 0) + captain_count
            )

    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['LIKE_INFO_V3_CLICK'] = _like_info_v3_callback
    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['POPULAR_RANK_CHANGED'] = _popularity_change
    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['USER_TOAST_MSG'] = _user_toast_msg
    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['USER_TOAST_MSG_V2'] = _user_toast_msg

    def _on_heartbeat(self, client: ws_base.WebSocketClientBase, message: web_models.HeartbeatMessage):
        if self.stop_event.is_set():
            return

        if not live_notification.check_if_live_cached(self.room_id):
            logger.success(f'Livestream is not going anymore for room id: {self.room_id},'
                           f' dumping the data. Total gift value: {self.gift_price}')

            try:
                hotspot_timestamp_data = get_sorted_timestamp_hotspot(
                    self.stream_danmaku_bucket_counts, TWENTY_FIVE_MINUTES)
            except (ValueError, TypeError):
                logger.exception('Failed to get hotspot data')
                hotspot_timestamp_data = []

            try:
                danmaku_graph_hotspot = _get_sorted_hotspot_time_to_frequency(self.stream_danmaku_bucket_counts)
                captain_graph_hotspot = dict(self.captain_purchase_bucket_counts)
                logger.info(f'Danmaku graph hotspot list: {danmaku_graph_hotspot}')
                file_name = _draw_danmaku_frequency_graph(danmaku_graph_hotspot, captain_graph_hotspot)
            except (OSError, RuntimeError, ValueError):
                logger.exception('Failed to get danmaku graph data')
                file_name = ''

            pickled_data = codecs.encode(pickle.dumps(LivestreamDanmakuData(
                danmaku_count=self.danmaku_count,
                danmaku_frequency_dict=self.danmaku_frequency_dict,
                qq_group_dumped=self.group_ids,
                like_received_count=self.like_received_count,
                gift_received_count=self.gift_received_count,
                highest_rank=self.highest_rank if self.highest_rank <= 100 else '未知',
                gift_total_price=self.gift_price if live_notification.is_fetch_gift_price(self.room_id) else 0,
                new_captains=self.new_captains,
                top_crazy_timestamps=hotspot_timestamp_data,
                danmaku_analyze_graph=file_name
            )), 'base64').decode()
            live_notification.dump_live_data(pickled_data)

            find_repeated_substring.cache_clear()
            self.stop_event.set()
            exit(0)

    def _on_gift(self, client: BLiveClient, message: web_models.GiftMessage):
        self.gift_received_count += message.num
        if message.coin_type.lower() == 'gold':
            self.gift_price += message.total_coin / 1000

    def _on_danmaku(self, client: BLiveClient, message: web_models.DanmakuMessage):
        self.add_danmaku_into_frequency_dict(message)

    def _on_super_chat(self, client: BLiveClient, message: web_models.SuperChatMessage):
        self.gift_received_count += 1
        self.gift_price += message.price
        logger.info(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')


# 直播间ID的取值看直播间URL
TEST_ROOM_IDS = []

# 这里填一个已登录账号的cookie。不填cookie也可以连接，但是收到弹幕的用户名会打码，UID会变成0
SESSDATA = BILI_SESS_DATA

session: Optional[aiohttp.ClientSession] = None
handler = MyDanmakuHandler()


async def main() -> None:
    global TEST_ROOM_IDS
    argv = sys.argv
    if not sys.argv or len(argv) != 4:
        raise RuntimeError('No argv, should includes at least one room id.')

    logger.info(f'Starting job with argv: {argv}')
    room_id = argv[1]
    group_ids = argv[2]
    start_time = argv[3]

    start_timestamp = int(parser.parse(start_time).timestamp())

    handler.set_start_time(start_timestamp)
    handler.set_room_id(room_id)
    handler.set_group_ids(group_ids)

    TEST_ROOM_IDS.append(room_id)

    init_session()
    try:
        await run_listening()
    finally:
        if session is not None:
            await session.close()


def init_session() -> None:
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = SESSDATA
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)


def hotspot_analyzation(timestamps: List[float], intervals: int = 60) -> Dict[float, int]:
    timestamps_sorted = sorted(timestamps)
    result_dict: Dict[float, int] = {}

    for timestamp in timestamps_sorted:
        interval_key = float(timestamp // intervals) * intervals
        result_dict[interval_key] = result_dict.get(interval_key, 0) + 1

    return result_dict


def _bucket_counts_to_series(bucket_counts: Dict[float, int]) -> Tuple[List[float], List[int]]:
    sorted_result = sorted(bucket_counts.items(), key=lambda x: x[0])
    x_axis_data = [float(x[0]) for x in sorted_result]
    y_axis_data = [int(x[1]) for x in sorted_result]
    return x_axis_data, y_axis_data


def seconds_to_hms(x: float, _pos: object) -> str:
    hours, remainder = divmod(x, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{int(hours):02}:{int(minutes):02}:{int(seconds):02}'


def _draw_danmaku_frequency_graph(
        data_tuple: Tuple[List[float], List[float]],
        captain_bucket_counts: Optional[Dict[float, int]] = None,
) -> str:
    import matplotlib.pyplot as plt
    from scipy.ndimage import gaussian_filter1d

    x_axis_data, y_axis_data = data_tuple

    # Styling/theme lives here so the output stays consistent across environments.
    plt.rcParams.update({
        'axes.unicode_minus': False,
        'axes.facecolor': '#0b1220',
        'figure.facecolor': '#0b1220',
        'savefig.facecolor': '#0b1220',
        'axes.edgecolor': '#1f2a3a',
        'axes.labelcolor': '#e6edf3',
        'text.color': '#e6edf3',
        'xtick.color': '#c9d1d9',
        'ytick.color': '#c9d1d9',
        'grid.color': '#223044',
        'grid.alpha': 0.45,
        'font.size': 12,
    })

    fig, ax = plt.subplots(figsize=(12.5, 6.5), dpi=160)

    ax.grid(True, which='major', axis='both', linestyle='-', linewidth=0.8)

    for spine_name in ('top', 'right'):
        ax.spines[spine_name].set_visible(False)

    ax.spines['left'].set_linewidth(1.0)
    ax.spines['bottom'].set_linewidth(1.0)

    line_color = '#22c55e'
    glow_color = '#34d399'

    if not x_axis_data or not y_axis_data:
        ax.set_title('弹幕活跃趋势', fontsize=18, fontweight='bold', pad=16)
        ax.text(
            0.5,
            0.5,
            '暂无可用数据',
            transform=ax.transAxes,
            ha='center',
            va='center',
            fontsize=14,
            color='#c9d1d9',
        )
        ax.set_xticks([])
        ax.set_yticks([])
        file_name = f'{getcwd()}/data/live/{int(time.time())}_danmaku.png'
        fig.savefig(file_name, bbox_inches='tight', pad_inches=0.25)
        plt.close(fig)
        return file_name

    y_array = np.asarray(y_axis_data, dtype=float)

    # When drawing on a linear axis, we can smooth directly.
    smoothed_y_axis_data: np.ndarray = gaussian_filter1d(y_array, sigma=2)

    # Main curve: crisp line + soft glow + gradient fill under the curve.
    ax.plot(x_axis_data, smoothed_y_axis_data, linewidth=3.0, color=line_color, solid_capstyle='round', zorder=3)
    ax.plot(
        x_axis_data,
        smoothed_y_axis_data,
        linewidth=7.0,
        color=glow_color,
        alpha=0.18,
        solid_capstyle='round',
        zorder=2,
    )

    gradient_fill(x_axis_data, smoothed_y_axis_data, alpha=0.45, color=line_color)

    # Linear scale (rollback from log scale).

    ax.xaxis.set_major_formatter(ticker.FuncFormatter(seconds_to_hms))
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
    ax.tick_params(axis='both', which='major', length=0)

    ax.set_title('弹幕活跃趋势', fontsize=18, fontweight='bold', pad=16)
    ax.set_xlabel('直播时间（误差±1分钟）', labelpad=10)
    ax.set_ylabel('弹幕量 / 分钟', labelpad=10)

    x_min = float(x_axis_data[0])
    x_max = float(x_axis_data[-1])
    duration_seconds = max(0.0, x_max - x_min)

    total_messages = int(np.nansum(y_array))
    mean_per_min = float(np.nanmean(y_array)) if len(y_array) else 0.0

    captain_total = 0
    if captain_bucket_counts:
        captain_total = int(sum(captain_bucket_counts.values()))

    try:
        peak_idx = int(np.nanargmax(smoothed_y_axis_data))
        peak_x = float(x_axis_data[peak_idx])
        peak_y = float(smoothed_y_axis_data[peak_idx])
        peak_label = f'{int(peak_y):,}'

        ax.scatter([peak_x], [peak_y], s=48, color='#fbbf24', zorder=4)
        ax.annotate(
            f'峰值 {peak_label}',
            xy=(peak_x, peak_y),
            xytext=(10, 12),
            textcoords='offset points',
            fontsize=11,
            color='#fbbf24',
            bbox={
                'boxstyle': 'round,pad=0.35',
                'fc': '#111827',
                'ec': '#f59e0b',
                'alpha': 0.85,
            },
            arrowprops={
                'arrowstyle': '-',
                'color': '#f59e0b',
                'alpha': 0.65,
                'lw': 1.2,
            },
            zorder=5,
        )
    except (ValueError, IndexError, TypeError):
        logger.exception('Failed to annotate peak value on graph')
        peak_x = float('nan')
        peak_y = float('nan')

    subtitle = f"区间 {seconds_to_hms(x_min, None)} → {seconds_to_hms(x_max, None)}"
    ax.text(0.0, 1.02, subtitle, transform=ax.transAxes, ha='left', va='bottom', fontsize=11, color='#c9d1d9')

    # Top-right: compact stats card (kept intentionally short so it doesn't clutter long streams).
    stats_lines = [
        f"时长  {seconds_to_hms(duration_seconds, None)}",
        f"弹幕  {total_messages:,}",
        f"均值  {mean_per_min:,.0f}/分",
    ]
    if captain_total > 0:
        stats_lines.append(f"上舰  {captain_total:,}")
    if np.isfinite(peak_x) and np.isfinite(peak_y):
        stats_lines.append(f"峰值  {int(peak_y):,}/分 @ {seconds_to_hms(peak_x, None)}")

    stats_text = "\n".join(stats_lines)
    ax.text(
        0.985,
        0.98,
        stats_text,
        transform=ax.transAxes,
        ha='right',
        va='top',
        fontsize=11,
        linespacing=1.4,
        bbox={
            'boxstyle': 'round,pad=0.5',
            'fc': '#0f172a',
            'ec': '#223044',
            'alpha': 0.92,
        },
        zorder=6,
    )

    ax.margins(x=0)

    # Captain overlay: captain_bucket_counts is already aggregated by minute bucket.
    # We place markers directly on the smoothed curve for the same bucket timestamp.
    if captain_bucket_counts:
        duration_minutes = (x_max - x_min) / 60.0

        if duration_minutes <= 60:
            aggregation_minutes = 5.0
        elif duration_minutes <= 720:
            aggregation_minutes = 5.0 + (duration_minutes - 60) / (720 - 60) * (15.0 - 5.0)
        else:
            aggregation_minutes = 15.0 + (duration_minutes - 720) / (2880 - 720) * (30.0 - 15.0)

        aggregation_seconds = aggregation_minutes * 60.0

        xs: List[float] = []
        ys: List[float] = []
        counts: List[int] = []

        aggregated_captain_counts: Dict[float, int] = {}
        for bucket_seconds, count in captain_bucket_counts.items():
            if count <= 0:
                continue
            minute_bucket = float(int(float(bucket_seconds) // _GRAPH_BUCKET_SECONDS) * _GRAPH_BUCKET_SECONDS)
            agg_bucket = float(int(minute_bucket // aggregation_seconds) * aggregation_seconds)
            aggregated_captain_counts[agg_bucket] = aggregated_captain_counts.get(agg_bucket, 0) + int(count)

        x_to_index: Dict[float, int] = {float(x): i for i, x in enumerate(x_axis_data)}
        for bucket_x, count in aggregated_captain_counts.items():
            closest_x = min(x_axis_data, key=lambda x: abs(float(x) - bucket_x))
            idx = x_to_index.get(float(closest_x))
            if idx is None:
                continue
            y_val = float(smoothed_y_axis_data[idx])
            xs.append(float(closest_x))
            ys.append(y_val)
            counts.append(int(count))

        if xs:
            max_count = max(counts) if counts else 1
            sizes = [int(30 + min(60.0, (c / max_count) * 80.0)) for c in counts]

            y_min, y_max = ax.get_ylim()
            stem_height = max((y_max - y_min) * 0.06, 8.0)
            stems_y0 = [max(y_min, y - stem_height) for y in ys]

            ax.vlines(xs, stems_y0, ys, colors='#93c5fd', linewidth=1.2, alpha=0.35, zorder=6)

            halo_sizes = [int(s * 1.9) for s in sizes]
            ax.scatter(
                xs,
                ys,
                s=halo_sizes,
                marker='D',
                color='#60a5fa',
                alpha=0.14,
                linewidths=0,
                zorder=6,
            )

            ax.scatter(
                xs,
                ys,
                s=sizes,
                marker='D',
                color='#60a5fa',
                edgecolors='#e6edf3',
                linewidths=1.0,
                alpha=0.95,
                zorder=7,
            )

            for x, y, c in zip(xs, ys, counts):
                if c <= 0:
                    continue
                ax.annotate(
                    f"舰长×{int(c)}",
                    xy=(x, y),
                    xytext=(0, 11),
                    textcoords='offset points',
                    ha='center',
                    va='bottom',
                    fontsize=10,
                    color='#bfdbfe',
                    bbox={
                        'boxstyle': 'round,pad=0.25',
                        'fc': '#0f172a',
                        'ec': '#1f2a3a',
                        'alpha': 0.78,
                    },
                    zorder=8,
                )

            legend_label = '舰长（总数）'
            ax.scatter([], [], s=40, marker='D', color='#60a5fa', edgecolors='#e6edf3', linewidths=1.0,
                       label=legend_label)
            ax.legend(
                loc='lower left',
                frameon=True,
                facecolor='#0f172a',
                edgecolor='#223044',
                framealpha=0.9,
                fontsize=10,
            )

    file_name = f'{getcwd()}/data/live/{int(time.time())}_danmaku.png'
    fig.savefig(file_name, bbox_inches='tight', pad_inches=0.25)
    plt.close(fig)

    return file_name


def _get_sorted_hotspot_time_to_frequency(stream_time_frequency: List[float] | Dict[float, int]) -> Tuple[
    List[float],
    List[int],
]:
    if isinstance(stream_time_frequency, dict):
        return _bucket_counts_to_series(stream_time_frequency)

    hotspot_analyzation_result = hotspot_analyzation(stream_time_frequency, intervals=60)
    return _bucket_counts_to_series(hotspot_analyzation_result)


def get_sorted_timestamp_hotspot(
        stream_time_frequency: List[float] | Dict[float, int],
        intervals: int = 60,
) -> List[str]:
    if isinstance(stream_time_frequency, dict):
        hotspot_analyzation_result = stream_time_frequency
    else:
        hotspot_analyzation_result = hotspot_analyzation(stream_time_frequency, intervals)

    sorted_result = sorted(
        hotspot_analyzation_result.items(),
        key=lambda x: (x[1], -x[0]),
        reverse=True,
    )
    if len(sorted_result) > TOP_TIMESTAMP_LIMIT:
        sorted_result = sorted_result[:TOP_TIMESTAMP_LIMIT]

    hotspot_timestamp_data = [float(x[0]) for x in sorted_result]
    return [construct_timestamp_string(x) for x in hotspot_timestamp_data]


async def run_listening() -> None:
    clients = [BLiveClient(int(single_room_id), session=session) for single_room_id in TEST_ROOM_IDS]
    for client in clients:
        client.set_handler(handler)
        client.start()

    try:
        await asyncio.gather(*(client.join() for client in clients), handler.stop_event.wait())
    finally:
        await asyncio.gather(*(client.stop_and_close() for client in clients))


if __name__ == '__main__':
    try:
        logger.success('Successfully started danmaku monitoring.')
        asyncio.run(main())
    finally:
        print()
