from Services.rate_limiter import RateLimitConfig

SETU_RATE_LIMIT = RateLimitConfig(
    user_time_period=20.0,
    user_function_limit=1.0,
    allowlist_can_bypass=True,
    group_time_period=20,
    group_function_limit=1,
    apply_group_limit=True,
    enable_progressive_limit=True,
    progressive_multiplier=1.5,
    progressive_max_period=60.0 * 5,
    progressive_reset_after=60.0 * 2
)

XP_CHECK_RATE_LIMIT = SETU_RATE_LIMIT

WORDCLOUD_RATE_LIMIT = RateLimitConfig(
    user_time_period=60.0,
    user_function_limit=1.0,
    allowlist_can_bypass=True,
    group_time_period=60,
    group_function_limit=1,
    apply_group_limit=True
)
