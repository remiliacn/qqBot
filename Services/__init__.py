from .discord_service import DiscordService
from .live_notification import LiveNotification, BilibiliDynamicNotifcation
from .rate_limiter import RateLimiter
from .twitch_service import TwitchService, TwitchClippingService

global_rate_limiter = RateLimiter()
live_notification = LiveNotification()
twitch_notification = TwitchService()
dynamic_notification = BilibiliDynamicNotifcation()
twitch_clipping = TwitchClippingService()
discord_notification = DiscordService()
