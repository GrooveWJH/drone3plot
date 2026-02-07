#!/bin/bash
source /opt/ros/noetic/setup.bash
source /home/nvidia/sunray_map/devel/setup.bash

# 1. 启动 ROS Core
roscore &
echo "Waiting for ROS Master..."
until rostopic list ; do sleep 1; done

# 2. 【关键】先启动 Fast-LIO (消费者)
# 注意：不需要 --wait，因为 roscore 已经有了
# Fast-LIO 启动后会因为没有 topic 而阻塞在 callback 等待中，这是正常的
roslaunch fast_lio mapping_mid360.launch &
FASTLIO_PID=$!
echo "Fast-LIO started (PID: $FASTLIO_PID), initializing..."

# 3. 给 Fast-LIO 充足的初始化时间 (比如 5-10秒)
# 这一步是为了确保 Fast-LIO 完成了内存分配、KD-Tree 构建等耗时操作
# 此时缓冲区是空的，因为还没有人发布数据
sleep 8.0 

# 4. 【最后】才启动 Livox 驱动 (生产者)
# 驱动一启动，发出的第一帧数据就会被已经准备好的 Fast-LIO 立刻处理
roslaunch livox_ros_driver2 msg_MID360.launch &
LIVOX_PID=$!
echo "Livox Driver started. Mapping begins now."

# 5. 挂起脚本
wait $FASTLIO_PID
