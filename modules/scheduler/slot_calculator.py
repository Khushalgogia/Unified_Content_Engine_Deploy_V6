"""
Slot Calculator — "Next Available Slot" Algorithm
Auto-fills posting times at 09:00, 14:00, 19:00 IST.
"""

from datetime import datetime, timedelta
import pytz

# ─── Configuration ────────────────────────────────────────────────────────────

IST = pytz.timezone("Asia/Kolkata")

# 3 daily posting slots (hour, minute) in IST
SLOT_TIMES = [
    (9, 0),    # 09:00 AM
    (14, 0),   # 02:00 PM
    (19, 0),   # 07:00 PM
]


# ─── Core Algorithm ──────────────────────────────────────────────────────────

def get_next_slot(last_scheduled_time=None):
    """
    Calculate the next available posting slot.

    Logic:
        - If no pending posts: find the next upcoming slot today.
          If all today's slots are past, start tomorrow at first slot.
        - If queue exists: take the last scheduled time and move
          to the next logical slot.

    Args:
        last_scheduled_time: datetime (timezone-aware) of the most recent
                             scheduled post, or None if queue is empty.

    Returns:
        datetime: timezone-aware datetime in IST for the next slot.
    """
    now = datetime.now(IST)

    if last_scheduled_time is None:
        # ── Queue is empty: find the next upcoming slot today ──
        for hour, minute in SLOT_TIMES:
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate > now:
                return candidate

        # All today's slots are past → first slot tomorrow
        tomorrow = now + timedelta(days=1)
        first_hour, first_minute = SLOT_TIMES[0]
        return tomorrow.replace(
            hour=first_hour, minute=first_minute, second=0, microsecond=0
        )

    else:
        # ── Queue exists: find the next slot after last_scheduled_time ──
        # Make sure it's IST-aware
        if last_scheduled_time.tzinfo is None:
            last_scheduled_time = IST.localize(last_scheduled_time)
        else:
            last_scheduled_time = last_scheduled_time.astimezone(IST)

        last_date = last_scheduled_time.date()
        last_hour = last_scheduled_time.hour
        last_minute = last_scheduled_time.minute

        # Find the next slot on the same day
        for hour, minute in SLOT_TIMES:
            if (hour, minute) > (last_hour, last_minute):
                candidate = IST.localize(
                    datetime.combine(last_date, datetime.min.time()).replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                )
                return candidate

        # All slots on that day are used → first slot next day
        next_day = last_date + timedelta(days=1)
        first_hour, first_minute = SLOT_TIMES[0]
        return IST.localize(
            datetime.combine(next_day, datetime.min.time()).replace(
                hour=first_hour, minute=first_minute, second=0, microsecond=0
            )
        )


def format_slot_display(slot_time):
    """Format a slot time for user-friendly display."""
    return slot_time.strftime("%a, %b %d at %I:%M %p IST")
