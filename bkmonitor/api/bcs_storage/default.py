import abc
import copy
import logging
from urllib.parse import urljoin

import six
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource.contrib.api import APIResource

logger = logging.getLogger("bcs_storage")


class BcsStorageBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    module_name = "bcs-storage"

    # BCS目前是非蓝鲸标准的返回格式，所以需要兼容
    IS_STANDARD_FORMAT = False

    def get_request_url(self, validated_request_data):
        request_url = self.base_url.rstrip("/") + "/" + self.action.lstrip("/")
        # BCS_DEBUG_STORAGE_ADAPTER 需要设置为 False，而且不需要通过集群进行判断 debug 和 prod 环境
        if settings.BCS_DEBUG_STORAGE_ADAPTER:
            # 特殊处理上云环境下两套bcs storage自动适配，其他环境无此问题，BCS storage合并需后移除这三行兼容逻辑
            cluster_id = validated_request_data.get("cluster_id")
            if request_url.find("prod-bcs-api") > -1 and cluster_id.find("BCS-K8S-2") > -1:
                request_url = request_url.replace("prod-bcs-api", "debug-bcs-api")

        # 添加field选择字段
        field = validated_request_data.get("field")
        if field:
            request_url = f"{request_url}&field={field}"

        url = request_url.format(**validated_request_data)
        validated_request_data.clear()
        return url

    def get_headers(self):
        headers = super().get_headers()
        headers["Authorization"] = f"Bearer {settings.BCS_API_GATEWAY_TOKEN}"
        return headers

    def render_response_data(self, validated_request_data, response_data):
        data = []
        for item in response_data.get("data", []):
            try:
                data.append(item.get("data", {}))
            except Exception as e:
                logger.error(e)
        return data


class FetchPageResource(BcsStorageBaseResource):
    base_url = urljoin(
        f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
        "/bcsapi/v4/storage/k8s/dynamic/all_resources/clusters",
    )
    action = "{cluster_id}/{type}?offset={offset}&limit={limit}"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = serializers.CharField(label="租户ID")
        cluster_id = serializers.CharField(label="集群ID")
        type = serializers.CharField(label="资源类型")
        field = serializers.CharField(label="字段选择器", required=False, allow_null=True)
        offset = serializers.IntegerField(label="偏移量")
        limit = serializers.IntegerField(label="每页数量")


class FetchResource(BcsStorageBaseResource):
    cache_type = CacheType.BCS
    base_url = urljoin(
        f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
        "/bcsapi/v4/storage/k8s/dynamic/all_resources/clusters",
    )
    action = "{cluster_id}/{type}?offset={offset}&limit={limit}"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = serializers.CharField(label="租户ID")
        cluster_id = serializers.CharField(label="集群ID")
        type = serializers.CharField(label="资源类型")
        field = serializers.CharField(label="字段选择器", required=False, allow_null=True)

    def perform_request(self, params: dict):
        data = []
        offset = 0
        limit = settings.BCS_STORAGE_PAGE_SIZE
        while True:
            params = copy.deepcopy(params)
            params["offset"] = offset
            params["limit"] = limit
            data_per_page = super().perform_request(params)
            data.extend(data_per_page)
            data_len = len(data_per_page)
            # 通过判断返回结果的数据判断是否需要获取下一页的数据
            if data_len == limit:
                offset += limit
                params["offset"] = offset
                continue
            break

        return data


def fetch_iterator(bk_tenant_id: str, cluster_id: str, resource_type: str, field: str | None = None):
    """
    获取bcs资源的迭代器
    """
    offset = 0
    limit = settings.BCS_STORAGE_PAGE_SIZE
    while True:
        data_per_page = FetchPageResource().perform_request(
            {
                "bk_tenant_id": bk_tenant_id,
                "cluster_id": cluster_id,
                "type": resource_type,
                "offset": offset,
                "limit": limit,
                "field": field,
            }
        )
        yield from data_per_page

        data_len = len(data_per_page)
        # 通过判断返回结果的数据判断是否需要获取下一页的数据
        if data_len == limit:
            offset += limit
            continue
        break
