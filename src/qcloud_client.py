#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯云 TokenHub API 客户端
封装 DescribeTokenPlanList 和 DescribeTokenPlan 接口调用
"""

import logging
from typing import Any, Dict, List, Optional

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tokenhub.v20260322 import tokenhub_client, models

logger = logging.getLogger(__name__)


class TokenHubClient:
    """腾讯云 TokenHub API 客户端封装"""

    def __init__(self, secret_id: str, secret_key: str, region: str = "ap-guangzhou"):
        """
        初始化 TokenHub 客户端

        Args:
            secret_id: 腾讯云 API SecretId
            secret_key: 腾讯云 API SecretKey
            region: 地域
        """
        self.credential = credential.Credential(secret_id, secret_key)
        self.region = region

        http_profile = HttpProfile()
        http_profile.endpoint = "tokenhub.tencentcloudapi.com"
        http_profile.reqTimeout = 30

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.signMethod = "TC3-HMAC-SHA256"

        self.client = tokenhub_client.TokenhubClient(
            self.credential, self.region, client_profile
        )

    def describe_token_plan_list(
        self, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """
        查询 TokenPlan 套餐列表

        Args:
            offset: 分页偏移量
            limit: 分页返回数量，最大 100

        Returns:
            包含 TokenPlanSet 和 TotalCount 的字典
        """
        try:
            req = models.DescribeTokenPlanListRequest()
            req.from_json_string(
                '{"Offset": %d, "Limit": %d}' % (offset, limit)
            )

            resp = self.client.DescribeTokenPlanList(req)
            result = resp.to_json_string()
            logger.debug("DescribeTokenPlanList 响应: %s", result)

            import json
            data = json.loads(result)
            return data
        except TencentCloudSDKException as e:
            logger.error("调用 DescribeTokenPlanList 失败: %s", e)
            raise
        except Exception as e:
            logger.error("DescribeTokenPlanList 未知异常: %s", e)
            raise

    def describe_token_plan(self, team_id: str) -> Dict[str, Any]:
        """
        查询指定 TokenPlan 套餐详情（含 Token 用量明细）

        Args:
            team_id: 套餐 ID

        Returns:
            套餐详情字典，包含 PackageInfo 和 TokenSummary
        """
        try:
            req = models.DescribeTokenPlanRequest()
            req.from_json_string('{"TeamId": "%s"}' % team_id)

            resp = self.client.DescribeTokenPlan(req)
            result = resp.to_json_string()
            logger.debug("DescribeTokenPlan(%s) 响应: %s", team_id, result)

            import json
            data = json.loads(result)
            return data
        except TencentCloudSDKException as e:
            logger.error("调用 DescribeTokenPlan(%s) 失败: %s", team_id, e)
            raise
        except Exception as e:
            logger.error("DescribeTokenPlan(%s) 未知异常: %s", team_id, e)
            raise

    def get_all_plans(self) -> List[Dict[str, Any]]:
        """
        获取所有 TokenPlan 套餐列表（自动分页）

        Returns:
            套餐列表
        """
        all_plans: List[Dict[str, Any]] = []
        offset = 0
        limit = 100

        while True:
            data = self.describe_token_plan_list(offset=offset, limit=limit)
            plans = data.get("TokenPlanSet", [])
            total_count = data.get("TotalCount", 0)

            all_plans.extend(plans)

            if len(all_plans) >= total_count or len(plans) == 0:
                break

            offset += limit

        logger.info("共获取到 %d 个套餐", len(all_plans))
        return all_plans

    def get_plan_details(self, team_id: str) -> Optional[Dict[str, Any]]:
        """
        获取套餐详情（含额度用量信息）

        Args:
            team_id: 套餐 ID

        Returns:
            套餐详情字典，失败返回 None
        """
        try:
            return self.describe_token_plan(team_id)
        except Exception as e:
            logger.error("获取套餐 %s 详情失败: %s", team_id, e)
            return None

    def describe_usage_rank_list(
        self,
        dimension: str = "apikey",
        metric_type: str = "tokens",
        start_time: str = "",
        end_time: str = "",
        period: int = 86400,
        target: str = "",
        show_all: bool = True,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        查询用量排行列表（按维度聚合的 Token 用量统计）

        Args:
            dimension: 统计维度，取值: apikey / model / endpoint
            metric_type: 指标族，取值: tokens / search
            start_time: 起始时间（RFC3339，闭区间）
            end_time: 结束时间（RFC3339，开区间），与 StartTime 跨度最大 90 天
            period: 统计粒度（秒），取值: 60 / 300 / 3600 / 86400
                    必须不小于跨度对应下限：
                    跨度 ≤ 1 天 → 60；1~5 天 → 300；5~10 天 → 3600；> 10 天 → 86400
                    仅 ShowAll=false 时使用
            target: 维度过滤值，空字符串表示查询全部对象
            show_all: true 返回全量对象（不含 Series），false 分页返回（每页 10 条，含 Series）
            offset: 翻页起点，仅 ShowAll=false 时有效

        Returns:
            用量排行数据，包含 TopList、TotalStats 等
        """
        try:
            import json

            params = {
                "Dimension": dimension,
                "MetricType": metric_type,
                "StartTime": start_time,
                "EndTime": end_time,
                "Period": period,
                "Target": target,
                "ShowAll": show_all,
                "Offset": offset,
            }

            req = models.DescribeUsageRankListRequest()
            req.from_json_string(json.dumps(params))

            resp = self.client.DescribeUsageRankList(req)
            result = resp.to_json_string()
            logger.debug(
                "DescribeUsageRankList(dim=%s) 响应: %s",
                dimension, result,
            )

            return json.loads(result)
        except TencentCloudSDKException as e:
            logger.error(
                "调用 DescribeUsageRankList(dim=%s) 失败: %s",
                dimension, e,
            )
            raise
        except Exception as e:
            logger.error(
                "DescribeUsageRankList(dim=%s) 未知异常: %s",
                dimension, e,
            )
            raise

    @staticmethod
    def _resolve_time_range(period: str) -> tuple:
        """
        将 period 字符串解析为 (start_time, end_time, granularity) 三元组

        支持以下格式：
          - 固定标识: today / yesterday / last_7_days / last_30_days / current_cycle
          - 相对时长: last_Nh (如 last_1h, last_6h, last_12h)
          - 相对天数: last_Nd (如 last_1d, last_3d, last_14d)

        Args:
            period: 时间范围标识

        Returns:
            (start_time, end_time, granularity)
            - start_time / end_time: RFC3339 格式字符串
            - granularity: 统计粒度（秒），取值 60/300/3600/86400
              跨度 ≤ 1 天 → 60；1~5 天 → 300；5~10 天 → 3600；> 10 天 → 86400
        """
        import re
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)

        def _fmt(dt: datetime) -> str:
            return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        def _granularity(start: datetime, end: datetime) -> int:
            """根据时间跨度返回最小允许的统计粒度（秒）"""
            span_seconds = (end - start).total_seconds()
            span_days = span_seconds / 86400
            if span_days <= 1:
                return 60
            elif span_days <= 5:
                return 300
            elif span_days <= 10:
                return 3600
            else:
                return 86400

        # 相对小时: last_Nh (如 last_1h, last_6h)
        m = re.match(r"^last_(\d+)h$", period)
        if m:
            hours = int(m.group(1))
            start = now - timedelta(hours=hours)
            return _fmt(start), _fmt(now), _granularity(start, now)

        # 相对天数: last_Nd (如 last_1d, last_3d)
        m = re.match(r"^last_(\d+)d$", period)
        if m:
            days = int(m.group(1))
            start = now - timedelta(days=days)
            return _fmt(start), _fmt(now), _granularity(start, now)

        # 固定标识
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return _fmt(start), _fmt(now), _granularity(start, now)
        elif period == "yesterday":
            start = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(days=1)
            return _fmt(start), _fmt(end), _granularity(start, end)
        elif period == "last_7_days":
            start = (now - timedelta(days=7)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return _fmt(start), _fmt(now), _granularity(start, now)
        elif period == "last_30_days":
            start = (now - timedelta(days=30)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return _fmt(start), _fmt(now), _granularity(start, now)
        else:
            # current_cycle / 未知值，默认取最近 30 天
            start = (now - timedelta(days=30)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return _fmt(start), _fmt(now), _granularity(start, now)

    def get_usage_rank(
        self,
        dimension: str = "apikey",
        period: str = "current_cycle",
    ) -> List[Dict[str, Any]]:
        """
        获取指定维度的用量排行（全量返回）

        使用 ShowAll=true 一次性返回全量对象，不返回 Series 时序点。
        我们只需要 Stats 聚合值，不需要时序曲线。

        Args:
            dimension: 统计维度，取值: apikey / model / endpoint
            period: 时间范围，支持: today / yesterday / last_7_days / last_30_days /
                    current_cycle / last_Nh / last_Nd

        Returns:
            TopList 列表，每项包含 Key、Name、Stats 等
        """
        start_time, end_time, granularity = self._resolve_time_range(period)

        data = self.describe_usage_rank_list(
            dimension=dimension,
            start_time=start_time,
            end_time=end_time,
            period=granularity,
            show_all=True,
        )
        top_list = data.get("TopList", [])

        logger.info(
            "%s 维度用量排行(%s~%s, 粒度%ds): 共 %d 条",
            dimension, start_time, end_time, granularity, len(top_list),
        )
        return top_list
