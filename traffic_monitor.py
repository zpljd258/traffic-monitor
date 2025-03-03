# traffic_monitor.py
import time
import datetime
import requests
import os
import json
import socket
import logging
import sys
from logging.handlers import RotatingFileHandler

# --- 从环境变量读取配置 ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TRAFFIC_DIRECTION = os.environ.get("TRAFFIC_DIRECTION", "outbound")  # 流量方向，默认为出站
MONTHLY_TRAFFIC_GB = int(os.environ.get("MONTHLY_TRAFFIC_GB", 1024))  # 每月流量上限，默认为 1024 GB
RESET_DAY = int(os.environ.get("RESET_DAY", 1))  # 流量重置日，默认为每月 1 号
THRESHOLDS_STR = os.environ.get("THRESHOLDS", "80,90,95")  # 流量阈值，默认为 80%, 90%, 95%
THRESHOLDS = sorted([float(t) / 100 for t in THRESHOLDS_STR.split(",")])  # 将阈值转换为小数并排序
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", 1))  # 检查间隔，默认为 1 秒
NETWORK_INTERFACE = os.environ.get("NETWORK_INTERFACE", "eth0")  # 网络接口名称，默认为 eth0
REPORT_INTERVAL_DAYS = int(os.environ.get("REPORT_INTERVAL_DAYS", 7))  # 新增：报告间隔天数，默认为 7 天

# --- 常量 ---
MAX_TRAFFIC_GB = MONTHLY_TRAFFIC_GB
TRAFFIC_DATA_FILE = "/data/outbound_traffic.json"  # 流量数据文件路径
LOG_FILE = "traffic_monitor.log"  # 日志文件路径
LOG_MAX_SIZE_BYTES = 2 * 1024 * 1024  # 日志文件最大大小，2MB

# --- 配置日志 ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 添加 FileHandler，将日志写入文件
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_SIZE_BYTES, backupCount=1)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 添加 StreamHandler，将日志输出到 stdout
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# --- 全局变量用于存储上次的流量数据 ---
previous_tx_bytes = 0
previous_rx_bytes = 0

# --- 函数 ---

def send_telegram_message(message):
    """发送 Telegram 消息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        logger.info(f"Telegram 消息已发送: {message}")
    except requests.exceptions.RequestException as e:
        logger.error(f"发送 Telegram 消息时出错: {e}")

def get_current_tx_bytes():
    """获取当前发送的字节数"""
    try:
        with open(f"/sys/class/net/{NETWORK_INTERFACE}/statistics/tx_bytes", "r") as f:
            return int(f.read())
    except FileNotFoundError:
        logger.error(f"错误: 找不到网络接口 {NETWORK_INTERFACE} 的发送统计信息。")
        return None

def get_current_rx_bytes():
    """获取当前接收的字节数"""
    try:
        with open(f"/sys/class/net/{NETWORK_INTERFACE}/statistics/rx_bytes", "r") as f:
            return int(f.read())
    except FileNotFoundError:
        logger.error(f"错误: 找不到网络接口 {NETWORK_INTERFACE} 的接收统计信息。")
        return None

def get_traffic_usage_gb(current_tx, current_rx):
    """计算两个时间间隔之间的流量使用量（GB）"""
    global previous_tx_bytes, previous_rx_bytes
    tx_diff = 0
    rx_diff = 0

    if current_tx is not None:
        tx_diff = current_tx - previous_tx_bytes if current_tx >= previous_tx_bytes else 0
        # 记录本次的 tx_bytes, rx_bytes
        previous_tx_bytes = current_tx
    else:
        return 0  # 无法获取发送数据，返回 0

    if current_rx is not None:
        rx_diff = current_rx - previous_rx_bytes if current_rx >= previous_rx_bytes else 0
        previous_rx_bytes = current_rx
    else:
        rx_diff = 0

    if TRAFFIC_DIRECTION == "bidirectional":
        traffic_gb = (tx_diff + rx_diff) / (1024 ** 3)
    else:
        traffic_gb = tx_diff / (1024 ** 3)

    # 添加详细日志
    logger.debug(f"current_tx: {current_tx}, previous_tx_bytes: {previous_tx_bytes}, tx_diff: {tx_diff}")
    logger.debug(f"current_rx: {current_rx}, previous_rx_bytes: {previous_rx_bytes}, rx_diff: {rx_diff}")
    logger.debug(f"Calculated traffic usage: {traffic_gb:.6f} GB")

    return traffic_gb

def get_host_hostname_from_file():
    """从 /etc/host_hostname 文件中获取主机名"""
    try:
        with open("/etc/host_hostname", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error("错误: 找不到 /etc/host_hostname 文件。")
        return "Unknown"

def get_public_ipv4():
    """获取公网 IPv4 地址"""
    try:
        response = requests.get("https://4.ipw.cn", timeout=5)
        response.raise_for_status()
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"获取公网 IP 时出错: {e}")
        return "Unknown"

def load_traffic_data():
    """加载流量数据"""
    try:
        with open(TRAFFIC_DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info("流量数据文件未找到，初始化新文件。")
        return {}
    except json.JSONDecodeError:
        logger.error("解码流量数据文件时出错，将使用新的数据。")
        return {}

def save_traffic_data(data):
    """保存流量数据"""
    with open(TRAFFIC_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def should_send_report(last_report_date, current_date):
    """检查是否应该发送定期报告"""
    if last_report_date is None:
        return True  # 第一次运行，发送报告
    last_report = datetime.datetime.strptime(last_report_date, "%Y-%m-%d").date()
    current = datetime.datetime.strptime(current_date, "%Y-%m-%d").date()
    return (current - last_report).days >= REPORT_INTERVAL_DAYS


if __name__ == "__main__":
    logger.info("流量监控服务已启动。")

    # 输入验证
    if not 1 <= REPORT_INTERVAL_DAYS <= 15:
        logger.warning(f"REPORT_INTERVAL_DAYS 值 ({REPORT_INTERVAL_DAYS}) 无效，已重置为默认值 7。")
        REPORT_INTERVAL_DAYS = 7

    HOST_HOSTNAME = get_host_hostname_from_file()
    PUBLIC_IP = get_public_ipv4()
    send_telegram_message(f"流量监控服务已启动！主机名: {HOST_HOSTNAME} (IP: {PUBLIC_IP})")

    # 第一次循环时初始化 previous_tx_bytes 和 previous_rx_bytes
    previous_tx_bytes = get_current_tx_bytes() or 0
    previous_rx_bytes = get_current_rx_bytes() or 0
    logger.info(f"Initial previous_tx_bytes: {previous_tx_bytes}, previous_rx_bytes: {previous_rx_bytes}")

    while True:
        now = datetime.datetime.now()
        current_month = now.strftime("%Y-%m")
        current_day = now.day
        current_date = now.strftime("%Y-%m-%d")

        traffic_data = load_traffic_data()

        if current_month not in traffic_data:
            traffic_data[current_month] = {
                "cumulative_traffic_gb": 0,
                "sent_thresholds": {str(threshold): False for threshold in THRESHOLDS},  # 使用字典记录每个阈值的发送状态
                "last_reset_day": 0,  # 添加一个字段来追踪上次重置的日期
                "last_report_date": None  # 新增：上次报告的日期
            }
            logger.info(f"为 {current_month} 创建新的流量记录。")

        cumulative_traffic_gb = traffic_data[current_month]["cumulative_traffic_gb"]
        sent_thresholds = traffic_data[current_month]["sent_thresholds"]
        last_reset_day = traffic_data[current_month].get("last_reset_day", 0) # 获取上次重置日期，默认为0
        last_report_date = traffic_data[current_month].get("last_report_date") # 新增：获取上次报告日期


        logger.info(f"当前累计流量: {cumulative_traffic_gb:.2f} GB")
        
        # 流量重置逻辑
        if current_day == RESET_DAY and last_reset_day != current_day:
            # 获取上个月的字符串和数据
            previous_month = (now - datetime.timedelta(days=30)).strftime("%Y-%m") # 粗略计算上个月

            if previous_month in traffic_data:
                previous_month_data = traffic_data[previous_month]
                previous_cumulative_traffic_gb = previous_month_data.get("cumulative_traffic_gb", 0)
                usage_percentage = (previous_cumulative_traffic_gb / MAX_TRAFFIC_GB) * 100 if MAX_TRAFFIC_GB > 0 else 0

                reset_message = (
                    f"流量已重置, 主机名: {HOST_HOSTNAME} (IP: {PUBLIC_IP}), "
                    f"{previous_month} 周期内使用流量 {previous_cumulative_traffic_gb:.2f}GB/{MAX_TRAFFIC_GB}GB, "
                    f"使用率 {usage_percentage:.0f}%"
                )
                send_telegram_message(reset_message)

            # 重置当前月数据
            traffic_data[current_month]["cumulative_traffic_gb"] = 0
            traffic_data[current_month]["sent_thresholds"] = {str(threshold): False for threshold in THRESHOLDS}
            traffic_data[current_month]["last_reset_day"] = current_day  # 更新上次重置日期
            traffic_data[current_month]["last_report_date"] = None  # 重置上次报告日期
            logger.info(f"{current_month} 流量计数已重置。")


        current_tx_bytes = get_current_tx_bytes()
        current_rx_bytes = get_current_rx_bytes() if TRAFFIC_DIRECTION == "bidirectional" else None

        if current_tx_bytes is not None:
            current_usage_gb = get_traffic_usage_gb(current_tx_bytes, current_rx_bytes)
            total_usage_gb = cumulative_traffic_gb + current_usage_gb

            # 定期报告逻辑
            if should_send_report(last_report_date, current_date):
                usage_percentage = (total_usage_gb / MAX_TRAFFIC_GB) * 100 if MAX_TRAFFIC_GB > 0 else 0
                report_message = (
                    f"定期报告, 主机名: {HOST_HOSTNAME} (IP: {PUBLIC_IP}), "
                    f"本周期内已使用流量 {total_usage_gb:.2f}GB/{MAX_TRAFFIC_GB}GB, "
                    f"使用率 {usage_percentage:.0f}%"
                )
                send_telegram_message(report_message)
                traffic_data[current_month]["last_report_date"] = current_date


            for threshold in THRESHOLDS:
                if total_usage_gb >= MAX_TRAFFIC_GB * threshold and not sent_thresholds.get(str(threshold)):
                    percentage = int(threshold * 100)
                    message = f"警告！主机名: {HOST_HOSTNAME} (IP: {PUBLIC_IP}) 本月流量已达到 {percentage}% ({total_usage_gb:.2f} GB / {MAX_TRAFFIC_GB} GB)。"
                    send_telegram_message(message)
                    traffic_data[current_month]["sent_thresholds"][str(threshold)] = True

            traffic_data[current_month]["cumulative_traffic_gb"] = total_usage_gb
            save_traffic_data(traffic_data)
            logger.info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 本次流量: {current_usage_gb:.6f} GB, 总流量: {total_usage_gb:.2f} GB")

        else:
            logger.warning("无法获取流量数据，跳过本次检查。")

        time.sleep(CHECK_INTERVAL_SECONDS)
