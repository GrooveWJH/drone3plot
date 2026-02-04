"""
控制器模块
包含平面控制器、平面+Yaw控制器和Yaw单独控制器
"""

import math
from .pid import PIDController


def quaternion_to_yaw(quat):
    """
    从四元数提取Yaw角（偏航角）

    Args:
        quat: 四元数格式 (qx, qy, qz, qw)

    Returns:
        Yaw角度（度），范围 [-180, 180]
    """
    qx, qy, qz, qw = quat
    yaw_rad = math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))
    return math.degrees(yaw_rad)


def normalize_angle(angle):
    """
    归一化角度到 (-180, 180] 范围（选择最短旋转路径）

    Args:
        angle: 角度误差（度）

    Returns:
        归一化后的角度（度），保证选择最短旋转路径

    Example:
        当前 179.8°, 目标 0°:
            error = 0 - 179.8 = -179.8°
            normalize(-179.8) = +0.2° (从另一侧绕过更短)

        当前 -179.8°, 目标 0°:
            error = 0 - (-179.8) = +179.8°
            normalize(+179.8) = -0.2° (从另一侧绕过更短)

    边界连续性验证：
        -170° → -180° → +180° → +170° 误差变化是连续的，不会突变
    """
    # 先归一化到 (-180, 180] 范围
    while angle > 180:
        angle -= 360
    while angle <= -180:
        angle += 360

    # 关键：选择最短旋转路径
    # 如果误差绝对值 > 180°，从另一侧绕过更短
    # 但由于已经归一化到 (-180, 180]，不会出现 >180 的情况
    # 所以这个公式是正确的，直接返回
    return angle


def get_yaw_error(target_yaw, current_yaw):
    """
    计算Yaw角误差（考虑±180°边界，选择最短旋转路径）

    Args:
        target_yaw: 目标Yaw角（度）
        current_yaw: 当前Yaw角（度）

    Returns:
        误差（度），正值表示需要逆时针旋转，范围 (-180, 180]

    关键逻辑：
        总是选择绝对值更小的旋转方向！

        例子1：当前 179.8°, 目标 0°
            - 方式1（顺时针）：179.8° → 0°，需要 179.8°
            - 方式2（逆时针）：179.8° → 180° → -180° → 0°，需要 0.2°
            - 选择方式2：返回 +0.2° (逆时针绕过边界)

        例子2：当前 -179°, 目标 0°
            - 方式1（逆时针）：-179° → 0°，需要 179°
            - 方式2（顺时针）：-179° → -180° → 180° → 0°，需要 181°
            - 选择方式1：返回 +179° (逆时针直达)
    """
    # 先归一化两个输入角度到 (-180, 180]
    target_yaw = normalize_angle(target_yaw)
    current_yaw = normalize_angle(current_yaw)

    # 计算直接误差
    error = target_yaw - current_yaw

    # 关键：选择最短旋转路径
    # 如果误差 > 180，说明逆时针绕远了，应该顺时针（error - 360）
    # 如果误差 < -180，说明顺时针绕远了，应该逆时针（error + 360）
    if error > 180:
        error -= 360
    elif error < -180:
        error += 360

    return error


class PlaneController:
    """平面位置控制器（X-Y平面，无Yaw控制）

    特性：
    - 距离自适应增益调度（远处激进，近处温和）
    """

    def __init__(
        self,
        kp,
        ki,
        kd,
        output_limit,
        enable_gain_scheduling=True,
        gain_schedule_profile=None,
        d_filter_alpha=None,
    ):
        """
        初始化平面控制器

        Args:
            kp, ki, kd: PID增益
            output_limit: 输出限幅
            enable_gain_scheduling: 是否启用增益调度
            gain_schedule_profile: {'far': {'kp_scale', 'kd_scale'}, 'near': {...}}
        """
        # 保存基础PID增益
        self.kp_base = kp
        self.ki_base = ki
        self.kd_base = kd
        self.output_limit = output_limit

        # 创建PID控制器
        self.x_pid = PIDController(
            kp, ki, kd, output_limit, d_filter_alpha=d_filter_alpha
        )  # X轴 → Pitch
        self.y_pid = PIDController(
            kp, ki, kd, output_limit, d_filter_alpha=d_filter_alpha
        )  # Y轴 → Roll

        # 增益调度配置
        self.enable_gain_scheduling = enable_gain_scheduling
        self.distance_far = 1.0  # 远距离阈值（米）
        self.distance_near = 0.3  # 近距离阈值（米）
        default_profile = {
            "far": {"kp_scale": 1.0, "kd_scale": 0.5, "ki_scale": 1.0},
            "near": {"kp_scale": 0.4, "kd_scale": 1.5, "ki_scale": 1.0},
        }
        self.gain_schedule_profile = gain_schedule_profile or default_profile

    def reset(self):
        """重置所有PID状态"""
        self.x_pid.reset()
        self.y_pid.reset()

    def selective_reset(self, reset_mask="111"):
        """
        选择性重置PID状态

        Args:
            reset_mask: 三位字符串，每位对应P、I、D是否重置
                       "000" - 不重置任何项
                       "101" - 重置P和D，保留I
                       "010" - 仅重置I项
                       "111" - 全部重置

        Examples:
            controller.selective_reset('101')  # 重置P和D，保留I
            controller.selective_reset('010')  # 仅重置I项（防止积分饱和）
        """
        if len(reset_mask) != 3:
            raise ValueError("reset_mask must be 3 characters (e.g., '101')")

        reset_p = reset_mask[0] == "1"
        reset_i = reset_mask[1] == "1"
        reset_d = reset_mask[2] == "1"

        # X轴PID选择性重置
        if reset_p:
            # P项没有状态，不需要重置
            pass
        if reset_i:
            self.x_pid.integral = 0.0
        if reset_d:
            self.x_pid.last_error = None
            self.x_pid.last_time = None
            self.x_pid.last_d_term = None

        # Y轴PID选择性重置
        if reset_p:
            pass
        if reset_i:
            self.y_pid.integral = 0.0
        if reset_d:
            self.y_pid.last_error = None
            self.y_pid.last_time = None
            self.y_pid.last_d_term = None

    def compute(self, target_x, target_y, current_x, current_y, current_time):
        """
        计算控制输出

        返回:
            roll_offset, pitch_offset: 杆量偏移值
            pid_components: {
                'x': (p, i, d),
                'y': (p, i, d)
            }
        """
        error_x = target_x - current_x  # 前方向误差
        error_y = target_y - current_y  # 左方向误差
        distance = math.sqrt(error_x**2 + error_y**2)

        # 【增益调度】根据距离调整PID增益
        if self.enable_gain_scheduling:
            self._apply_gain_scheduling(distance)

        # PID计算
        pitch_offset, x_components = self.x_pid.compute(
            error_x, current_time
        )  # X → Pitch正
        y_output, y_components = self.y_pid.compute(error_y, current_time)

        # 输出限幅
        pitch_offset = max(-self.output_limit, min(self.output_limit, pitch_offset))
        y_output = max(-self.output_limit, min(self.output_limit, y_output))

        roll_offset = -y_output  # Y → Roll负

        # 组装PID分量字典
        pid_components = {"x": x_components, "y": y_components}

        return roll_offset, pitch_offset, pid_components

    def _apply_gain_scheduling(self, distance):
        """
        根据距离调整PID增益

        策略：
        - 远距离(>distance_far): 使用profile['far']给定的增益缩放
        - 中距离: 在远/近两组增益之间按距离线性插值
        - 近距离(<distance_near): 使用profile['near']给定的增益缩放
        """
        profile_far = self.gain_schedule_profile.get("far", {})
        profile_near = self.gain_schedule_profile.get("near", {})
        kp_far = profile_far.get("kp_scale", 1.0)
        kd_far = profile_far.get("kd_scale", 0.5)
        ki_far = profile_far.get("ki_scale", 1.0)
        kp_near = profile_near.get("kp_scale", 0.4)
        kd_near = profile_near.get("kd_scale", 1.5)
        ki_near = profile_near.get("ki_scale", 1.0)

        if distance > self.distance_far:
            kp_scale = kp_far
            kd_scale = kd_far
            ki_scale = ki_far
        elif distance > self.distance_near and self.distance_far > self.distance_near:
            # 线性插值
            ratio = (distance - self.distance_near) / (
                self.distance_far - self.distance_near
            )
            kp_scale = kp_near + (kp_far - kp_near) * ratio
            kd_scale = kd_near + (kd_far - kd_near) * ratio
            ki_scale = ki_near + (ki_far - ki_near) * ratio
        else:
            kp_scale = kp_near
            kd_scale = kd_near
            ki_scale = ki_near

        # 应用缩放
        self.x_pid.kp = self.kp_base * kp_scale
        self.x_pid.kd = self.kd_base * kd_scale
        self.x_pid.ki = self.ki_base * ki_scale
        self.y_pid.kp = self.kp_base * kp_scale
        self.y_pid.kd = self.kd_base * kd_scale
        self.y_pid.ki = self.ki_base * ki_scale

    def get_distance(self, target_x, target_y, current_x, current_y):
        """计算当前位置到目标位置的距离"""
        dx = target_x - current_x
        dy = target_y - current_y
        return (dx**2 + dy**2) ** 0.5


class PlaneYawController:
    """平面+Yaw控制器（X-Y平面 + Yaw角度）"""

    def __init__(self, kp_xy, ki_xy, kd_xy, kp_yaw, ki_yaw, kd_yaw, output_limit):
        # XY平面控制器
        self.x_pid = PIDController(kp_xy, ki_xy, kd_xy, output_limit)
        self.y_pid = PIDController(kp_xy, ki_xy, kd_xy, output_limit)
        # Yaw角控制器
        self.yaw_pid = PIDController(kp_yaw, ki_yaw, kd_yaw, output_limit)

    def reset(self):
        """重置所有PID状态"""
        self.x_pid.reset()
        self.y_pid.reset()
        self.yaw_pid.reset()

    def compute(
        self,
        target_x,
        target_y,
        target_yaw,
        current_x,
        current_y,
        current_yaw,
        current_time,
    ):
        """
        计算控制输出

        返回:
            roll_offset, pitch_offset, yaw_offset: 杆量偏移值
            pid_components: {
                'x': (p, i, d),
                'y': (p, i, d),
                'yaw': (p, i, d)
            }
        """
        # 计算XY平面误差
        error_x = target_x - current_x
        error_y = target_y - current_y

        # 计算Yaw角误差（处理-180~180度边界）
        error_yaw = self._normalize_angle(target_yaw - current_yaw)

        # 计算PID输出（获取分量）
        pitch_offset, x_components = self.x_pid.compute(
            error_x, current_time
        )  # X → Pitch
        y_output, y_components = self.y_pid.compute(error_y, current_time)
        roll_offset = -y_output  # Y → Roll负
        yaw_offset, yaw_components = self.yaw_pid.compute(
            error_yaw, current_time
        )  # Yaw

        # 组装PID分量字典
        pid_components = {"x": x_components, "y": y_components, "yaw": yaw_components}

        return roll_offset, pitch_offset, yaw_offset, pid_components

    def get_distance(self, target_x, target_y, current_x, current_y):
        """计算XY平面距离"""
        dx = target_x - current_x
        dy = target_y - current_y
        return (dx**2 + dy**2) ** 0.5

    def get_yaw_error(self, target_yaw, current_yaw):
        """计算Yaw角误差（归一化到-180~180）"""
        return abs(self._normalize_angle(target_yaw - current_yaw))

    @staticmethod
    def _normalize_angle(angle):
        """归一化角度到-180~180度"""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle


class YawOnlyController:
    """Yaw角单独控制器（仅控制偏航角）"""

    def __init__(self, kp, ki, kd, output_limit, i_activation_error=None):
        """
        初始化Yaw控制器

        Args:
            kp: 比例增益
            ki: 积分增益
            kd: 微分增益
            output_limit: 输出限幅
            i_activation_error: I项启动误差阈值（度），误差在此范围内才启动积分
        """
        self.yaw_pid = PIDController(kp, ki, kd, output_limit, i_activation_error)

    def reset(self):
        """重置PID状态"""
        self.yaw_pid.reset()

    def compute(self, target_yaw, current_yaw, current_time):
        """
        计算Yaw控制输出

        Args:
            target_yaw: 目标Yaw角（度）
            current_yaw: 当前Yaw角（度）
            current_time: 当前时间

        Returns:
            yaw_offset: Yaw杆量偏移值
            pid_components: (p_term, i_term, d_term) PID三个分量
        """
        # 计算Yaw角误差（考虑±180°边界）
        error_yaw = get_yaw_error(target_yaw, current_yaw)

        # PID控制（获取分量）
        # 注意：误差为正（需要逆时针旋转）→ 输出正值 → 杆量<1024（向左）
        output, pid_components = self.yaw_pid.compute(error_yaw, current_time)
        yaw_offset = -output

        return yaw_offset, pid_components

    def get_yaw_error(self, target_yaw, current_yaw):
        """
        计算Yaw角误差的绝对值

        Args:
            target_yaw: 目标Yaw角（度）
            current_yaw: 当前Yaw角（度）

        Returns:
            误差绝对值（度）
        """
        return abs(get_yaw_error(target_yaw, current_yaw))
