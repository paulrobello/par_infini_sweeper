def format_duration(elapsed: int) -> str:
    """Format elapsed time in seconds to HH:MM:SS"""
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{str(hours).rjust(2, '0')}:{str(minutes).rjust(2, '0')}:{str(seconds).rjust(2, '0')}"
