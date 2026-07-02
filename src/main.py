#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯云 TokenPlan 额度监控程序
主程序入口

功能：
1. 周期性查询腾讯云 TokenHub 所有套餐额度
2. 检测额度使用率是否达到阈值
3. 通过企业微信群机器人发送告警通知
"""

import argparse
import logging
import os
import sys
import time
from typing import Dict, Any

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# 将 src 目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger_config import setup_logging
from qcloud_client import TokenHubClient
from monitor import QuotaMonitor, AlertCooldownManager
from notifier import WeComBot

logger = logging.getLogger(__name__)


class TokenPlanMonitorApp:
    """TokenPlan 监控应用"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # 初始化腾讯云客户端
        tc = config["tencent_cloud"]
        self.client = TokenHubClient(
            secret_id=tc["secret_id"],
            secret_key=tc["secret_key"],
            region=tc.get("region", "ap-guangzhou"),
        )

        # 初始化监控器
        self.monitor = QuotaMonitor(
            thresholds=config.get("thresholds", []),
            alert_on_exhausted=config.get("alert_on_exhausted", True),
        )

        # 初始化告警冷却管理器
        self.cooldown_mgr = AlertCooldownManager(
            cooldown_minutes=config.get("alert_cooldown_minutes", 60)
        )

        # 初始化企微机器人
        self.bot = WeComBot(webhook_url=config["wecom_webhook"])

    def run_check(self):
        """执行一次额度检查"""
        logger.info("=" * 60)
        logger.info("开始执行 TokenPlan 额度检查")
        start_time = time.time()

        try:
            # 1. 获取所有套餐列表
            plans = self.client.get_all_plans()
            if not plans:
                logger.info("未找到任何套餐")
                return

            # 2. 获取每个套餐的详情（含额度用量）
            plan_details = []
            for plan in plans:
                team_id = plan.get("TeamId", "")
                if not team_id:
                    continue

                # 列表接口已包含基本信息，详情接口包含 PackageInfo 和 TokenSummary
                detail = self.client.get_plan_details(team_id)
                if detail:
                    plan_details.append(detail)
                else:
                    # 如果详情接口失败，用列表数据兜底
                    logger.warning(
                        "套餐 %s 详情获取失败，使用列表数据", team_id
                    )
                    plan_details.append(plan)

                # 避免触发频率限制（20次/秒，保守一点）
                time.sleep(0.1)

            # 3. 检查阈值
            alerts = self.monitor.check_all_plans(plan_details)

            if not alerts:
                logger.info("所有套餐额度使用正常，无需告警")
                return

            # 4. 过滤冷却期内的告警
            filtered_alerts = []
            for alert in alerts:
                if self.cooldown_mgr.should_alert(alert.plan.team_id, alert.level):
                    filtered_alerts.append(alert)

            if not filtered_alerts:
                logger.info("所有告警均在冷却期内，跳过发送")
                return

            # 5. 发送告警
            logger.info("共 %d 条告警需要发送", len(filtered_alerts))
            success = self.bot.send_alerts_summary(filtered_alerts)

            if success:
                logger.info("告警发送完成")
            else:
                logger.error("部分告警发送失败")

        except Exception as e:
            logger.error("额度检查执行失败: %s", e, exc_info=True)
            # 发送错误通知
            try:
                self.bot.send_text(f"TokenPlan 监控程序执行异常: {e}")
            except Exception:
                pass

        elapsed = time.time() - start_time
        logger.info("额度检查完成，耗时 %.2f 秒", elapsed)
        logger.info("=" * 60)

    def run_once(self):
        """执行一次检查后退出"""
        self.run_check()

    def run_scheduled(self):
        """启动定时调度"""
        schedule_config = self.config.get("schedule", {})

        scheduler = BlockingScheduler()

        # 优先使用 cron 表达式
        cron_expr = schedule_config.get("cron")
        interval_minutes = schedule_config.get("interval_minutes")

        if cron_expr:
            # 解析 cron 表达式 "*/30 * * * *"
            parts = cron_expr.split()
            if len(parts) == 5:
                trigger = CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                )
                scheduler.add_job(
                    self.run_check,
                    trigger=trigger,
                    id="token_plan_monitor",
                    name="TokenPlan 额度监控",
                    max_instances=1,
                    misfire_grace_time=300,
                )
                logger.info("已配置 cron 定时任务: %s", cron_expr)
            else:
                logger.error("cron 表达式格式错误: %s，应为 5 段格式", cron_expr)
                sys.exit(1)
        elif interval_minutes:
            trigger = IntervalTrigger(minutes=interval_minutes)
            scheduler.add_job(
                self.run_check,
                trigger=trigger,
                id="token_plan_monitor",
                name="TokenPlan 额度监控",
                max_instances=1,
                misfire_grace_time=300,
                next_run_time=None,  # 不立即执行，等待第一个间隔
            )
            logger.info("已配置 interval 定时任务: 每 %d 分钟", interval_minutes)
        else:
            logger.error("未配置调度方式，请在 config.yaml 中设置 schedule.cron 或 schedule.interval_minutes")
            sys.exit(1)

        # 启动时先执行一次
        logger.info("启动时先执行一次检查...")
        self.run_check()

        logger.info("定时监控已启动，按 Ctrl+C 退出")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("监控程序已停止")


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 校验必填项
    tc = config.get("tencent_cloud", {})
    if not tc.get("secret_id") or tc.get("secret_id") == "your-secret-id":
        logger.error("请在配置文件中设置 tencent_cloud.secret_id")
        sys.exit(1)
    if not tc.get("secret_key") or tc.get("secret_key") == "your-secret-key":
        logger.error("请在配置文件中设置 tencent_cloud.secret_key")
        sys.exit(1)
    if not config.get("wecom_webhook") or "your-bot-key" in config.get("wecom_webhook", ""):
        logger.error("请在配置文件中设置 wecom_webhook")
        sys.exit(1)

    return config


def main():
    # 默认配置路径基于项目根目录（src 的上一级）
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_config = os.path.join(project_root, "config", "config.yaml")

    parser = argparse.ArgumentParser(description="腾讯云 TokenPlan 额度监控程序")
    parser.add_argument(
        "-c", "--config",
        default=default_config,
        help="配置文件路径 (默认: config/config.yaml)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只执行一次检查后退出（不启动定时任务）",
    )
    parser.add_argument(
        "--test-alert",
        action="store_true",
        help="发送一条测试告警消息到企微群",
    )
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 配置日志
    log_config = config.get("logging", {})
    setup_logging(
        level=log_config.get("level", "INFO"),
        log_file=log_config.get("file"),
        max_size_mb=log_config.get("max_size_mb", 10),
        backup_count=log_config.get("backup_count", 5),
    )

    logger.info("腾讯云 TokenPlan 额度监控程序启动")
    logger.info("配置文件: %s", args.config)

    # 测试告警模式
    if args.test_alert:
        from monitor import AlertInfo, PlanUsageInfo

        bot = WeComBot(webhook_url=config["wecom_webhook"])
        test_plan = PlanUsageInfo(
            team_id="team-test-0001",
            name="测试套餐",
            status="enable",
            stop_reason="",
            product_type="enterprise",
            total_quota=1000000,
            total_used=850000,
            usage_percent=85.0,
            remaining=150000,
            current_cycle=3,
            remain_cycles=9,
            cycle_quota=100000,
            start_time="2026-04-01T00:00:00Z",
            expire_time="2027-04-01T00:00:00Z",
            unit="credits",
        )
        test_alert = AlertInfo(
            plan=test_plan,
            level="warning",
            message="这是一条测试告警消息",
            usage_percent=85.0,
        )
        success = bot.send_alert(test_alert)
        if success:
            logger.info("测试告警发送成功")
        else:
            logger.error("测试告警发送失败")
        return

    # 初始化应用
    app = TokenPlanMonitorApp(config)

    if args.once:
        logger.info("单次执行模式")
        app.run_once()
    else:
        app.run_scheduled()


if __name__ == "__main__":
    main()
