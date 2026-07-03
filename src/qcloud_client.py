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
        team_id: str,
        dimension: str = "apikey",
        metric_type: str = "tokens",
        start_time: str = "",
        end_time: str = "",
        period: str = "current_cycle",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        查询用量排行列表（按维度聚合的 Token 用量统计）

        Args:
            team_id: 套餐 ID
            dimension: 维度，取值: apikey / model / endpoint
            metric_type: 指标类型，取值: tokens / search
            start_time: 开始时间（RFC3339），留空使用 period
            end_time: 结束时间（RFC3339），留空使用 period
            period: 时间范围，取值: current_cycle / last_cycle / today / yesterday / last_7_days / last_30_days
            limit: 返回数量
            offset: 分页偏移

        Returns:
            用量排行数据，包含 TopList、TotalStats 等
        """
        try:
            import json

            params = {
                "Target": team_id,
                "Dimension": dimension,
                "MetricType": metric_type,
                "Period": period,
                "Limit": limit,
                "Offset": offset,
            }
            if start_time:
                params["StartTime"] = start_time
            if end_time:
                params["EndTime"] = end_time

            req = models.DescribeUsageRankListRequest()
            req.from_json_string(json.dumps(params))

            resp = self.client.DescribeUsageRankList(req)
            result = resp.to_json_string()
            logger.debug(
                "DescribeUsageRankList(%s, dim=%s) 响应: %s",
                team_id, dimension, result,
            )

            return json.loads(result)
        except TencentCloudSDKException as e:
            logger.error(
                "调用 DescribeUsageRankList(%s, dim=%s) 失败: %s",
                team_id, dimension, e,
            )
            raise
        except Exception as e:
            logger.error(
                "DescribeUsageRankList(%s, dim=%s) 未知异常: %s",
                team_id, dimension, e,
            )
            raise

    def get_usage_rank(
        self,
        team_id: str,
        dimension: str = "apikey",
        period: str = "current_cycle",
    ) -> List[Dict[str, Any]]:
        """
        获取指定维度的用量排行（自动分页）

        Args:
            team_id: 套餐 ID
            dimension: 维度，取值: apikey / model / endpoint
            period: 时间范围

        Returns:
            TopList 列表，每项包含 Key、Name、Stats 等
        """
        all_items: List[Dict[str, Any]] = []
        offset = 0
        limit = 100

        while True:
            data = self.describe_usage_rank_list(
                team_id=team_id,
                dimension=dimension,
                period=period,
                limit=limit,
                offset=offset,
            )
            top_list = data.get("TopList", [])
            total = data.get("Total", 0)

            all_items.extend(top_list)

            if len(all_items) >= total or len(top_list) == 0:
                break

            offset += limit

        logger.info(
            "套餐 %s 的 %s 维度用量排行: 共 %d 条",
            team_id, dimension, len(all_items),
        )
        return all_items
