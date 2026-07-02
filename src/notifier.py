#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信群机器人告警通知模块
通过 Webhook 发送 Markdown 格式告警消息
"""

import logging
from typing import List

import requests

from monitor import AlertInfo

logger = logging.getLogger(__name__)


class WeComBot:
    """企业微信群机器人通知"""

    def __init__(self, webhook_url: str, timeout: int = 10):
        """
        Args:
            webhook_url: 企微机器人 Webhook 地址
            timeout: 请求超时时间（秒）
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    def _send(self, payload: dict) -> bool:
        """发送请求到企微 Webhook"""
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                logger.info("企微告警发送成功")
                return True
            else:
                logger.error("企微告警发送失败: %s", data)
                return False
        except requests.RequestException as e:
            logger.error("企微告警请求异常: %s", e)
            return False
        except Exception as e:
            logger.error("企微告警未知异常: %s", e)
            return False

    def send_text(self, content: str, mentioned_list: List[str] = None) -> bool:
        """发送文本消息"""
        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
                "mentioned_list": mentioned_list or [],
            },
        }
        return self._send(payload)

    def send_markdown(self, content: str) -> bool:
        """发送 Markdown 消息"""
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }
        return self._send(payload)

    def send_alert(self, alert: AlertInfo) -> bool:
        """
        发送单条告警消息（Markdown 格式）

        Args:
            alert: 告警信息

        Returns:
            是否发送成功
        """
        content = self._format_alert_markdown(alert)
        return self.send_markdown(content)

    def send_alerts_summary(self, alerts: List[AlertInfo]) -> bool:
        """
        发送多条告警的汇总消息

        Args:
            alerts: 告警列表

        Returns:
            是否发送成功
        """
        if not alerts:
            return True

        # 企微 Markdown 消息上限 4096 字节，多条告警时分批发送
        batch_size = 5
        all_success = True

        for i in range(0, len(alerts), batch_size):
            batch = alerts[i : i + batch_size]
            content = self._format_summary_markdown(batch)
            if not self.send_markdown(content):
                all_success = False

        return all_success

    def _format_alert_markdown(self, alert: AlertInfo) -> str:
        """格式化单条告警为 Markdown"""
        plan = alert.plan

        # 根据告警级别选择颜色标识
        level_emoji = {
            "critical": "🔴",
            "warning": "🟠",
            "notice": "🟡",
            "exhausted": "⚫",
        }
        emoji = level_emoji.get(alert.level, "⚠️")

        # 格式化数字
        def _fmt_num(val: float) -> str:
            if val >= 1_000_000:
                return f"{val / 1_000_000:.2f}M"
            elif val >= 1_000:
                return f"{val / 1_000:.2f}K"
            return f"{val:.0f}"

        lines = [
            f"{emoji} **TokenPlan 额度告警**",
            f"",
            f"> **告警级别**: {alert.level}",
            f"> **告警信息**: {alert.message}",
            f"",
            f"**套餐名称**: {plan.name}",
            f"**套餐 ID**: `{plan.team_id}`",
            f"**套餐类型**: {plan.product_type}",
            f"**套餐状态**: {plan.status}" + (
                f" ({plan.stop_reason})" if plan.stop_reason else ""
            ),
            f"",
            f"**额度使用情况**:",
            f"- 总额度: {_fmt_num(plan.total_quota)} {plan.unit}",
            f"- 已使用: {_fmt_num(plan.total_used)} {plan.unit}",
            f"- 剩余: <font color=\"warning\">{_fmt_num(plan.remaining)}</font> {plan.unit}",
            f"- 使用率: <font color=\"warning\">{plan.usage_percent:.1f}%</font>",
            f"",
        ]

        if plan.cycle_quota > 0:
            lines.append(f"**周期信息**:")
            lines.append(f"- 当期额度: {_fmt_num(plan.cycle_quota)} {plan.unit}")
            lines.append(f"- 当前周期: {plan.current_cycle}")
            lines.append(f"- 剩余周期: {plan.remain_cycles}")
            lines.append("")

        if plan.shared_pool > 0 or plan.exclusive_allocated > 0:
            lines.append(f"**额度池详情**:")
            if plan.exclusive_allocated > 0:
                lines.append(
                    f"- 独占池: 已分配 {_fmt_num(plan.exclusive_allocated)} / 已用 {_fmt_num(plan.exclusive_used)}"
                )
            if plan.shared_pool > 0:
                lines.append(
                    f"- 共享池: 总额 {_fmt_num(plan.shared_pool)} / 已用 {_fmt_num(plan.shared_used)}"
                )
            lines.append("")

        if plan.expire_time:
            lines.append(f"**到期时间**: {plan.expire_time}")
            lines.append("")

        lines.append(f"<font color=\"comment\">请及时关注并处理</font>")

        return "\n".join(lines)

    def _format_summary_markdown(self, alerts: List[AlertInfo]) -> str:
        """格式化多条告警汇总为 Markdown"""
        level_emoji = {
            "critical": "🔴",
            "warning": "🟠",
            "notice": "🟡",
            "exhausted": "⚫",
        }

        lines = [
            f"## ⚠️ TokenPlan 额度监控告警 ({len(alerts)} 条)",
            f"",
        ]

        for alert in alerts:
            plan = alert.plan
            emoji = level_emoji.get(alert.level, "⚠️")
            lines.append(
                f"{emoji} **{plan.name}** | 使用率: "
                f"<font color=\"warning\">{plan.usage_percent:.1f}%</font> "
                f"| 级别: {alert.level}"
            )
            lines.append(
                f"  > 已用 {plan.total_used:.0f} / 总额 {plan.total_quota:.0f} {plan.unit}"
            )
            lines.append("")

        lines.append("<font color=\"comment\">请及时关注并处理</font>")

        return "\n".join(lines)
