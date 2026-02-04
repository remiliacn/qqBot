from Services.rate_limiter import RateLimitConfig

SETU_RATE_LIMIT = RateLimitConfig(
    user_time=20.0,
    user_count=1.0,
    group_time=20,
    group_count=2,
    apply_group_limit=True,
    progressive=True,
    multiplier=1.5,
    max_period=60.0 * 5,
    reset_after=60.0 * 2
)

XP_CHECK_RATE_LIMIT = SETU_RATE_LIMIT

WORDCLOUD_RATE_LIMIT = RateLimitConfig(
    user_time=60.0,
    user_count=1.0,
    group_time=40,
    group_count=1,
    apply_group_limit=True
)
