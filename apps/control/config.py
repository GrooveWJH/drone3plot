"""
配置参数模块
所有可调参数集中在此文件
"""

# ========== 连接配置 ==========
GATEWAY_SN = '9N9CN2B00121JN'

MQTT_CONFIG = {
    'host': '192.168.20.186',
    'port': 1883,
    'username': 'admin',
    'password': 'yundrone123',
}

# ========== DRC 控制配置 ==========
DRC_USER_ID = "pilot_0"
DRC_USER_CALLSIGN = "控制算法测试"
DRC_OSD_FREQUENCY = 30
DRC_HSI_FREQUENCY = 10
DRC_HEARTBEAT_INTERVAL = 1.0

# ========== SLAM 数据源 ==========
SLAM_POSE_TOPIC = 'slam/position'
SLAM_YAW_TOPIC = 'slam/yaw'

# ========== 轨迹飞行配置 ==========
TRAJECTORY_FILE = "data/trajectory/trajectory.json"
TRAJECTORY_REQUIRE_CONFIRM = True  # 每个航点完成后是否需要手动确认

# ========== 数据记录配置 ==========
ENABLE_DATA_LOGGING = True   # 是否启用数据记录

# ========== 核心控制参数（平面/垂直/旋转分离）==========
CONTROL_FREQUENCY = 50       # 控制频率（Hz）
TOLERANCE_XY = 0.05          # XY平面到达阈值（米）
TOLERANCE_YAW = 2.0          # Yaw角到达阈值（度）
MAX_STICK_OUTPUT = 330       # XY平面最大杆量输出限幅
MAX_YAW_STICK_OUTPUT = 440   # Yaw最大杆量输出限幅
NEUTRAL = 1024               # 杆量中值
YAW_ZERO_THRESHOLD_DEG = 1.0  # Yaw 小于该阈值时视为 0

# PID增益（分离控制仍复用）
KP_XY = 150.0   
# I 可以稍微大点，因为我们限制了它只在最后时刻生效，起效要快
KI_XY = 40.0    # [增加] 原来是 25。因为作用范围小了，力度要大。
# D 必须大幅增加，这是唯一的刹车来源
KD_XY = 110.0    # [大幅增加] 原来是 65。我们需要强力阻尼来对抗惯性。

KP_YAW = 30.0   # Yaw角比例增益
KI_YAW = 5.0    # Yaw角积分增益
KD_YAW = 1.0    # Yaw角微分增益

# ========== 平面运动配置（XY） ==========
WAYPOINTS = [
    (0, 0),
    (-1, 1),
]

PLANE_ARRIVAL_STABLE_TIME = 1.0  # 到达稳定时间（秒）
PLANE_AUTO_NEXT_WAYPOINT = False  # 到达航点后自动前往下一个航点（无需按Enter）

PLANE_USE_RANDOM_WAYPOINTS = True  # 使用随机生成的航点（替代WAYPOINTS）
PLANE_RANDOM_BOUND = 1.25           # 随机航点边界（米），对应 2.5m * 2.5m 平面
PLANE_RANDOM_NEAR_DISTANCE = 0.25   # 近点距离下限（米）
PLANE_RANDOM_NEAR_DISTANCE_MAX = 0.30  # 近点距离上限（米）
PLANE_RANDOM_FAR_DISTANCE = 1.0     # 远点距离下限（米）

PLANE_GAIN_SCHEDULING_CONFIG = {
    'enabled': True,
    
    # [关键修改 1] 放宽过渡带
    'distance_far': 0.6,    # 拉开一点距离，让参数过渡更平滑
    # 让飞机在 0.25m 处就开始承认"我到了"，从而启用积分来消除那最后的过冲。
    # 这能解决"回弹慢"的问题。
    'distance_near': 0.25,  

    'profile': {
        'far': {
            # [关键修改 2] 远端降 P，增 D
            # 远距离咱们不追求极速（P稍微降点），追求的是"稳如老狗"的刹车感（D大幅提升）。
            'kp_scale': 0.85,  # 稍微限制一下最高速，减少惯性
            'kd_scale': 1.6,   # [重刹车] 远距离 D 增益 1.6倍！相当于 KD=176！
            'ki_scale': 0.0,   # 保持积分分离，这是成功的关键
        },
        'near': {
            'kp_scale': 1.0,
            'kd_scale': 1.0,
            'ki_scale': 1.0,   # 进圈即开启 KI=40 的强力修正
        }
    }
}

# D项滤波（指数平滑），0-1，数值越小越平滑
PLANE_D_FILTER_ALPHA = 0.2

# ========== 垂直运动配置（Z） ==========
VERTICAL_HEIGHT_SOURCE = "slam"  # "slam" 或 "relative"
VERTICAL_TARGET_HEIGHT = 1.0     # 目标高度（米）
VERTICAL_SLAM_ZERO_AT_START = True  # 使用初始SLAM高度作为0点
VERTICAL_KP = 400.0
VERTICAL_KI = 30.0
VERTICAL_KD = 50.0
VERTICAL_I_ACTIVATION_ERROR = 0.05   # I项启动阈值（米），None 表示不限
VERTICAL_TOLERANCE = 0.08           # 到达阈值（米）
VERTICAL_MAX_THROTTLE_OUTPUT = 330  # 最大升降杆量偏移
VERTICAL_CONTROL_FREQUENCY = 20     # 控制频率（Hz）
VERTICAL_ARRIVAL_STABLE_TIME = 1.0  # 到达稳定时间（秒）

# ========== 旋转运动配置（Yaw） ==========
TARGET_YAWS = [
    0,      # 正北（初始朝向）
    90,     # 正东（逆时针90°）
    180,    # 正南（逆时针180°）
    -90,    # 正西（顺时针90°，等价于逆时针270°）
]

YAW_ARRIVAL_STABLE_TIME = 0.5  # 到达稳定时间（秒）
YAW_I_ACTIVATION_ERROR = 10    # I项启动阈值（度）
YAW_DEADZONE = 0               # Yaw杆量死区（小于此值输出为0）

AUTO_NEXT_TARGET = True        # 到达目标后自动前往下一个目标（无需按Enter）
USE_RANDOM_ANGLES = True       # 使用随机生成的目标角度（替代TARGET_YAWS）
RANDOM_ANGLE_MIN_DIFF = 45     # 随机角度与当前目标的最小角度差（度）
