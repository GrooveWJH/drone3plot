#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
import subprocess
import threading
import os
import signal
import math
import paho.mqtt.client as mqtt

# ==========================================
#        核心配置 (Hyperparameters)
# ==========================================

# --- 1. MQTT 连接配置 ---
MQTT_BROKER = "192.168.10.90"
MQTT_PORT = 1883
MQTT_USER = "admin"
MQTT_PASS = "yundrone123"

# --- 2. MQTT 话题配置 ---
MQTT_TOPIC_CMD_START = "slam/start"      # 接收启动/停止指令
MQTT_TOPIC_POSE      = "slam/position"   # 发送位置
MQTT_TOPIC_YAW       = "slam/yaw"        # 发送航向角
MQTT_TOPIC_FREQ      = "slam/frequency"  # 发送频率统计
MQTT_TOPIC_STATUS    = "slam/status"     # 发送系统状态心跳

# --- 3. ROS 与 脚本配置 ---
ROS_TOPIC_ODOM = "/sunray/odometry"
LAUNCH_SCRIPT  = "/home/nvidia/sunray_map/headless_start.sh"

# --- 4. 逻辑控制超参数 ---
STATUS_REPORT_RATE = 0.5   # 状态上报频率 (Hz)
MAX_MQTT_RATE = 30.0       # 数据发送限流 (Hz)
TIMEOUT_SEC = 5.0          # 数据超时判定 (秒)
STARTUP_TIMEOUT_SEC = 30   # 启动超时判定 (秒)

# ==========================================

# --- 全局变量 ---
client = None
ros_process = None  
is_ros_active = False 

# 延迟加载 ROS 库
rospy = None
Odometry = None
euler_from_quaternion = None

# 桥接变量
last_ros_msg_time = 0.0
last_mqtt_pub_time = 0.0
is_timeout = False
stat_ros_count = 0
stat_mqtt_count = 0
last_stat_time = 0.0

# ==========================================
#  辅助函数：发送 Null 数据清洗前端
# ==========================================
def send_null_data():
    """
    发送显式的 Null 数据，用于清洗前端显示。
    告诉前端：现在没有有效的位置信息。
    """
    ts = int(time.time() * 1000)
    
    # 1. 清空位置
    try:
        client.publish(MQTT_TOPIC_POSE, json.dumps({
            "timestamp": ts, 
            "x": None, "y": None, "z": None
        }), qos=0)
        
        # 2. 清空航向
        client.publish(MQTT_TOPIC_YAW, json.dumps({
            "timestamp": ts, 
            "yaw": None
        }), qos=0)
        
        # 3. 清空频率
        client.publish(MQTT_TOPIC_FREQ, json.dumps({
            "timestamp": ts, 
            "rostopic": 0.0, "mqtt": 0.0
        }), qos=0)
    except:
        pass
    
    print("[Manager] 已发送数据清洗包 (Null Data)")

# ==========================================
#  MQTT 回调函数
# ==========================================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Manager] MQTT 连接成功")
        client.subscribe(MQTT_TOPIC_CMD_START)
        
        # 遗嘱：意外断电发 offline
        will_payload = json.dumps({"timestamp": 0, "status": "offline"})
        client.will_set(MQTT_TOPIC_STATUS, will_payload, qos=0, retain=True)
        
        # 刚连上时，先清洗一次数据，防止前端显示历史残留
        send_null_data()
        
        # 发送初始状态 Idle
        client.publish(MQTT_TOPIC_STATUS, json.dumps({
            "timestamp": int(time.time()*1000), 
            "status": "idle"
        }), qos=0, retain=True)
    else:
        print(f"[Manager] MQTT 连接失败: {rc}")

def on_message(client, userdata, msg):
    """
    处理控制指令: {"start": true} 或 {"start": false}
    """
    if msg.topic == MQTT_TOPIC_CMD_START:
        try:
            payload = json.loads(msg.payload.decode())
            
            # 过滤掉自己发的 ACK
            if "result" in payload: return

            target_state = payload.get("start")

            # === 情况 1: 启动 ===
            if target_state is True:
                if is_ros_active:
                    send_ack("info", "System is already running")
                else:
                    send_ack("ack", "Command received, starting system...")
                    threading.Thread(target=launch_ros_system).start()
            
            # === 情况 2: 停止 ===
            elif target_state is False:
                if is_ros_active:
                    send_ack("ack", "Command received, stopping system...")
                    threading.Thread(target=stop_ros_system).start()
                else:
                    send_ack("info", "System is already idle")

        except Exception as e:
            print(f"指令错误: {e}")

def send_ack(result_type, msg_content):
    try:
        ack = {
            "timestamp": int(time.time()*1000),
            "result": result_type,
            "message": msg_content
        }
        client.publish(MQTT_TOPIC_CMD_START, json.dumps(ack), qos=0)
    except: pass

# ==========================================
#  系统控制逻辑
# ==========================================

def stop_ros_system():
    """
    停止逻辑：标记状态 -> 杀进程 -> 发 Null 数据 -> 更新状态
    """
    global is_ros_active, ros_process
    print("[Manager] 正在执行停止程序...")
    
    # 1. 立即停止数据转发
    is_ros_active = False

    # 2. 暴力清理所有相关节点
    # 增加 roslaunch 防止自动重启，增加 rosmaster 确保环境重置
    cmd = "killall -9 livox_ros_driver2_node fastlio_mapping roscore rosmaster roslaunch"
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL)
    
    # 3. 清理 Shell 进程对象
    if ros_process:
        try:
            ros_process.terminate()
            ros_process.wait(timeout=1)
        except: pass
        ros_process = None

    # 4. 发送 Null 数据覆盖最后一帧有效位置
    send_null_data()

    # 5. 更新状态为 idle
    try:
        status_payload = {
            "timestamp": int(time.time()*1000),
            "status": "idle"
        }
        client.publish(MQTT_TOPIC_STATUS, json.dumps(status_payload), qos=0, retain=True)
    except: pass
    
    print("[Manager] 系统已完全停止")

def launch_ros_system():
    global is_ros_active, ros_process
    
    if is_ros_active: return

    try:
        # 启动 Shell 脚本
        ros_process = subprocess.Popen(["/bin/bash", LAUNCH_SCRIPT])
        is_ros_active = True
    except Exception as e:
        print(f"启动失败: {e}")
        is_ros_active = False
        return

    # 动态加载 ROS 库 (如果还没加载过)
    global rospy, Odometry, euler_from_quaternion
    if rospy is None:
        try:
            import rospy as _rospy
            from nav_msgs.msg import Odometry as _Odometry
            from tf.transformations import euler_from_quaternion as _efq
            rospy = _rospy
            Odometry = _Odometry
            euler_from_quaternion = _efq
        except ImportError:
            print("[Error] 无法加载 ROS 库，请检查环境")
            stop_ros_system()
            return

    # 循环等待 roscore 上线
    print("[Manager] 等待 ROS Master...")
    timeout_cnt = 0
    while is_ros_active: 
        try:
            rospy.get_master().getSystemState()
            print("[Manager] ROS Master 上线，初始化桥接...")
            start_ros_bridge()
            break
        except:
            if not is_ros_active: break # 如果等待期间被用户停止
            time.sleep(1)
            timeout_cnt += 1
            if timeout_cnt > STARTUP_TIMEOUT_SEC: 
                print("启动超时")
                stop_ros_system()
                break

def start_ros_bridge():
    global last_ros_msg_time, last_stat_time
    
    try:
        # anonymous=True 很重要，防止节点名冲突
        rospy.init_node('odom_mqtt_bridge', anonymous=True, disable_signals=True)
    except rospy.exceptions.ROSException:
        pass 

    rospy.Subscriber(ROS_TOPIC_ODOM, Odometry, odom_callback)
    
    last_ros_msg_time = time.time()
    last_stat_time = time.time()
    print("[Bridge] 开始转发数据")

def odom_callback(msg):
    if not is_ros_active: return # 停止后不再处理

    global last_ros_msg_time, is_timeout, last_mqtt_pub_time, stat_ros_count, stat_mqtt_count
    
    current_time = time.time()
    last_ros_msg_time = current_time
    stat_ros_count += 1
    
    # 如果之前是超时状态，现在恢复了，标记解除
    if is_timeout: is_timeout = False

    # 限流控制
    if (current_time - last_mqtt_pub_time) < (1.0 / MAX_MQTT_RATE):
        return 

    last_mqtt_pub_time = current_time
    stat_mqtt_count += 1

    # 解析数据
    timestamp_ms = int(msg.header.stamp.to_sec() * 1000)
    pos = msg.pose.pose.position
    ori = msg.pose.pose.orientation
    try:
        (_, _, yaw_rad) = euler_from_quaternion([ori.x, ori.y, ori.z, ori.w])
        yaw_deg = math.degrees(yaw_rad)
    except:
        yaw_deg = 0.0

    # 发送数据
    try:
        client.publish(MQTT_TOPIC_POSE, json.dumps({
            "timestamp": timestamp_ms, "x": round(pos.x, 3), "y": round(pos.y, 3), "z": round(pos.z, 3)
        }), qos=0)
        client.publish(MQTT_TOPIC_YAW, json.dumps({
            "timestamp": timestamp_ms, "yaw": round(yaw_deg, 3)
        }), qos=0)
    except: pass

# ==========================================
#  主循环与监控
# ==========================================

def check_system_health():
    global is_ros_active, ros_process, is_timeout
    
    # 1. 进程守护：如果脚本意外退出
    if is_ros_active and ros_process:
        if ros_process.poll() is not None:
            print("[Monitor] 启动脚本已退出，重置为 Idle")
            stop_ros_system() # 调用完整的停止逻辑清理残局
            return
    
    # 2. 数据流超时检测
    if is_ros_active:
        if time.time() - last_ros_msg_time > TIMEOUT_SEC:
            if not is_timeout: # 仅在状态切换时打印
                print("[Monitor] 数据流中断 (Stalled)")
                # 超时也发一次 Null，提示前端数据断了
                send_null_data()
            is_timeout = True
        else:
            is_timeout = False

    # 3. 发送系统状态心跳
    status_str = "running" if is_ros_active else "idle"
    if is_ros_active and is_timeout:
        status_str = "stalled" 

    try:
        status_payload = {
            "timestamp": int(time.time()*1000),
            "status": status_str
        }
        client.publish(MQTT_TOPIC_STATUS, json.dumps(status_payload), qos=0, retain=True)
    except: pass

    # 4. 发送频率统计
    if is_ros_active and not is_timeout:
        send_stats()

def send_stats():
    global stat_ros_count, stat_mqtt_count, last_stat_time
    dt = time.time() - last_stat_time
    if dt <= 0: return
    
    try:
        stats = {
            "timestamp": int(time.time()*1000),
            "rostopic": round(stat_ros_count / dt, 1),
            "mqtt": round(stat_mqtt_count / dt, 1)
        }
        client.publish(MQTT_TOPIC_FREQ, json.dumps(stats), qos=0)
    except: pass
    
    stat_ros_count = 0
    stat_mqtt_count = 0
    last_stat_time = time.time()

if __name__ == '__main__':
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print("[System] 服务启动...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start() 
        
        while True:
            check_system_health()
            time.sleep(1.0 / STATUS_REPORT_RATE)
            
    except KeyboardInterrupt:
        print("\n[System] 用户终止程序")
        stop_ros_system() 
        client.loop_stop()
        client.disconnect()
