import math

def reward_function(params):
    '''
    Reward function encouraging the car to stay near the center,
    drive smoothly, maintain reasonable speed, align with track direction,
    plus milestone bonuses to push for full laps.
    '''

    # Read input parameters (only standard DeepRacer keys)
    track_width = params['track_width']
    distance_from_center = params['distance_from_center']
    speed = params['speed']
    steering_angle = abs(params['steering_angle'])
    is_offtrack = params['is_offtrack']
    is_crashed = params['is_crashed']
    progress = params['progress']
    steps = params['steps']
    heading = params['heading']
    waypoints = params['waypoints']
    closest_waypoints = params['closest_waypoints']

    # Base reward
    reward = 1.0

    # 1) Center line reward
    marker_1 = 0.1 * track_width
    marker_2 = 0.25 * track_width
    marker_3 = 0.5 * track_width

    if distance_from_center <= marker_1:
        reward *= 1.2
    elif distance_from_center <= marker_2:
        reward *= 0.8
    elif distance_from_center <= marker_3:
        reward *= 0.4
    else:
        reward *= 1e-3

    # 2) Encourage reasonable speed
    if distance_from_center < marker_2 and speed > 2.0:
        reward *= 1.5
    elif speed < 1.0:
        reward *= 0.5

    # 3) Discourage harsh steering
    if steering_angle > 20:
        reward *= 0.7

    # 4) Heading alignment bonus
    next_point = waypoints[closest_waypoints[1]]
    prev_point = waypoints[closest_waypoints[0]]
    track_direction = math.degrees(math.atan2(next_point[1] - prev_point[1],
                                              next_point[0] - prev_point[0]))

    direction_diff = abs(track_direction - heading)
    if direction_diff > 180:
        direction_diff = 360 - direction_diff

    if direction_diff < 10:
        reward *= 1.2
    elif direction_diff < 30:
        reward *= 0.9
    else:
        reward *= 0.7

    # 5) Smooth progress bonus (efficiency)
    if steps > 0:
        reward += (progress / steps) * 5.0

    # 6) Progress completion bonus (shaping)
    reward += progress / 100.0

    # Milestone bonuses to encourage finishing laps
    # (kept small since this applies at many steps)
    if progress >= 100:
        reward += 3.0
    elif progress >= 75:
        reward += 1.2
    elif progress >= 50:
        reward += 0.8
    elif progress >= 25:
        reward += 0.4

    # 7) Hard penalties
    if is_offtrack or is_crashed:
        reward = 1e-3

    return float(reward)
