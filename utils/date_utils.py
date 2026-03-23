from datetime import datetime

def is_holiday(dt):
    """Kiểm tra xem một ngày có phải là ngày lễ lớn trong năm 2026 hay không."""
    fixed_holidays = [(1, 1), (30, 4), (1, 5), (2, 9)]
    specific_2026_holidays = [
        datetime(2026, 2, 16), datetime(2026, 2, 17), datetime(2026, 2, 18),
        datetime(2026, 2, 19), datetime(2026, 2, 20), datetime(2026, 2, 21),
        datetime(2026, 2, 22), datetime(2026, 4, 26) 
    ]
    if (dt.day, dt.month) in fixed_holidays:
        return True
    if dt.date() in [d.date() for d in specific_2026_holidays]:
        return True
    return False