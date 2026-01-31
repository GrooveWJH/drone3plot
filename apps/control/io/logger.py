"""
数据记录器模块
支持自定义CSV字段的参数化记录器
"""
import csv
import os
from datetime import datetime
from rich.console import Console


# 预定义的字段集合
FIELD_SETS = {
    'plane_yaw': [
        'timestamp', 'target_x', 'target_y', 'target_yaw',
        'current_x', 'current_y', 'current_yaw',
        'error_x', 'error_y', 'error_yaw', 'distance',
        'roll_offset', 'pitch_offset', 'yaw_offset',
        'roll_absolute', 'pitch_absolute', 'yaw_absolute', 'waypoint_index',
        # PID components for X (Pitch)
        'x_pid_p', 'x_pid_i', 'x_pid_d',
        # PID components for Y (Roll)
        'y_pid_p', 'y_pid_i', 'y_pid_d',
        # PID components for Yaw
        'yaw_pid_p', 'yaw_pid_i', 'yaw_pid_d'
    ],
    'yaw_only': [
        'timestamp', 'target_yaw', 'current_yaw', 'error_yaw',
        'yaw_offset', 'yaw_absolute', 'target_index',
        # PID components for Yaw
        'yaw_pid_p', 'yaw_pid_i', 'yaw_pid_d'
    ],
    'plane_only': [
        'timestamp', 'target_x', 'target_y',
        'current_x', 'current_y',
        'error_x', 'error_y', 'distance',
        'roll_offset', 'pitch_offset',
        'roll_absolute', 'pitch_absolute', 'waypoint_index',
        # PID components for X (Pitch)
        'x_pid_p', 'x_pid_i', 'x_pid_d',
        # PID components for Y (Roll)
        'y_pid_p', 'y_pid_i', 'y_pid_d'
    ],
    'vertical': [
        'timestamp', 'target_height', 'current_height', 'error_height',
        'throttle_offset', 'throttle_absolute',
        # PID components for Height
        'height_pid_p', 'height_pid_i', 'height_pid_d'
    ],
}


class DataLogger:
    """参数化PID控制数据记录器"""

    def __init__(self, enabled=True, base_dir=None, field_set='plane_yaw',
                 csv_name='control_data.csv', subdir=''):
        """
        初始化数据记录器

        Args:
            enabled: 是否启用记录
            base_dir: 基础目录
            field_set: 字段集合名称('plane_yaw', 'yaw_only')或自定义字段列表
            csv_name: CSV文件名
            subdir: 子目录名称(如'yaw')
        """
        self.enabled = enabled
        self.csv_file = None
        self.csv_writer = None
        self.log_dir = None
        self.fields = self._get_fields(field_set)
        self.csv_name = csv_name
        self.subdir = subdir

        if self.enabled:
            self._setup_logging(base_dir)

    def _get_fields(self, field_set):
        """获取字段列表"""
        if isinstance(field_set, str):
            return FIELD_SETS.get(field_set, FIELD_SETS['plane_yaw'])
        elif isinstance(field_set, list):
            return field_set
        else:
            return FIELD_SETS['plane_yaw']

    def _setup_logging(self, base_dir=None):
        """创建数据目录和CSV文件"""
        # 确定基础目录
        if base_dir is None:
            import sys
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            if os.path.basename(script_dir) == 'control':
                script_dir = os.path.dirname(script_dir)
            base_dir = os.path.join(script_dir, 'data')

        # 添加子目录
        if self.subdir:
            base_dir = os.path.join(base_dir, self.subdir)

        os.makedirs(base_dir, exist_ok=True)

        # 创建时间戳目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_dir = os.path.join(base_dir, timestamp)
        os.makedirs(self.log_dir, exist_ok=True)

        # 创建CSV文件
        csv_path = os.path.join(self.log_dir, self.csv_name)
        self.csv_file = open(csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # 写入CSV头部
        self.csv_writer.writerow(self.fields)
        self.csv_file.flush()

    def log(self, **kwargs):
        """记录一条数据（使用关键字参数）"""
        if not self.enabled or self.csv_writer is None:
            return

        # 按字段顺序提取数据
        row = [kwargs.get(field, '') for field in self.fields]
        self.csv_writer.writerow(row)

        # 每10条刷新一次
        timestamp = kwargs.get('timestamp', 0)
        if timestamp and int(timestamp * 50) % 10 == 0:
            self.csv_file.flush()

    def log_plane_yaw(self, timestamp, target_x, target_y, target_yaw,
                      current_x, current_y, current_yaw,
                      error_x, error_y, error_yaw, distance,
                      roll_offset, pitch_offset, yaw_offset,
                      roll_absolute, pitch_absolute, yaw_absolute, waypoint_index):
        """记录平面+Yaw控制数据（向后兼容）"""
        self.log(
            timestamp=timestamp, target_x=target_x, target_y=target_y, target_yaw=target_yaw,
            current_x=current_x, current_y=current_y, current_yaw=current_yaw,
            error_x=error_x, error_y=error_y, error_yaw=error_yaw, distance=distance,
            roll_offset=roll_offset, pitch_offset=pitch_offset, yaw_offset=yaw_offset,
            roll_absolute=roll_absolute, pitch_absolute=pitch_absolute,
            yaw_absolute=yaw_absolute, waypoint_index=waypoint_index
        )

    def log_yaw_only(self, timestamp, target_yaw, current_yaw, error_yaw,
                     yaw_offset, yaw_absolute, target_index):
        """记录Yaw单独控制数据"""
        self.log(
            timestamp=timestamp, target_yaw=target_yaw, current_yaw=current_yaw,
            error_yaw=error_yaw, yaw_offset=yaw_offset, yaw_absolute=yaw_absolute,
            target_index=target_index
        )

    def close(self):
        """关闭日志文件并创建latest副本"""
        if self.csv_file:
            self.csv_file.close()
            console = Console()
            console.print(f"[green]✓ 数据已保存至: {self.log_dir}[/green]")

            # 创建"latest"副本（覆盖旧的latest）
            if self.log_dir:
                import shutil
                base_dir = os.path.dirname(self.log_dir)
                latest_dir = os.path.join(base_dir, 'latest')

                # 如果latest已存在，先删除
                if os.path.exists(latest_dir):
                    shutil.rmtree(latest_dir)

                # 复制整个目录到latest
                shutil.copytree(self.log_dir, latest_dir)
                console.print(f"[green]✓ 最新记录已复制至: {latest_dir}[/green]")

    def get_log_dir(self):
        """获取日志目录路径"""
        return self.log_dir
