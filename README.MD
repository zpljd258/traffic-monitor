# 云服务器出站流量监控工具

**描述:**

这是一个用于监控运行 Alpine Linux 的云服务器出站流量（或双向流量）的工具。它会定期检查服务器的流量使用情况，并在达到预设的阈值时通过 Telegram 发送告警通知。该工具使用 Python 编写，并通过 Docker 进行容器化，方便部署和管理。

DockerHub 仓库地址: [https://hub.docker.com/r/zpljd/traffic-monitor](https://hub.docker.com/r/zpljd/traffic-monitor)

**主要功能:**

*   **每月流量监控:** 跟踪每个自然月的出站或双向流量。
*   **灵活的计费模式:** 可通过环境变量配置监控出站流量或双向流量。
*   **自定义每月流量:** 可以通过环境变量设置每月总流量限制。
*   **可配置的重置日:** 可以设置每月哪一天重置流量计数。
*   **多阈值告警:** 支持配置多个不同的流量告警阈值。
*   **Telegram 告警:** 当流量达到设定的阈值时，发送 Telegram 通知。
*   **每月重置通知:** 在每月流量重置时发送 Telegram 通知，包含上个月的流量使用情况。
*   **定期流量报告:** 可配置每 N 天 (1-15) 发送一次当前周期的流量使用情况报告。
*   **Docker 容器化:** 方便部署和管理，无需在主机上安装 Python 环境。
*   **持久化存储:** 使用 Docker Volume 持久化存储流量数据，避免因服务器重启导致数据丢失。
*   **告警信息包含主机名和 IP:** Telegram 告警消息中包含触发告警的服务器主机名和公网 IPv4 地址。
*   **可配置的检查间隔:** 可以通过环境变量自定义流量检查的频率。
*   **详细日志记录:** 将运行日志输出到容器的标准输出和文件中，方便查看和排错。

**前提条件:**

*   已安装 Docker 和 Docker Compose 的云服务器。
*   一个 Telegram Bot 及其 API Token。
*   你希望接收告警通知的 Telegram Chat ID。

**快速开始:**

1.  **复制文件:** 将以下文件复制到你的云服务器上的一个目录中：
    *   `Dockerfile`
    *   `traffic_monitor.py`
    *   `docker-compose.yml`

2.  **配置环境变量:** 编辑 `docker-compose.yml` 文件，将以下占位符替换为你的实际值：
    *   `YOUR_TELEGRAM_BOT_TOKEN`: 你的 Telegram Bot 的 API Token。
    *   `YOUR_TELEGRAM_CHAT_ID`: 你希望接收通知的 Telegram Chat ID。
    *   根据需要配置其他环境变量，例如 `TRAFFIC_DIRECTION`, `MONTHLY_TRAFFIC_GB`, `RESET_DAY`, `THRESHOLDS`, `CHECK_INTERVAL_SECONDS`, `NETWORK_INTERFACE`, `REPORT_INTERVAL_DAYS`。

3.  **构建 Docker 镜像:** 在包含 `docker-compose.yml` 文件的目录下运行：
    ```bash
    docker-compose build
    ```

4.  **启动 Docker 容器:** 运行以下命令启动流量监控服务：
    ```bash
    docker-compose up -d
    ```

**文件说明:**

*   `Dockerfile`: 用于构建 Docker 镜像的配置文件，包含安装依赖和复制代码的指令。
*   `traffic_monitor.py`: Python 脚本，负责监控流量、计算使用量、检查阈值并发送 Telegram 通知。
*   `docker-compose.yml`: 用于定义和管理 Docker 容器的配置文件，包括环境变量、Volume 挂载等。

**配置:**

`docker-compose.yml`:

| 环境变量                | 描述                                      | 默认值      | 可选值                                       |
| :---------------------- | :---------------------------------------- | :---------- | :------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`    | 你的 Telegram Bot 的 API Token。            | 必填        |                                              |
| `TELEGRAM_CHAT_ID`      | 你希望接收通知的 Telegram Chat ID。         | 必填        |                                              |
| `TRAFFIC_DIRECTION`     | 流量计算方向。                          | `outbound`   | `outbound`, `bidirectional`                |
| `MONTHLY_TRAFFIC_GB`    | 每月流量限制 (GB)。                       | `1024`      | 任意正整数                                   |
| `RESET_DAY`             | 每月流量重置的日期 (1-31)。                 | `1`         | `1` 到 `31` 的整数                          |
| `THRESHOLDS`            | 告警阈值，以逗号分隔的百分比表示。          | `"80,90,95"` | 任意正数，用逗号分隔，例如 `"70,85,98"`      |
| `CHECK_INTERVAL_SECONDS` | 检查流量的间隔时间 (秒)。                   | `60`        | 任意正整数                                   |
| `NETWORK_INTERFACE`     | 需要监控的网络接口名称。                  | `eth0`      | 服务器上的有效网络接口名称                   |
| `REPORT_INTERVAL_DAYS`  | 定期流量报告的间隔天数 (1-15)。             | `7`         | `1` 到 `15` 的整数                          |

`traffic_monitor.py`:

此文件中的常量值通常通过 `docker-compose.yml` 中的环境变量进行配置，一般情况下无需直接修改。

**使用:**

*   启动服务后，脚本会定期检查出站流量（或双向流量）。
*   当达到设定的阈值时，你会在 Telegram 中收到告警通知。
*   每月流量重置时，你会在 Telegram 中收到包含上个月流量使用情况的通知。
*   每隔 `REPORT_INTERVAL_DAYS` 天，你会在 Telegram 收到当前周期的流量使用情况报告。
*   可以使用 `docker logs <容器ID>` 命令查看容器的实时日志。
*   可以使用 `docker-compose stop` 和 `docker-compose start` 命令停止和启动服务。

**贡献:**

欢迎提交 Issue 和 Pull Request 来改进这个项目。

**许可证:**

本项目采用 MIT 许可证。
