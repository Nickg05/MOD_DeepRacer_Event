import math

SPEED_MIN = 1.0
SPEED_MAX = 3.0
track_turns = []

def find_next_segment(next_waypoint):
    for j in range(len(track_turns)):
        turn_start, turn_amount, seg_length = track_turns[j]
        if turn_start >= next_waypoint:
            return j, turn_start, float(turn_amount), float(seg_length)
    # wrap around to first turn
    s, a, l = track_turns[0]
    return 0, s, float(a), float(l)

def get_waypoint_distance(waypoints, idx1, idx2) -> float:
    n_wp = len(waypoints)
    dist = 0.0
    i = idx1
    while i != idx2:
        p1 = waypoints[i]
        p2 = waypoints[(i + 1) % n_wp]
        dist += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        i = (i + 1) % n_wp
    return dist

def calculate_speed_target(waypoints, next_waypoint: int) -> float:
    next_seg_idx, next_start, next_amount, next_length = find_next_segment(next_waypoint)
    curr_start, curr_amount, curr_length = track_turns[(next_seg_idx - 1) % len(track_turns)]

    APPROACH_WINDOW = 1.0  # meters of look-ahead for blending
    TURN_EASY = 20.0       # deg of heading change considered an easy turn
    TURN_HARD = 80.0      # deg considered a hard turn
    L_REF = 1.25           # reference segment length

    # Convert angle thresholds to curvature thresholds (deg per meter)
    CURV_EASY = TURN_EASY / L_REF
    CURV_HARD = TURN_HARD / L_REF

    def severity(angle_abs: float, seg_length: float) -> float:
        curvature = angle_abs / max(seg_length, 1e-6)  # deg/m

        if curvature <= CURV_EASY:
            s = 0.0
        elif curvature >= CURV_HARD:
            s = 1.0
        else:
            s = (curvature - CURV_EASY) / (CURV_HARD - CURV_EASY)
        return s ** 1.2

    def speed_for(angle_abs: float, seg_length: float) -> float:
        sev = severity(angle_abs, seg_length)
        return SPEED_MAX - (SPEED_MAX - SPEED_MIN) * sev

    curr_speed = speed_for(abs(curr_amount), curr_length)
    next_speed = speed_for(abs(next_amount), next_length)

    # Distance to the next segment start
    dist_to_boundary = get_waypoint_distance(waypoints, next_waypoint, next_start)
    # Blend factor: 0 far away -> 1 at boundary
    alpha = 1.0 - min(1.0, max(0.0, dist_to_boundary / max(1e-6, APPROACH_WINDOW)))

    target = (1.0 - alpha) * curr_speed + alpha * next_speed
    return float(max(min(target, SPEED_MAX), SPEED_MIN))

def create_track_segments(waypoints, straight_threshold=2.0, min_turn_angle=10, min_seg_length=0.7):
    def normalize_angle(a: float) -> float:
        return (a + 180.0) % 360.0 - 180.0
    def _first_equals_lst(waypoints, tol: float = 1e-6) -> bool:
        try:
            p0 = waypoints[0]
            p1 = waypoints[-1]
            return (abs(p0[0] - p1[0]) <= tol) and (abs(p0[1] - p1[1]) <= tol)
        except Exception:
            return False

    turns = []
    n_wp = len(waypoints)
    turn_type = 0 # 0=straight, 1=left, -1=right
    turn_start_idx = 0
    turn_angle = 0.0

    if _first_equals_lst(waypoints): n_wp -= 1

    curr_idx = 0
    while not turns or curr_idx != turns[0][0] + 1:
        curr_pt = waypoints[curr_idx]
        next_pt = waypoints[(curr_idx + 1) % n_wp]
        future_pt = waypoints[(curr_idx + 2) % n_wp]

        seg_heading = normalize_angle(
            math.degrees(math.atan2(next_pt[1] - curr_pt[1], next_pt[0] - curr_pt[0]))
        )
        future_heading = normalize_angle(
            math.degrees(math.atan2(future_pt[1] - next_pt[1], future_pt[0] - next_pt[0]))
        )

        delta = normalize_angle(future_heading - seg_heading) # Heading difference
        going_straight = abs(delta) <= straight_threshold
        if going_straight: delta = 0.0
        curr_turn_type = 0 if going_straight else (1 if delta > 0 else -1)

        if turn_type != curr_turn_type:
            # Turn type changed - end previous segment
            length = get_waypoint_distance(waypoints, turn_start_idx, curr_idx)

            if abs(turn_angle) >= min_turn_angle:
                turns.append((turn_start_idx, turn_angle, length))
            elif turns and turns[-1][1] != 0.0:
                turns.append((turn_start_idx, 0.0, length))
            elif turns:  # Extend previous straight
                start, angle, _ = turns[-1]
                turns[-1] = (start, angle, get_waypoint_distance(waypoints, start, curr_idx))

            # Start new segment
            turn_type = curr_turn_type
            turn_start_idx = curr_idx
            turn_angle = delta
        else:
            # Continue current segment
            turn_angle += delta
        curr_idx = (curr_idx + 1) % n_wp

    # remove short segments (merge with the neighbor whose angle is most similar)
    i = 0
    while i < len(turns):
        start, angle, length = turns[i]
        if length < min_seg_length and len(turns) > 1:
            seg_before = (i - 1) % len(turns)
            seg_after = (i + 1) % len(turns)

            diff_before = abs(turns[seg_before][1] - angle)
            diff_after = abs(turns[seg_after][1] - angle)

            if diff_before <= diff_after:
                b_start, b_angle, b_length = turns[seg_before]
                turns[seg_before] = (b_start, b_angle + angle, b_length + length)
                turns.pop(i)
                # After pop, adjust index: if we merged backward and i > 0, stay at i-1
                if i > 0: i -= 1
                else: i = 0
                continue
            else:
                a_start, a_angle, a_length = turns[seg_after]
                turns[seg_after] = (start, a_angle + angle, a_length + length)
                turns.pop(i)
                continue
        i += 1

    return turns

def reward_function(params):
    reward = 0.0
    
    track_width = params['track_width']
    distance_from_center = params['distance_from_center']
    all_wheels_on_track = params['all_wheels_on_track']
    progress = params['progress']
    waypoints = params['waypoints']
    closest_waypoints = params['closest_waypoints']
    heading = params['heading']
    speed = params['speed']
    steps = params['steps']
    steering = abs(params['steering_angle'])

    global track_turns
    if not track_turns:
        track_turns = create_track_segments(waypoints)
    
    marker_1 = 0.13 * track_width
    marker_2 = 0.25 * track_width
    marker_3 = 0.48 * track_width

    if all_wheels_on_track == False:
        return 1e-6
        
    if distance_from_center <= marker_1:
        reward += 0.6
    elif distance_from_center <= marker_2:
        reward += 0.4
    elif distance_from_center <= marker_3:
        reward += 0.15
    
    speed_target = calculate_speed_target(waypoints, closest_waypoints[1])
    speed_diff = abs(speed - speed_target)

    next_point = waypoints[closest_waypoints[1]]
    prev_point = waypoints[closest_waypoints[0]]
    
    track_direction = math.atan2(
        next_point[1] - prev_point[1],
        next_point[0] - prev_point[0]
    )
    track_direction = math.degrees(track_direction)
    
    direction_diff = abs(track_direction - heading)
    if direction_diff > 180:
        direction_diff = 360 - direction_diff
    
    if direction_diff < 8.0 and speed_diff < 0.2:
        reward += 0.5
    elif direction_diff < 15.0 and speed_diff < 0.6:
        reward += 0.2
    else:
        reward *= 0.85
    
    if speed > 2.4 and steering > 10:
        reward *= 0.7
    else:
        reward += 0.1

    return float(reward)