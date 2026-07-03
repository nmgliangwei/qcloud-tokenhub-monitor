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
- 告警开关可配置，关闭后仅暴露 Prometheus 指标，由 Alertmanager 负责告警
- 支持 cron 表达式和 interval 两种定时调度方式
- 支持单次执行模式和测试告警模式
- 暴露 Prometheus metrics 指标，指标刷新与告警检测独立调度
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
│   ├── metrics.py           # Prometheus 指标暴露
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
# 告警关闭时（alert.enabled=false）可不配置
wecom_webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的机器人key"

# 告警配置
alert:
  # 是否启用企微告警通知
  # true  - 通过企业微信群机器人发送告警（需配置 wecom_webhook）
  # false - 关闭告警，仅暴露 Prometheus 指标，由 Alertmanager 负责告警
  enabled: true
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
| [DescribeUsageRankList](https://cloud.tencent.com/document/api/1823/132279) | 查询用量排行（按 API Key/模型/接入点维度聚合） |

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

## Prometheus 指标

程序内置 Prometheus metrics 暴露，默认监听 `0.0.0.0:9100/metrics`，可对接 Prometheus + Grafana + Alertmanager 实现完整的监控告警体系。

metrics 指标刷新与告警检测使用独立的调度周期：
- **告警检测**：由 `schedule.cron` 或 `schedule.interval_minutes` 控制（如每 30 分钟）
- **指标刷新**：由 `metrics.refresh_interval_minutes` 控制（如每 5 分钟），独立调用 API 更新指标，不影响告警检测频率

### 配置

```yaml
metrics:
  enabled: true               # 是否启用
  addr: "0.0.0.0"             # 监听地址
  port: 9100                  # 监听端口
  # metrics 指标刷新周期（分钟），独立于告警检测周期 schedule
  # 腾讯云 API 限制 20 次/秒，建议不低于 3 分钟，默认 5 分钟
  refresh_interval_minutes: 5
  # 用量排行维度，支持: apikey / model / endpoint
  usage_dimensions: ["apikey", "model"]
  # 用量统计时间范围，支持:
  #   固定标识:
  #     today          - 今天 0:00 到当前时刻
  #     yesterday      - 昨天 0:00 到今天 0:00（完整自然日）
  #     last_7_days    - 7 天前 0:00 到当前时刻
  #     last_30_days   - 30 天前 0:00 到当前时刻
  #     current_cycle  - 默认取最近 30 天
  #   相对小时（滚动窗口，从 N 小时前到当前时刻）:
  #     last_Nh        - N 为任意正整数，如 last_1h, last_6h, last_12h, last_24h
  #   相对天数（滚动窗口，从 N 天前同一时刻到当前时刻）:
  #     last_Nd        - N 为任意正整数，如 last_1d, last_3d, last_14d
  # 注意:
  #   - N 为任意正整数，代码层面无上限
  #   - 腾讯云 API 对时间跨度有上限限制（错误码 PeriodExceedsSpan），文档未明确具体值
  #   - 建议不超过 30 天，超出后 API 可能返回错误，程序会跳过并记录 WARNING 日志
  usage_period: "last_24h"
```

### 指标列表

#### 额度指标

| 指标 | 类型 | 说明 | 标签 |
|------|------|------|------|
| `tokenhub_plan_usage_percent` | Gauge | 套餐额度使用率（%） | team_id, name, product_type |
| `tokenhub_plan_total_quota` | Gauge | 套餐总额度 | team_id, name, unit |
| `tokenhub_plan_total_used` | Gauge | 套餐已使用额度 | team_id, name, unit |
| `tokenhub_plan_remaining` | Gauge | 套餐剩余额度 | team_id, name, unit |
| `tokenhub_plan_cycle_quota` | Gauge | 套餐当期额度 | team_id, name, unit |
| `tokenhub_plan_current_cycle` | Gauge | 当前周期 | team_id, name |
| `tokenhub_plan_remain_cycles` | Gauge | 剩余周期数 | team_id, name |
| `tokenhub_plan_total_cycles` | Gauge | 总周期数 | team_id, name |
| `tokenhub_plan_status` | Gauge | 套餐状态（1=正常, 0=异常） | team_id, name, status, stop_reason |
| `tokenhub_plan_exclusive_allocated` | Gauge | 独占池已分配额度 | team_id, name, unit |
| `tokenhub_plan_exclusive_used` | Gauge | 独占池已使用额度 | team_id, name, unit |
| `tokenhub_plan_shared_pool` | Gauge | 共享池总额度 | team_id, name, unit |
| `tokenhub_plan_shared_used` | Gauge | 共享池已使用额度 | team_id, name, unit |

#### Token 使用指标（当前周期累计）

| 指标 | 类型 | 说明 | 标签 |
|------|------|------|------|
| `tokenhub_plan_token_usage` | Gauge | Token 用量（通用，按 billing_item 标签区分） | team_id, name, billing_item |
| `tokenhub_plan_token_input` | Gauge | 输入 Token 用量 | team_id, name |
| `tokenhub_plan_token_output` | Gauge | 输出 Token 用量 | team_id, name |
| `tokenhub_plan_token_cache` | Gauge | 缓存 Token 用量 | team_id, name |
| `tokenhub_plan_token_total` | Gauge | 总 Token 用量（输入+输出+缓存） | team_id, name |
| `tokenhub_plan_call_count` | Gauge | API 调用次数 | team_id, name |
| `tokenhub_plan_cache_hit_ratio` | Gauge | 缓存命中率（%） | team_id, name |

#### 时间指标

| 指标 | 类型 | 说明 | 标签 |
|------|------|------|------|
| `tokenhub_plan_start_timestamp` | Gauge | 套餐开始时间（Unix 时间戳） | team_id, name |
| `tokenhub_plan_expire_timestamp` | Gauge | 套餐到期时间（Unix 时间戳） | team_id, name |
| `tokenhub_plan_cycle_seq` | Gauge | 当前计费周期序号 | team_id, name |
| `tokenhub_plan_cycle_start_timestamp` | Gauge | 当前计费周期开始时间 | team_id, name |
| `tokenhub_plan_cycle_end_timestamp` | Gauge | 当前计费周期结束时间 | team_id, name |

#### API Key 指标

| 指标 | 类型 | 说明 | 标签 |
|------|------|------|------|
| `tokenhub_plan_api_key_count` | Gauge | 已创建 API Key 数量 | team_id, name |
| `tokenhub_plan_api_key_max` | Gauge | API Key 上限 | team_id, name |

#### 按维度聚合的 Token 用量指标（DescribeUsageRankList）

按 `apikey` / `model` / `endpoint` 维度聚合的 Token 用量，可通过配置 `metrics.usage_dimensions` 选择启用的维度。

| 指标 | 类型 | 说明 | 标签 |
|------|------|------|------|
| `tokenhub_usage_input_token` | Gauge | 输入 Token 用量 | team_id, plan_name, dimension, key, name |
| `tokenhub_usage_output_token` | Gauge | 输出 Token 用量 | team_id, plan_name, dimension, key, name |
| `tokenhub_usage_cache_token` | Gauge | 缓存 Token 用量 | team_id, plan_name, dimension, key, name |
| `tokenhub_usage_total_token` | Gauge | 总 Token 用量 | team_id, plan_name, dimension, key, name |
| `tokenhub_usage_search_request_count` | Gauge | 搜索请求数 | team_id, plan_name, dimension, key, name |
| `tokenhub_usage_search_count` | Gauge | 搜索引擎调用次数 | team_id, plan_name, dimension, key, name |

> `dimension` 标签取值: `apikey` / `model` / `endpoint`，`key` 为对应维度的标识（如 API Key ID、模型名等），`name` 为展示名。

#### 程序运行指标

| 指标 | 类型 | 说明 | 标签 |
|------|------|------|------|
| `tokenhub_plans_total` | Gauge | 监控的套餐总数 | - |
| `tokenhub_check_total` | Counter | 额度检查执行总次数 | - |
| `tokenhub_check_errors_total` | Counter | 额度检查失败次数 | - |
| `tokenhub_check_duration_seconds` | Gauge | 最近一次检查耗时（秒） | - |

### Prometheus 采集配置示例

```yaml
scrape_configs:
  - job_name: 'qcloud-tokenhub-monitor'
    static_configs:
      - targets: ['localhost:9100']
```

### Alertmanager 告警规则示例

```yaml
groups:
  - name: tokenhub-quota
    rules:
      # 使用率 >= 90%
      - alert: TokenHubQuotaCritical
        expr: tokenhub_plan_usage_percent >= 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "套餐 {{ $labels.name }} 额度使用率严重"
          description: "套餐 {{ $labels.name }} ({{ $labels.team_id }}) 使用率已达 {{ $value }}%"

      # 使用率 >= 80%
      - alert: TokenHubQuotaWarning
        expr: tokenhub_plan_usage_percent >= 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "套餐 {{ $labels.name }} 额度使用率告警"
          description: "套餐 {{ $labels.name }} ({{ $labels.team_id }}) 使用率已达 {{ $value }}%"

      # 套餐状态异常
      - alert: TokenHubPlanAbnormal
        expr: tokenhub_plan_status == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "套餐 {{ $labels.name }} 状态异常"
          description: "套餐 {{ $labels.name }} 状态: {{ $labels.status }}, 原因: {{ $labels.stop_reason }}"

      # 套餐即将到期（7天内）
      - alert: TokenHubPlanExpiringSoon
        expr: (tokenhub_plan_expire_timestamp - time()) < 7 * 24 * 3600
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "套餐 {{ $labels.name }} 即将到期"
          description: "套餐 {{ $labels.name }} 将在 {{ $value | humanizeDuration }} 后到期"

      # 检查失败
      - alert: TokenHubCheckFailed
        expr: rate(tokenhub_check_errors_total[10m]) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "TokenHub 监控检查失败"
          description: "过去 10 分钟内检查出现错误"
```

### Grafana 常用 PromQL 示例

```promql
# 各套餐使用率
tokenhub_plan_usage_percent

# 使用率超过 80% 的套餐
tokenhub_plan_usage_percent > 80

# 套餐剩余额度
tokenhub_plan_remaining

# 输入 Token 用量
tokenhub_plan_token_input

# 输出 Token 用量
tokenhub_plan_token_output

# 缓存 Token 用量
tokenhub_plan_token_cache

# 总 Token 用量
tokenhub_plan_token_total

# 缓存命中率
tokenhub_plan_cache_hit_ratio

# API 调用次数
tokenhub_plan_call_count

# 各计费项 Token 使用量（通用）
tokenhub_plan_token_usage

# 按 API Key 维度的输入 Token 用量
tokenhub_usage_input_token{dimension="apikey"}

# 按模型维度的总 Token 用量排行
topk(10, tokenhub_usage_total_token{dimension="model"})

# 按模型维度的缓存命中率
tokenhub_usage_cache_token{dimension="model"} / (tokenhub_usage_input_token{dimension="model"} + tokenhub_usage_cache_token{dimension="model"}) * 100

# 按 API Key 维度的输出 Token 用量
tokenhub_usage_output_token{dimension="apikey"}

# 按 endpoint 维度的搜索调用次数
tokenhub_usage_search_count{dimension="endpoint"}

# 距离到期剩余天数
(tokenhub_plan_expire_timestamp - time()) / 86400

# 当前计费周期剩余天数
(tokenhub_plan_cycle_end_timestamp - time()) / 86400

# API Key 使用率
tokenhub_plan_api_key_count / tokenhub_plan_api_key_max * 100

# 检查成功率
1 - rate(tokenhub_check_errors_total[1h]) / rate(tokenhub_check_total[1h])

# 最近一次检查耗时
tokenhub_check_duration_seconds
```

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
  -p 9100:9100 \
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
  -p 9100:9100 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  qcloud-tokenhub-monitor
```

## 注意事项

1. **API 频率限制**：TokenHub API 限制 20 次/秒，程序已内置 0.1 秒间隔避免触发限流
2. **子账号权限**：子账号只能查看自己创建的套餐，建议使用主账号 API 密钥
3. **企微消息限制**：Markdown 消息上限 4096 字节，程序已自动分批发送
4. **额度单位**：企业版专业套餐单位为 credits，企业版轻享套餐单位为 tokens
