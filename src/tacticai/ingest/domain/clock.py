"""Match clocks. engine_time_s is physical time (speeds, rates); match_time_s is for display only."""
FRAME_S = 0.1
MATCH_DURATION_FACTOR = 0.027 * 0.2 + 0.05
STEPS_PER_MATCH = 3000
SECOND_HALF_STEP = 1500


def engine_time_s(frame_index):
    return round(frame_index * FRAME_S, 1)


def match_time_s(step):
    return round(step * FRAME_S / MATCH_DURATION_FACTOR, 2)
