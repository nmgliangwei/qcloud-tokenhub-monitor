#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prometheus 指标模块
定义并暴露 TokenPlan 额度监控相关指标
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    start_http_server,
)

from monitor import PlanUsageInfo

logger = logging.getLogger(__name__)


class MetricsManager:
    """Prometheus 指标管理器"""

    def __init__(self, registry: CollectorRegistry = None):
        self.registry = registry or CollectorRegistry()

        # --- 套餐额度指标 ---
        self.plan_usage_percent = Gauge(
            "tokenhub_plan_usage_percent",
            "套餐额度使用率（百分比）",
            ["team_id", "name", "product_type"],
            registry=self.registry,
        )
        self.plan_total_quota = Gauge(
            "tokenhub_plan_total_quota",
            "套餐总额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )
        self.plan_total_used = Gauge(
            "tokenhub_plan_total_used",
            "套餐已使用额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )
        self.plan_remaining = Gauge(
            "tokenhub_plan_remaining",
            "套餐剩余额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )
        self.plan_cycle_quota = Gauge(
            "tokenhub_plan_cycle_quota",
            "套餐当期额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )
        self.plan_remain_cycles = Gauge(
            "tokenhub_plan_remain_cycles",
            "套餐剩余周期数",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_current_cycle = Gauge(
            "tokenhub_plan_current_cycle",
            "套餐当前周期",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_total_cycles = Gauge(
            "tokenhub_plan_total_cycles",
            "套餐总周期数",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_status = Gauge(
            "tokenhub_plan_status",
            "套餐状态（1=正常, 0=异常/关停）",
            ["team_id", "name", "status", "stop_reason"],
            registry=self.registry,
        )
        self.plan_exclusive_allocated = Gauge(
            "tokenhub_plan_exclusive_allocated",
            "独占池已分配额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )
        self.plan_exclusive_used = Gauge(
            "tokenhub_plan_exclusive_used",
            "独占池已使用额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )
        self.plan_shared_pool = Gauge(
            "tokenhub_plan_shared_pool",
            "共享池总额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )
        self.plan_shared_used = Gauge(
            "tokenhub_plan_shared_used",
            "共享池已使用额度",
            ["team_id", "name", "unit"],
            registry=self.registry,
        )

        # --- 套餐时间指标 ---
        self.plan_expire_timestamp = Gauge(
            "tokenhub_plan_expire_timestamp",
            "套餐到期时间（Unix 时间戳）",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_start_timestamp = Gauge(
            "tokenhub_plan_start_timestamp",
            "套餐开始时间（Unix 时间戳）",
            ["team_id", "name"],
            registry=self.registry,
        )

        # --- Token 使用明细指标 ---
        self.plan_token_usage = Gauge(
            "tokenhub_plan_token_usage",
            "Token 使用量（按计费项维度，当前周期累计）",
            ["team_id", "name", "billing_item"],
            registry=self.registry,
        )
        self.plan_token_input = Gauge(
            "tokenhub_plan_token_input",
            "输入 Token 用量（当前周期累计）",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_token_output = Gauge(
            "tokenhub_plan_token_output",
            "输出 Token 用量（当前周期累计）",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_token_cache = Gauge(
            "tokenhub_plan_token_cache",
            "缓存 Token 用量（当前周期累计）",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_token_total = Gauge(
            "tokenhub_plan_token_total",
            "总 Token 用量（输入+输出+缓存，当前周期累计）",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_call_count = Gauge(
            "tokenhub_plan_call_count",
            "API 调用次数（当前周期累计）",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_cache_hit_ratio = Gauge(
            "tokenhub_plan_cache_hit_ratio",
            "缓存命中率（缓存Token / (输入Token+缓存Token)）",
            ["team_id", "name"],
            registry=self.registry,
        )

        # --- 计费周期指标 ---
        self.plan_cycle_seq = Gauge(
            "tokenhub_plan_cycle_seq",
            "当前计费周期序号",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_cycle_start_timestamp = Gauge(
            "tokenhub_plan_cycle_start_timestamp",
            "当前计费周期开始时间（Unix 时间戳）",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_cycle_end_timestamp = Gauge(
            "tokenhub_plan_cycle_end_timestamp",
            "当前计费周期结束时间（Unix 时间戳）",
            ["team_id", "name"],
            registry=self.registry,
        )

        # --- API Key 指标 ---
        self.plan_api_key_count = Gauge(
            "tokenhub_plan_api_key_count",
            "已创建 API Key 数量",
            ["team_id", "name"],
            registry=self.registry,
        )
        self.plan_api_key_max = Gauge(
            "tokenhub_plan_api_key_max",
            "API Key 上限",
            ["team_id", "name"],
            registry=self.registry,
        )

        # --- 按维度聚合的 Token 用量指标（DescribeUsageRankList） ---
        # 维度: apikey / model / endpoint
        self.usage_input_token = Gauge(
            "tokenhub_usage_input_token",
            "按维度聚合的输入 Token 用量",
            ["team_id", "plan_name", "dimension", "key", "name"],
            registry=self.registry,
        )
        self.usage_output_token = Gauge(
            "tokenhub_usage_output_token",
            "按维度聚合的输出 Token 用量",
            ["team_id", "plan_name", "dimension", "key", "name"],
            registry=self.registry,
        )
        self.usage_cache_token = Gauge(
            "tokenhub_usage_cache_token",
            "按维度聚合的缓存 Token 用量",
            ["team_id", "plan_name", "dimension", "key", "name"],
            registry=self.registry,
        )
        self.usage_total_token = Gauge(
            "tokenhub_usage_total_token",
            "按维度聚合的总 Token 用量",
            ["team_id", "plan_name", "dimension", "key", "name"],
            registry=self.registry,
        )
        self.usage_search_request_count = Gauge(
            "tokenhub_usage_search_request_count",
            "按维度聚合的搜索请求数",
            ["team_id", "plan_name", "dimension", "key", "name"],
            registry=self.registry,
        )
        self.usage_search_count = Gauge(
            "tokenhub_usage_search_count",
            "按维度聚合的搜索引擎调用次数",
            ["team_id", "plan_name", "dimension", "key", "name"],
            registry=self.registry,
        )

        # --- 检查指标 ---
        self.check_total = Counter(
            "tokenhub_check_total",
            "额度检查执行总次数",
            registry=self.registry,
        )
        self.check_errors = Counter(
            "tokenhub_check_errors_total",
            "额度检查执行失败次数",
            registry=self.registry,
        )
        self.check_duration = Gauge(
            "tokenhub_check_duration_seconds",
            "最近一次额度检查耗时（秒）",
            registry=self.registry,
        )
        self.plans_total = Gauge(
            "tokenhub_plans_total",
            "监控的套餐总数",
            registry=self.registry,
        )

        # 已记录的 team_id 集合，用于清理过期指标
        self._recorded_plans: set = set()
        # 已记录的维度项集合，key: (team_id, dimension), value: set of item_key
        self._recorded_usage: Dict[tuple, set] = {}

    def update_plan_metrics(self, plans: List[PlanUsageInfo]):
        """更新套餐相关指标"""
        current_plans: set = set()

        for plan in plans:
            current_plans.add(plan.team_id)

            self.plan_usage_percent.labels(
                team_id=plan.team_id,
                name=plan.name,
                product_type=plan.product_type,
            ).set(plan.usage_percent)

            self.plan_total_quota.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.total_quota)

            self.plan_total_used.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.total_used)

            self.plan_remaining.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.remaining)

            self.plan_cycle_quota.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.cycle_quota)

            self.plan_remain_cycles.labels(
                team_id=plan.team_id, name=plan.name
            ).set(plan.remain_cycles)

            self.plan_current_cycle.labels(
                team_id=plan.team_id, name=plan.name
            ).set(plan.current_cycle)

            self.plan_total_cycles.labels(
                team_id=plan.team_id, name=plan.name
            ).set(plan.total_cycles)

            # 状态：enable 且无 stop_reason 为正常(1)，其余为异常(0)
            is_normal = 1 if (plan.status == "enable" and not plan.stop_reason) else 0
            self.plan_status.labels(
                team_id=plan.team_id,
                name=plan.name,
                status=plan.status,
                stop_reason=plan.stop_reason or "none",
            ).set(is_normal)

            self.plan_exclusive_allocated.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.exclusive_allocated)

            self.plan_exclusive_used.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.exclusive_used)

            self.plan_shared_pool.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.shared_pool)

            self.plan_shared_used.labels(
                team_id=plan.team_id, name=plan.name, unit=plan.unit
            ).set(plan.shared_used)

            # 到期/开始时间戳
            expire_ts = self._parse_timestamp(plan.expire_time)
            if expire_ts:
                self.plan_expire_timestamp.labels(
                    team_id=plan.team_id, name=plan.name
                ).set(expire_ts)

            start_ts = self._parse_timestamp(plan.start_time)
            if start_ts:
                self.plan_start_timestamp.labels(
                    team_id=plan.team_id, name=plan.name
                ).set(start_ts)

            # Token 使用明细
            token_input = 0.0
            token_output = 0.0
            token_cache = 0.0
            call_count = 0.0
            for item in plan.token_billing_items:
                billing_item = item.get("billing_item", "")
                total_qty = item.get("total_qty", 0.0)
                if not billing_item:
                    continue

                # 通用指标（按 billing_item 标签）
                self.plan_token_usage.labels(
                    team_id=plan.team_id,
                    name=plan.name,
                    billing_item=billing_item,
                ).set(total_qty)

                # 分类指标
                if billing_item == "input":
                    token_input = total_qty
                elif billing_item == "output":
                    token_output = total_qty
                elif billing_item == "cache":
                    token_cache = total_qty
                elif billing_item == "call_count":
                    call_count = total_qty

            self.plan_token_input.labels(
                team_id=plan.team_id, name=plan.name
            ).set(token_input)
            self.plan_token_output.labels(
                team_id=plan.team_id, name=plan.name
            ).set(token_output)
            self.plan_token_cache.labels(
                team_id=plan.team_id, name=plan.name
            ).set(token_cache)
            self.plan_token_total.labels(
                team_id=plan.team_id, name=plan.name
            ).set(token_input + token_output + token_cache)
            self.plan_call_count.labels(
                team_id=plan.team_id, name=plan.name
            ).set(call_count)

            # 缓存命中率 = cache / (input + cache)
            input_plus_cache = token_input + token_cache
            cache_ratio = (token_cache / input_plus_cache * 100) if input_plus_cache > 0 else 0.0
            self.plan_cache_hit_ratio.labels(
                team_id=plan.team_id, name=plan.name
            ).set(cache_ratio)

            # 计费周期信息
            self.plan_cycle_seq.labels(
                team_id=plan.team_id, name=plan.name
            ).set(plan.cycle_seq)

            cycle_start_ts = self._parse_timestamp(plan.cycle_start_time)
            if cycle_start_ts:
                self.plan_cycle_start_timestamp.labels(
                    team_id=plan.team_id, name=plan.name
                ).set(cycle_start_ts)

            cycle_end_ts = self._parse_timestamp(plan.cycle_end_time)
            if cycle_end_ts:
                self.plan_cycle_end_timestamp.labels(
                    team_id=plan.team_id, name=plan.name
                ).set(cycle_end_ts)

            # API Key 数量
            self.plan_api_key_count.labels(
                team_id=plan.team_id, name=plan.name
            ).set(plan.api_key_count)
            self.plan_api_key_max.labels(
                team_id=plan.team_id, name=plan.name
            ).set(plan.api_key_max)

        # 清理已不存在的套餐指标
        stale_plans = self._recorded_plans - current_plans
        for team_id in stale_plans:
            logger.debug("清理已删除套餐的指标: %s", team_id)
            self._remove_plan_metrics(team_id)

        self._recorded_plans = current_plans
        self.plans_total.set(len(plans))

    def update_usage_rank_metrics(
        self,
        team_id: str,
        plan_name: str,
        dimension: str,
        rank_items: List[Dict[str, Any]],
    ):
        """
        更新按维度聚合的 Token 用量指标

        Args:
            team_id: 套餐 ID
            plan_name: 套餐名称
            dimension: 维度 (apikey / model / endpoint)
            rank_items: DescribeUsageRankList 返回的 TopList
        """
        current_keys: set = set()

        def _to_float(val) -> float:
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        for item in rank_items:
            key = item.get("Key", "")
            name = item.get("Name", key)
            if not key:
                continue

            current_keys.add(key)
            stats = item.get("Stats") or {}

            labels = dict(
                team_id=team_id,
                plan_name=plan_name,
                dimension=dimension,
                key=key,
                name=name,
            )

            self.usage_input_token.labels(**labels).set(
                _to_float(stats.get("InputTotalToken"))
            )
            self.usage_output_token.labels(**labels).set(
                _to_float(stats.get("OutputTotalToken"))
            )
            self.usage_cache_token.labels(**labels).set(
                _to_float(stats.get("CacheTotalToken"))
            )
            self.usage_total_token.labels(**labels).set(
                _to_float(stats.get("TotalToken"))
            )
            self.usage_search_request_count.labels(**labels).set(
                _to_float(stats.get("SearchRequestCount"))
            )
            self.usage_search_count.labels(**labels).set(
                _to_float(stats.get("SearchCount"))
            )

        # 清理已不存在的维度项指标
        cache_key = (team_id, dimension)
        prev_keys = self._recorded_usage.get(cache_key, set())
        stale_keys = prev_keys - current_keys
        for key in stale_keys:
            self._remove_usage_metrics(team_id, plan_name, dimension, key)

        self._recorded_usage[cache_key] = current_keys

    def record_check(self, duration: float, success: bool):
        """记录一次检查的指标"""
        self.check_total.inc()
        self.check_duration.set(duration)
        if not success:
            self.check_errors.inc()

    @staticmethod
    def _parse_timestamp(time_str: str) -> float:
        """将 ISO 8601 时间字符串转为 Unix 时间戳"""
        if not time_str:
            return 0.0
        try:
            # 兼容 "2026-04-01T00:00:00Z" 和 "2026-04-01T00:00:00+08:00" 格式
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            logger.debug("无法解析时间字符串: %s", time_str)
            return 0.0

    def _remove_plan_metrics(self, team_id: str):
        """移除指定套餐的所有指标"""
        for metric in [
            self.plan_usage_percent,
            self.plan_total_quota,
            self.plan_total_used,
            self.plan_remaining,
            self.plan_cycle_quota,
            self.plan_remain_cycles,
            self.plan_current_cycle,
            self.plan_total_cycles,
            self.plan_status,
            self.plan_exclusive_allocated,
            self.plan_exclusive_used,
            self.plan_shared_pool,
            self.plan_shared_used,
            self.plan_expire_timestamp,
            self.plan_start_timestamp,
            self.plan_token_usage,
            self.plan_token_input,
            self.plan_token_output,
            self.plan_token_cache,
            self.plan_token_total,
            self.plan_call_count,
            self.plan_cache_hit_ratio,
            self.plan_cycle_seq,
            self.plan_cycle_start_timestamp,
            self.plan_cycle_end_timestamp,
            self.plan_api_key_count,
            self.plan_api_key_max,
        ]:
            labels_to_remove = []
            for label_tuple in metric.collect():
                for sample in label_tuple.samples:
                    if sample.labels.get("team_id") == team_id:
                        label_values = tuple(
                            sample.labels.get(name, "") for name in metric._labelnames
                        )
                        labels_to_remove.append(label_values)

            for label_values in labels_to_remove:
                try:
                    metric.remove(*label_values)
                except KeyError:
                    pass

        # 同时清理该套餐的按维度聚合用量指标
        for metric in [
            self.usage_input_token,
            self.usage_output_token,
            self.usage_cache_token,
            self.usage_total_token,
            self.usage_search_request_count,
            self.usage_search_count,
        ]:
            labels_to_remove = []
            for label_tuple in metric.collect():
                for sample in label_tuple.samples:
                    if sample.labels.get("team_id") == team_id:
                        label_values = tuple(
                            sample.labels.get(name, "")
                            for name in metric._labelnames
                        )
                        labels_to_remove.append(label_values)

            for label_values in labels_to_remove:
                try:
                    metric.remove(*label_values)
                except KeyError:
                    pass

        # 清理已记录的维度项缓存
        keys_to_del = [k for k in self._recorded_usage if k[0] == team_id]
        for k in keys_to_del:
            del self._recorded_usage[k]

    def _remove_usage_metrics(
        self, team_id: str, plan_name: str, dimension: str, key: str
    ):
        """移除指定维度项的用量指标"""
        for metric in [
            self.usage_input_token,
            self.usage_output_token,
            self.usage_cache_token,
            self.usage_total_token,
            self.usage_search_request_count,
            self.usage_search_count,
        ]:
            labels_to_remove = []
            for label_tuple in metric.collect():
                for sample in label_tuple.samples:
                    if (
                        sample.labels.get("team_id") == team_id
                        and sample.labels.get("dimension") == dimension
                        and sample.labels.get("key") == key
                    ):
                        label_values = tuple(
                            sample.labels.get(name, "")
                            for name in metric._labelnames
                        )
                        labels_to_remove.append(label_values)

            for label_values in labels_to_remove:
                try:
                    metric.remove(*label_values)
                except KeyError:
                    pass

    def start_server(self, port: int, addr: str = "0.0.0.0"):
        """启动 Prometheus metrics HTTP 服务"""
        start_http_server(port, addr=addr, registry=self.registry)
        logger.info("Prometheus metrics 服务已启动，监听 %s:%d/metrics", addr, port)
