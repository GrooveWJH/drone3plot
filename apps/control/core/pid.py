"""
PID控制器基础类
"""


class PIDController:
    """单轴PID控制器"""

    def __init__(
        self,
        kp,
        ki,
        kd,
        output_limit=None,
        i_activation_threshold=None,
        d_filter_alpha=None,
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit
        self.i_activation_threshold = i_activation_threshold  # I项启动阈值
        self.d_filter_alpha = d_filter_alpha  # D项滤波系数（0-1），None=关闭

        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None
        self.last_d_term = None

    def reset(self):
        """重置PID状态"""
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None
        self.last_d_term = None

    def compute(self, error, current_time):
        """
        计算PID输出

        Returns:
            output: PID总输出
            components: (p_term, i_term, d_term) 三个分量
        """
        dt = 0.0 if self.last_time is None else current_time - self.last_time

        # P项
        p_term = self.kp * error

        # D项
        raw_d = self.kd * ((error - self.last_error) / dt if dt > 0 else 0.0)
        if self.d_filter_alpha is None or self.last_d_term is None:
            d_term = raw_d
        else:
            alpha = self.d_filter_alpha
            d_term = alpha * raw_d + (1 - alpha) * self.last_d_term
        self.last_d_term = d_term

        # I项（带积分限幅、启动区间与抗饱和）
        if dt > 0:
            if self.i_activation_threshold is None or abs(error) <= self.i_activation_threshold:
                if self.output_limit and self.ki > 0:
                    output_no_i = p_term + d_term
                    candidate_integral = self.integral + error * dt
                    output_with_i = output_no_i + self.ki * candidate_integral
                    is_saturated = abs(output_with_i) >= self.output_limit
                    same_direction = error * output_with_i > 0
                    if not (is_saturated and same_direction):
                        self.integral = candidate_integral
                else:
                    self.integral += error * dt

                if self.output_limit and self.ki > 0:
                    max_integral = self.output_limit / self.ki
                    self.integral = max(-max_integral, min(max_integral, self.integral))
            else:
                self.integral = 0.0

        i_term = self.ki * self.integral

        # 总输出（带限幅）
        output = p_term + i_term + d_term
        if self.output_limit:
            output = max(-self.output_limit, min(self.output_limit, output))

        # 更新状态
        self.last_error = error
        self.last_time = current_time

        return output, (p_term, i_term, d_term)
