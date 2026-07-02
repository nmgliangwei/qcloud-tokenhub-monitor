# 腾讯云 TokenPlan 额度监控程序

![Docker Build](https://img.shields.io/github/actions/workflow/status/nmgliangwei/qcloud-tokenhub-monitor/docker-publish.yml?logo=github&label=docker%20build)
![Docker Image Version](https://img.shields.io/github/v/tag/nmgliangwei/qcloud-tokenhub-monitor?logo=docker&label=docker&sort=semver)
![Docker Pulls](https://img.shields.io/badge/ghcr.io-nmgliangwei%2Fqcloud--tokenhub--monitor-blue?logo=docker)
![Python Version](https://img.shields.io/badge/python-3.14-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-linux%2Famd64%20%7C%20arm64-green?logo=linux)
![License](https://img.shields.io/github/license/nmgliangwei/qcloud-tokenhub-monitor?logo=opensourceinitiative)

周期性检测腾讯云 TokenHub 所有套餐额度使用情况，当使用率达到设定阈值时，通过企业微信群机器人自动发送告警通知。

## 功能特性

- 自动获取腾讯云 TokenHub 所有 TokenPlan 套餐及额度详情
- 支持多级阈值告警（提醒 / 警告 / 严重），按使用率从高到低匹配
- 支持告警冷却机制，避免同一套餐同一级别重复告警
- 额度耗尽（EXHAUSTED）套餐单独告警
- 企业微信群机器人 Markdown 格式告警，信息丰富直观
- 支持 cron 表达式和 interval 两种定时调度方式
- 支持单次执行模式和测试告警模式
- 完善的日志记录（控制台 + 文件轮转）

## 项目结构

```
qcloud-monitor/
├── config/
│   └── config.yaml          # 配置文件
├── src/
│   ├── __init__.py
│   ├── main.py              # 主程序入口
│   ├── qcloud_client.py     # 腾讯云 TokenHub API 客户端
│   ├── monitor.py           # 额度监控逻辑
│   ├── notifier.py          # 企微机器人告警通知
│   └── logger_config.py     # 日志配置
├── logs/                    # 日志目录（自动创建）
├── requirements.txt         # Python 依赖
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
cd qcloud-monitor
pip install -r requirements.txt
```

### 2. 配置

编辑 `config/config.yaml`，填入以下信息：

```yaml
# 腾讯云 API 凭证（获取地址：https://console.cloud.tencent.com/cam/capi）
tencent_cloud:
  secret_id: "你的SecretId"
  secret_key: "你的SecretKey"
  region: "ap-guangzhou"

# 企业微信群机器人 Webhook
# 获取方式：企微群 → 右上角群设置 → 群机器人 → 添加机器人 → 复制 Webhook 地址
wecom_webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的机器人key"
```

### 3. 运行

#### 测试告警（验证企微机器人配置是否正确）

```bash
cd src
python main.py --test-alert
```

#### 单次执行检查

```bash
cd src
python main.py --once
```

#### 启动定时监控（前台运行）

```bash
cd src
python main.py
```

#### 后台运行（推荐使用 nohup 或 systemd）

```bash
cd src
nohup python main.py > /dev/null 2>&1 &
```

## 配置说明

### 阈值配置

支持多级阈值，按 `usage_percent` 从高到低匹配，同一套餐只会触发最高级别的告警：

```yaml
thresholds:
  - level: "critical"        # 严重告警
    usage_percent: 95        # 使用率 >= 95%
    message: "额度即将耗尽，请立即处理！"
  - level: "warning"         # 警告
    usage_percent: 80        # 使用率 >= 80%
    message: "额度使用率较高，请关注。"
  - level: "notice"          # 提醒
    usage_percent: 50        # 使用率 >= 50%
    message: "额度使用过半，请注意。"
```

### 告警冷却

同一套餐在冷却时间内达到同一告警级别不会重复发送：

```yaml
alert_cooldown_minutes: 60   # 冷却时间 60 分钟
```

### 定时调度

支持两种方式，`cron` 优先：

```yaml
# 方式一：cron 表达式（推荐）
schedule:
  cron: "*/30 * * * *"       # 每 30 分钟执行一次

# 方式二：间隔执行
schedule:
  interval_minutes: 30       # 每 30 分钟执行一次
```

常用 cron 表达式：

| 表达式 | 说明 |
|--------|------|
| `*/30 * * * *` | 每 30 分钟 |
| `0 * * * *` | 每小时整点 |
| `0 */2 * * *` | 每 2 小时 |
| `0 9 * * *` | 每天 9:00 |
| `0 9,18 * * *` | 每天 9:00 和 18:00 |

## 告警消息示例

### 汇总告警

```
⚠️ TokenPlan 额度监控告警 (2 条)

🟠 生产环境套餐 | 使用率: 85.3% | 级别: warning
  > 已用 853000 / 总额 1000000 credits

🔴 测试套餐 | 使用率: 96.2% | 级别: critical
  > 已用 962000 / 总额 1000000 credits

请及时关注并处理
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `-c, --config` | 指定配置文件路径（默认: `config/config.yaml`） |
| `--once` | 只执行一次检查后退出 |
| `--test-alert` | 发送一条测试告警消息到企微群 |

## API 说明

本程序使用以下腾讯云 TokenHub API：

| API | 功能 |
|-----|------|
| [DescribeTokenPlanList](https://cloud.tencent.com/document/api/1823/132269) | 查询套餐列表 |
| [DescribeTokenPlan](https://cloud.tencent.com/document/api/1823/132270) | 查询套餐详情（含额度用量） |

### 关键数据结构

**TokenPlanPackageInfo**（主额度包信息）：
- `TotalQuota` - 总额度
- `TotalUsed` - 总已使用额度
- `CycleQuota` - 当期额度
- `CurrentCycle` / `RemainCycles` - 当前/剩余周期
- `ExclusiveAllocated` / `ExclusiveUsed` - 独占池已分配/已用
- `SharedPool` / `SharedUsed` - 共享池总额/已用

**StopReason**（关停原因）：
- `NORMAL` - 正常
- `ISOLATED` - 隔离/欠费
- `FROZEN` - 冻结
- `EXHAUSTED` - 额度耗尽
- `DESTROYED` - 已销毁

## 部署建议

### systemd 服务

创建 `/etc/systemd/system/qcloud-tokenhub-monitor.service`：

```ini
[Unit]
Description=Tencent Cloud TokenPlan Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/qcloud-tokenhub-monitor/src
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable qcloud-tokenhub-monitor
sudo systemctl start qcloud-tokenhub-monitor
```

### Docker启动

镜像地址：`ghcr.io/nmgliangwei/qcloud-tokenhub-monitor`

#### 镜像 Tag 说明

| Tag | 说明 | 触发条件 |
|-----|------|----------|
| `dev` | 开发版，包含最新代码 | 推送到 `main` 分支时自动构建 |
| `v*` (如 `v1.0.0`) | 正式发布版，与 Git Tag 一一对应 | 打 `v*` 开头的 Tag 时构建 |
| `latest` | 最新正式发布版 | 打 `v*` 开头的 Tag 时自动指向该版本 |

**推荐使用 `latest` tag**，它始终指向最新的正式发布版本，稳定性有保障。如果需要体验最新功能，可以使用 `dev` tag。

#### 使用镜像(镜像 tag 自行替换)
```
docker run -d --name qcloud-tokenhub-monitor \
  --restart unless-stopped \
  -e TZ=Asia/Shanghai \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/nmgliangwei/qcloud-tokenhub-monitor:latest
```

## 自行打包
```bash
#镜像制作
docker build -t qcloud-tokenhub-monitor .
#启动
docker run -d --name qcloud-tokenhub-monitor \
  --restart unless-stopped \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  qcloud-tokenhub-monitor
```

## 注意事项

1. **API 频率限制**：TokenHub API 限制 20 次/秒，程序已内置 0.1 秒间隔避免触发限流
2. **子账号权限**：子账号只能查看自己创建的套餐，建议使用主账号 API 密钥
3. **企微消息限制**：Markdown 消息上限 4096 字节，程序已自动分批发送
4. **额度单位**：企业版专业套餐单位为 credits，企业版轻享套餐单位为 tokens
