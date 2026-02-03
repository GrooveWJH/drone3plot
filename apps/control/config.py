"""控制与运行参数。"""

# ========== 基础连接 ==========
GATEWAY_SN = "9N9CN2B00121JN"

MQTT_CONFIG = {
    "host": "192.168.10.90",
    "port": 1883,
    "username": "admin",
    "password": "yundrone123",
}

# ========== DRC 控制 ==========
DRC_USER_ID = "pilot_0"
DRC_USER_CALLSIGN = "控制算法测试"
DRC_OSD_FREQUENCY = 30
DRC_HSI_FREQUENCY = 10
DRC_HEARTBEAT_INTERVAL = 1.0

# ========== SLAM 数据源 ==========
SLAM_POSE_TOPIC = "slam/position"
SLAM_YAW_TOPIC = "slam/yaw"

# ========== 数据记录 ==========
ENABLE_DATA_LOGGING = True

# ========== 控制核心 ==========
CONTROL_FREQUENCY = 50  # Hz
TOLERANCE_XY = 0.1  # m
TOLERANCE_YAW = 2.0  # deg
MAX_STICK_OUTPUT = 220
MAX_YAW_STICK_OUTPUT = 440
NEUTRAL = 1024
YAW_ZERO_THRESHOLD_DEG = 1.0

# 平面 PID
KP_XY = 300
KI_XY = 40.0
KD_XY = 110.0

# Yaw PID
KP_YAW = 30.0
KI_YAW = 5.0
KD_YAW = 1.0

# ========== 平面运动（XY） ==========
WAYPOINTS = [(0, 0), (-1, 1)]

PLANE_ARRIVAL_STABLE_TIME = 1.0  # 到达稳定时间（秒）
PLANE_AUTO_NEXT_WAYPOINT = True  # 到达航点后自动前往下一个航点（无需按Enter）

PLANE_USE_RANDOM_WAYPOINTS = True
PLANE_RANDOM_BOUND = 0.90
PLANE_RANDOM_NEAR_DISTANCE = 0.25
PLANE_RANDOM_NEAR_DISTANCE_MAX = 0.30
PLANE_RANDOM_FAR_DISTANCE = 0.5
PLANE_RANDOM_ONLY_FAR = True

PLANE_GAIN_SCHEDULING_CONFIG = {
    "enabled": True,
    "distance_far": 0.6,
    "distance_near": 0.25,
    "profile": {
        "far": {
            "kp_scale": 0.85,
            "kd_scale": 1.6,
            "ki_scale": 0.8,
        },
        "near": {
            "kp_scale": 1.0,
            "kd_scale": 1.0,
            "ki_scale": 1.0,
        },
    },
}

# D 项滤波（0-1，越小越平滑）
PLANE_D_FILTER_ALPHA = 0.2

# ========== 平面控制：APPROACH -> BRAKE -> SETTLE ==========
PLANE_BRAKE_DISTANCE = TOLERANCE_XY * 1.3
PLANE_BRAKE_HOLD_TIME = 1.0
PLANE_BRAKE_MAX_COUNT = 1
PLANE_SETTLE_DISTANCE = TOLERANCE_XY
PLANE_SETTLE_TIMEOUT = 10
PLANE_SETTLE_KP = KP_XY * 10
PLANE_SETTLE_KI = 10.0
PLANE_SETTLE_KD = KD_XY

# ========== 垂直运动（Z） ==========
VERTICAL_HEIGHT_SOURCE = "slam"  # "slam" or "relative"
VERTICAL_TARGET_HEIGHT = 1.0
VERTICAL_SLAM_ZERO_AT_START = True
VERTICAL_KP = 400.0
VERTICAL_KI = 30.0
VERTICAL_KD = 50.0
VERTICAL_I_ACTIVATION_ERROR = 0.05
VERTICAL_TOLERANCE = 0.08
VERTICAL_MAX_THROTTLE_OUTPUT = 330
VERTICAL_CONTROL_FREQUENCY = 20
VERTICAL_ARRIVAL_STABLE_TIME = 1.0

# ========== 旋转运动（Yaw） ==========
TARGET_YAWS = [
    0,
    90,
    180,
    -90,
]

YAW_ARRIVAL_STABLE_TIME = 0.5
YAW_I_ACTIVATION_ERROR = 10
YAW_DEADZONE = 0

AUTO_NEXT_TARGET = True
USE_RANDOM_ANGLES = True
RANDOM_ANGLE_MIN_DIFF = 45

# ========== 轨迹飞行 ==========
TRAJECTORY_FILE = "data/trajectory/trajectory.json"
TRAJECTORY_REQUIRE_CONFIRM = True
