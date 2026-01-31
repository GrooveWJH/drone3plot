# 平面位置控制 - 高级控制特性说明

本文档说明 `main_plane.py` 中实现的高级控制特性，用于解决网络延迟和机体惯性导致的超调问题。

## 问题背景

### 原有问题
- **输入**：位置反馈（来自 SLAM）
- **输出**：摇杆量（发送给DJI）
- **挑战**：
  1. 网络延迟（~500ms）
  2. 机体惯性（无速度/加速度反馈）
  3. 多级控制延迟（你的PID → 摇杆 → DJI内环PID → 电机）

### 症状
- 无人机经常飞过目标点才开始减速
- 提高D项会导致运动过于缓慢
- 难以在速度和精度之间找到平衡

---

## 解决方案1：增益调度（Gain Scheduling）

### 原理
根据距离目标的远近，自动调整PID增益：
- **远距离 (>1.0m)**：高P低D → 快速接近
- **中距离 (0.3~1.0m)**：平衡P和D → 渐进减速
- **近距离 (<0.3m)**：低P高D → 精确停止

### 配置参数（在 `config.py` 中）
```python
PLANE_ENABLE_GAIN_SCHEDULING = True   # 启用/禁用增益调度
PLANE_DISTANCE_FAR = 1.0              # 远距离阈值（米）
PLANE_DISTANCE_NEAR = 0.3             # 近距离阈值（米）
```

### 增益缩放策略
| 距离范围 | P增益缩放 | D增益缩放 | 效果 |
|---------|----------|----------|------|
| > 1.0m  | 1.0x     | 0.5x     | 快速接近 |
| 0.3~1.0m| 0.4~1.0x | 0.5~1.5x | 线性过渡 |
| < 0.3m  | 0.4x     | 1.5x     | 精确停止 |

### 实现细节（controller.py:154-179）
```python
def _apply_gain_scheduling(self, distance):
    if distance > self.distance_far:
        kp_scale = 1.0
        kd_scale = 0.5
    elif distance > self.distance_near:
        # 线性插值
        ratio = (distance - self.distance_near) / (self.distance_far - self.distance_near)
        kp_scale = 0.4 + 0.6 * ratio
        kd_scale = 1.5 - 0.5 * ratio
    else:
        kp_scale = 0.4
        kd_scale = 1.5

    # 应用缩放
    self.x_pid.kp = self.kp_base * kp_scale
    self.x_pid.kd = self.kd_base * kd_scale
```

---

## 解决方案2：Smith预测器（Smith Predictor）

### 原理
补偿系统延迟的经典控制方法：
1. **记录历史指令**：存储每个时刻的控制输出
2. **延迟回溯**：取出500ms前发送的指令
3. **预测当前效果**：用简单模型估算该延迟指令对当前速度的影响
4. **提前补偿**：从当前指令中减去预测的延迟效应

### 配置参数（在 `config.py` 中）
```python
PLANE_ENABLE_SMITH_PREDICTOR = True   # 启用/禁用Smith预测器
PLANE_ESTIMATED_DELAY = 0.5           # 估计延迟（秒）
PLANE_RESPONSE_GAIN = 0.0015          # 杆量→速度响应增益
```

### 参数调优
| 参数 | 作用 | 调整建议 |
|------|------|---------|
| `PLANE_ESTIMATED_DELAY` | 延迟时间 | 测量实际网络延迟+机体响应时间 |
| `PLANE_RESPONSE_GAIN` | 响应模型 | 如果补偿不足增大，过度补偿则减小 |

### 实现细节（controller.py:181-210）
```python
def _apply_smith_predictor(self, command, buffer, current_time, axis):
    # 存储当前指令
    buffer.append((current_time, command))

    # 获取延迟时间前的历史指令
    delayed_time = current_time - self.estimated_delay
    delayed_command = self._get_delayed_command(buffer, delayed_time)

    # 预测该延迟指令造成的当前速度
    predicted_velocity = delayed_command * self.response_gain

    # 补偿：从当前指令减去预测速度的影响
    compensation = predicted_velocity * 150
    compensated_command = command - compensation

    return compensated_command
```

---

## 使用指南

### 快速启用
两个特性默认都已启用，无需额外配置：
```bash
python -m apps.control.main_plane
```

启动时会显示：
```
┌─ 平面位置PID控制器 - 重构版本 ─┐
│ ...                            │
│ 控制特性: 增益调度 (远:1.0m, 近:0.3m) | Smith预测器 (延迟:500ms) │
└────────────────────────────────┘
```

### 禁用某个特性
在 `config.py` 中修改：
```python
PLANE_ENABLE_GAIN_SCHEDULING = False   # 禁用增益调度
PLANE_ENABLE_SMITH_PREDICTOR = False   # 禁用Smith预测器
```

### 调优建议

#### 1. 测量实际延迟
运行简单测试：
1. 记录发送控制指令的时间戳
2. 观察无人机开始响应的时间
3. 计算延迟 = 响应时间 - 发送时间
4. 将延迟值设置为 `PLANE_ESTIMATED_DELAY`

#### 2. 调整增益调度阈值
如果无人机在特定距离仍然超调：
```python
PLANE_DISTANCE_FAR = 1.5   # 增大，提前开始减速
PLANE_DISTANCE_NEAR = 0.5  # 增大，更早进入精确模式
```

#### 3. 调整Smith预测器响应增益
观察实际飞行：
- **症状：仍然超调** → 增大 `PLANE_RESPONSE_GAIN`（增强补偿）
- **症状：提前减速过度** → 减小 `PLANE_RESPONSE_GAIN`（减弱补偿）
- **症状：震荡** → 检查 `PLANE_ESTIMATED_DELAY` 是否准确

---

## 实验对比

### 测试场景
- 目标点：从 (0, 0) 到 (2, 0)
- 初始PID：Kp=300, Ki=30, Kd=100

### 结果对比
| 配置 | 超调距离 | 到达时间 | 稳定时间 |
|------|---------|---------|---------|
| 基础PID | 0.5m | 8s | 15s |
| + 增益调度 | 0.2m | 6s | 10s |
| + Smith预测器 | 0.05m | 5s | 6s |
| 两者都启用 | **0.03m** | **4.5s** | **5s** |

*注：以上数据为示例，实际效果取决于你的系统参数。*

---

## 技术细节

### 增益调度的数学表达
```
距离 d:
  if d > d_far:
    kp = kp_base × 1.0
    kd = kd_base × 0.5
  elif d > d_near:
    ratio = (d - d_near) / (d_far - d_near)
    kp = kp_base × (0.4 + 0.6 × ratio)
    kd = kd_base × (1.5 - 0.5 × ratio)
  else:
    kp = kp_base × 0.4
    kd = kd_base × 1.5
```

### Smith预测器的数学表达
```
指令缓冲: B = [(t₁, u₁), (t₂, u₂), ..., (tₙ, uₙ)]
当前时间: t_now
延迟时间: τ

延迟指令: u_delayed = B[t_now - τ]  (线性插值)
预测速度: v_pred = u_delayed × k_response
补偿量:   c = v_pred × 150
最终输出: u_out = u_pid - c
```

---

## 常见问题

### Q1: 为什么不用卡尔曼滤波？
**A:** 卡尔曼滤波主要处理**测量噪声**，而你的问题是**控制延迟**。SLAM 数据已经足够稳定，增加复杂度不值得。

### Q2: 为什么补偿系数是150？
**A:** 这是经验值，根据 `predicted_velocity × 150` 将速度转换为杆量偏移。需要根据实际飞行调整。

### Q3: 能否只用其中一个特性？
**A:** 可以。增益调度和Smith预测器是独立的，可以单独启用/禁用。

### Q4: 如何知道延迟补偿是否起作用？
**A:** 观察数据日志中的PID输出：
- 启用前：接近目标时PID输出仍然很大
- 启用后：接近目标时PID输出提前减小

---

## 进一步优化

如果以上方法仍不够理想，可以考虑：

1. **系统辨识（System Identification）**
   - 收集阶跃响应数据
   - 拟合传递函数模型
   - 计算最优PID增益

2. **速度前馈（Velocity Feedforward）**
   - 从位置差分估算速度
   - 添加速度阻尼项

3. **模型预测控制（MPC）**
   - 适用于更复杂的场景
   - 需要更多计算资源

---

## 参考资料

- **Smith Predictor**: Smith, O. J. M. (1957). "Closer Control of Loops with Dead Time"
- **Gain Scheduling**: Rugh, W. J., & Shamma, J. S. (2000). "Research on Gain Scheduling"
- **PID Tuning**: Åström, K. J., & Hägglund, T. (2006). "Advanced PID Control"
