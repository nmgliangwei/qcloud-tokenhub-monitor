#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
额度监控模块
解析套餐额度数据，计算使用率，判断是否达到告警阈值
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanUsageInfo:
    """套餐额度使用信息"""

    team_id: str
    name: str
    status: str
    stop_reason: str
    product_type: str

    # 额度信息
    total_quota: float = 0.0
    total_used: float = 0.0
    usage_percent: float = 0.0
    remaining: float = 0.0

    # 周期信息
    current_cycle: int = 0
    remain_cycles: int = 0
    cycle_quota: float = 0.0

    # 独占池 / 共享池
    exclusive_allocated: float = 0.0
    exclusive_used: float = 0.0
    shared_pool: float = 0.0
    shared_used: float = 0.0

    # 套餐包时间
    start_time: str = ""
    expire_time: str = ""

    # 额度单位
    unit: str = "credits"

    # 原始数据
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertInfo:
    """告警信息"""

    plan: PlanUsageInfo
    level: str          # critical / warning / notice / exhausted
    message: str
    usage_percent: float


class QuotaMonitor:
    """额度监控器"""

    def __init__(self, thresholds: List[Dict[str, Any]], alert_on_exhausted: bool = True):
        """
        Args:
            thresholds: 阈值配置列表，按 usage_percent 从高到低排序
            alert_on_exhausted: 是否对已耗尽套餐发送告警
        """
        # 确保阈值按使用率从高到低排序
        self.thresholds = sorted(
            thresholds, key=lambda x: x.get("usage_percent", 0), reverse=True
        )
        self.alert_on_exhausted = alert_on_exhausted

    def parse_plan_detail(self, plan_detail: Dict[str, Any]) -> PlanUsageInfo:
        """
        解析套餐详情，提取额度使用信息

        Args:
            plan_detail: DescribeTokenPlan 返回的套餐详情

        Returns:
            PlanUsageInfo 对象
        """
        package_info = plan_detail.get("PackageInfo") or {}

        # 确定额度单位
        product_type = plan_detail.get("ProductType", "enterprise")
        unit = "tokens" if product_type == "enterprise-auto" else "credits"

        # 解析额度数值（API 返回的是字符串类型）
        def _to_float(val: Any) -> float:
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        total_quota = _to_float(package_info.get("TotalQuota"))
        total_used = _to_float(package_info.get("TotalUsed"))
        remaining = total_quota - total_used
        usage_percent = (total_used / total_quota * 100) if total_quota > 0 else 0.0

        return PlanUsageInfo(
            team_id=plan_detail.get("TeamId", ""),
            name=plan_detail.get("Name", ""),
            status=plan_detail.get("Status", ""),
            stop_reason=plan_detail.get("StopReason", ""),
            product_type=product_type,
            total_quota=total_quota,
            total_used=total_used,
            usage_percent=usage_percent,
            remaining=remaining,
            current_cycle=package_info.get("CurrentCycle", 0) or 0,
            remain_cycles=package_info.get("RemainCycles", 0) or 0,
            cycle_quota=_to_float(package_info.get("CycleQuota")),
            exclusive_allocated=_to_float(package_info.get("ExclusiveAllocated")),
            exclusive_used=_to_float(package_info.get("ExclusiveUsed")),
            shared_pool=_to_float(package_info.get("SharedPool")),
            shared_used=_to_float(package_info.get("SharedUsed")),
            start_time=package_info.get("StartTime", ""),
            expire_time=package_info.get("ExpireTime", ""),
            unit=unit,
            raw=plan_detail,
        )

    def check_threshold(self, plan: PlanUsageInfo) -> Optional[AlertInfo]:
        """
        检查套餐是否达到告警阈值

        Args:
            plan: 套餐使用信息

        Returns:
            告警信息，未达到阈值返回 None
        """
        # 检查额度是否已耗尽
        if plan.stop_reason == "EXHAUSTED":
            if self.alert_on_exhausted:
                return AlertInfo(
                    plan=plan,
                    level="exhausted",
                    message="额度已耗尽，套餐已被关停！",
                    usage_percent=100.0,
                )
            return None

        # 检查是否达到阈值
        for threshold in self.thresholds:
            threshold_percent = threshold.get("usage_percent", 0)
            if plan.usage_percent >= threshold_percent:
                return AlertInfo(
                    plan=plan,
                    level=threshold.get("level", "warning"),
                    message=threshold.get("message", "额度使用率告警"),
                    usage_percent=plan.usage_percent,
                )

        return None

    def check_all_plans(
        self, plans_with_details: List[Dict[str, Any]]
    ) -> List[AlertInfo]:
        """
        批量检查所有套餐

        Args:
            plans_with_details: 套餐详情列表

        Returns:
            需要告警的套餐列表
        """
        alerts: List[AlertInfo] = []

        for detail in plans_with_details:
            try:
                plan_info = self.parse_plan_detail(detail)
                alert = self.check_threshold(plan_info)
                if alert:
                    alerts.append(alert)
                    logger.warning(
                        "套餐 [%s](%s) 触发告警: %s (使用率: %.1f%%)",
                        plan_info.name,
                        plan_info.team_id,
                        alert.level,
                        plan_info.usage_percent,
                    )
                else:
                    logger.info(
                        "套餐 [%s](%s) 使用率: %.1f%%，状态正常",
                        plan_info.name,
                        plan_info.team_id,
                        plan_info.usage_percent,
                    )
            except Exception as e:
                logger.error("解析套餐详情失败: %s, 错误: %s", detail.get("TeamId", "unknown"), e)

        return alerts


class AlertCooldownManager:
    """告警冷却管理器，避免同一套餐同一级别重复告警"""

    def __init__(self, cooldown_minutes: int = 60):
        """
        Args:
            cooldown_minutes: 冷却时间（分钟）
        """
        self.cooldown_seconds = cooldown_minutes * 60
        # 存储 key: (team_id, level) -> last_alert_timestamp
        self._alert_history: Dict[tuple, float] = {}

    def should_alert(self, team_id: str, level: str) -> bool:
        """判断是否应该发送告警（是否在冷却期内）"""
        key = (team_id, level)
        now = time.time()
        last_alert = self._alert_history.get(key)

        if last_alert is None:
            self._alert_history[key] = now
            return True

        if now - last_alert >= self.cooldown_seconds:
            self._alert_history[key] = now
            return True

        logger.info(
            "套餐 %s 的 %s 级别告警在冷却期内，跳过", team_id, level
        )
        return False

    def reset(self, team_id: Optional[str] = None):
        """重置冷却记录"""
        if team_id is None:
            self._alert_history.clear()
        else:
            keys_to_remove = [k for k in self._alert_history if k[0] == team_id]
            for k in keys_to_remove:
                del self._alert_history[k]
