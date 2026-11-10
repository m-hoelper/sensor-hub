from sensor_hub.schemas import MeasurementIn, ThresholdsOut, NotificationOut
from datetime import datetime, timedelta
def run_window_recommendation(m: MeasurementIn, s: ThresholdsOut, n: NotificationOut | None, now: datetime) -> str | None:
    if n is not None and now - n.created_at <= timedelta(minutes=s.cooldown_min):
        return None

    state = n.new_state if n is not None else 'CLOSED'

    if state == 'CLOSED' and (m.humidity_pct >= s.humidity_open_pct or (m.co2_ppm >= s.co2_open_ppm and m.humidity_pct > s.humidity_min_pct) or m.co2_ppm >= s.co2_max_ppm):
        return 'OPEN_RECOMMENDED'
    
    if state == 'OPEN_RECOMMENDED' and ((m.humidity_pct <= s.humidity_close_pct and m.co2_ppm <= s.co2_close_ppm) or (m.humidity_pct <= s.humidity_min_pct and m.co2_ppm < s.co2_max_ppm)):
        return 'CLOSED'

    return None


def build_message(new_state: str, m: MeasurementIn, s: ThresholdsOut) -> str:
    
    values = f"CO2 {m.co2_ppm} ppm, humidity {m.humidity_pct:.0f} %"

    if new_state == 'OPEN_RECOMMENDED':
        if m.humidity_pct >= s.humidity_open_pct:
            return f"Open the window: too humid, mold risk ({values}, limit {s.humidity_open_pct:.0f} %)"
        if m.humidity_pct <= s.humidity_min_pct:
            return f"Open the window briefly: CO2 very high although the air is dry ({values}, max {s.co2_max_ppm} ppm)"
        return f"Open the window: CO2 too high ({values}, limit {s.co2_open_ppm} ppm)"

    if m.humidity_pct <= s.humidity_min_pct:
        return f"Close the window: too dry ({values}, min {s.humidity_min_pct:.0f} %)"
    return f"Close the window: air is fresh again ({values})"
