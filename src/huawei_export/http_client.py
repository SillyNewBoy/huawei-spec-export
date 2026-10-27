"""HTTP 客户端：华为商城 VMALL 与华为消费者官网共用基础设施。"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests


class VmallClientError(RuntimeError):
    """Base client error."""


class CsrftokenExpiredError(VmallClientError):
    """Raised when the server rejects the csrf token."""


class RateLimitError(VmallClientError):
    """Raised when the server rate-limits the client."""


class VmallClient:
    """华为商城（vmall.com）HTTP 客户端，内置 CSRF、限速与重试。"""

    BASE_URL = "https://www.vmall.com"
    OPENAPI_URL = "https://openapi.vmall.com"
    SEARCH_PATH = "/mcp/v1/search/queryPrd"
    CSRF_PATH = "/csrftoken.js"
    NEXT_DATA_PATTERN = re.compile(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    )
    CSRF_PATTERN = re.compile(r'csrftoken\s*=\s*"([^"]+)"')

    def __init__(
        self,
        *,
        timeout: int = 20,
        session: requests.Session | None = None,
        user_agent: str | None = None,
        min_request_interval: float = 0.8,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        logger: logging.Logger | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent or self._default_user_agent(),
                "Accept": "application/json, text/plain, */*",
            }
        )
        self._csrf_token: str | None = None
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logger or logging.getLogger(__name__)
        self._last_request_ts = 0.0

    def _default_user_agent(self) -> str:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )

    def _ensure_csrf(self) -> str:
        if self._csrf_token:
            return self._csrf_token

        self.logger.info("Initializing VMALL session and requesting csrf token")
        self._request("GET", self.BASE_URL, use_retry=False)
        response = self._request(
            "GET",
            f"{self.OPENAPI_URL}{self.CSRF_PATH}",
            use_retry=False,
        )
        match = self.CSRF_PATTERN.search(response.text)
        if not match:
            raise RuntimeError("Unable to extract CSRF token from VMALL response.")
        self._csrf_token = match.group(1)
        self.logger.info("Fetched csrf token successfully")
        return self._csrf_token

    def _reset_csrf(self) -> None:
        self._csrf_token = None

    def _search_headers(self) -> dict[str, str]:
        token = self._ensure_csrf()
        return {
            "CsrfToken": token,
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < self.min_request_interval:
            sleep_for = self.min_request_interval - elapsed
            self.logger.debug("Sleeping %.2fs to respect request interval", sleep_for)
            time.sleep(sleep_for)

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        use_retry: bool = True,
    ) -> requests.Response:
        attempts = self.max_retries if use_retry else 1

        for attempt in range(1, attempts + 1):
            self._throttle()
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    timeout=self.timeout,
                )
                self._last_request_ts = time.monotonic()
                self._raise_for_response(response)
                return response
            except CsrftokenExpiredError:
                self.logger.warning("Csrf token expired, refreshing token and retrying")
                self._reset_csrf()
                if attempt >= attempts:
                    raise
            except (RateLimitError, requests.RequestException, VmallClientError) as exc:
                if attempt >= attempts:
                    raise
                sleep_for = self.backoff_factor * attempt
                self.logger.warning(
                    "Request failed on attempt %s/%s: %s. Retrying in %.2fs",
                    attempt,
                    attempts,
                    exc,
                    sleep_for,
                )
                time.sleep(sleep_for)

        raise VmallClientError(f"Request failed unexpectedly: {method} {url}")

    def _raise_for_response(self, response: requests.Response) -> None:
        if response.status_code in {403, 429}:
            raise RateLimitError(f"HTTP {response.status_code} for {response.url}")
        response.raise_for_status()
        self._raise_for_body(response)

    def _raise_for_body(self, response: requests.Response) -> None:
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return
        try:
            data = response.json()
        except ValueError:
            return

        code = str(data.get("code", ""))
        info = str(data.get("info", "") or data.get("msg", ""))
        result_code = str(data.get("resultCode", ""))

        if code == "200917" or "csrftoken" in info.lower():
            raise CsrftokenExpiredError(info or code)
        if code in {"429", "403"} or result_code in {"429", "403"}:
            raise RateLimitError(info or code or result_code)

    def search_products(
        self,
        *,
        keyword: str,
        category_id: int | None = None,
        page_size: int = 20,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        sid = ""
        search_id: str | None = None

        for page_num in range(1, max_pages + 1):
            self.logger.info(
                "Searching products: keyword=%s category_id=%s page=%s page_size=%s",
                keyword,
                category_id,
                page_num,
                page_size,
            )
            payload: dict[str, Any] = {
                "keyword": keyword,
                "pageNum": str(page_num),
                "pageSize": str(page_size),
                "portal": "1",
                "lang": "zh_CN",
                "country": "CN",
                "sid": sid,
                "searchFlag": "0",
            }
            if category_id is not None:
                payload["categoryId"] = str(category_id)
            if search_id:
                payload["searchId"] = search_id

            response = self._request(
                "POST",
                f"{self.OPENAPI_URL}{self.SEARCH_PATH}",
                headers=self._search_headers(),
                json_data=payload,
            )
            data = response.json()
            if not data.get("success"):
                raise RuntimeError(
                    f"VMALL search failed for keyword={keyword!r}: {json.dumps(data, ensure_ascii=False)}"
                )

            page_items = data.get("resultList") or []
            if not page_items:
                self.logger.info("Search returned no items, stopping pagination")
                break

            for item in page_items:
                product_id = item.get("productId")
                sku_code = item.get("skuCode")
                product_name = item.get("name")
                sku_name = item.get("skuName")
                if not all([product_id, sku_code, product_name, sku_name]):
                    continue
                results.append(
                    {
                        "product_id": str(product_id),
                        "product_name": str(product_name).strip(),
                        "sku_code": str(sku_code),
                        "sku_name": str(sku_name).strip(),
                        "category_code": item.get("thirdLevelPhysicalCategoryCode"),
                        "product_url": f"{self.BASE_URL}/product/{product_id}.html",
                    }
                )

            sid = data.get("sid") or sid
            search_id = data.get("searchId") or search_id
            total_count = int(data.get("totalCount") or 0)
            self.logger.info(
                "Fetched search page successfully: page=%s items=%s total=%s",
                page_num,
                len(page_items),
                total_count,
            )
            if page_num * page_size >= total_count:
                break

        return results

    def fetch_product_next_data(self, product_id: str) -> dict[str, Any]:
        self.logger.info("Fetching product detail page: product_id=%s", product_id)
        response = self._request(
            "GET",
            f"{self.BASE_URL}/product/{product_id}.html",
            headers={"Referer": f"{self.BASE_URL}/"},
        )
        match = self.NEXT_DATA_PATTERN.search(response.text)
        if not match:
            raise RuntimeError(f"Unable to locate __NEXT_DATA__ for product {product_id}.")
        return json.loads(match.group(1))


class ConsumerClientError(RuntimeError):
    """Base consumer-site client error."""


class ConsumerRateLimitError(ConsumerClientError):
    """Raised when the consumer site rate-limits the client."""


class ConsumerHttpError(ConsumerClientError):
    """Raised for non-retryable HTTP errors."""

    def __init__(self, status_code: int, url: str) -> None:
        super().__init__(f"HTTP {status_code} for {url}")
        self.status_code = status_code
        self.url = url


class ConsumerClient:
    """华为消费者官网（consumer.huawei.com）HTTP 客户端。

    官网页面为服务端渲染静态 HTML，普通 GET 即可，客户端只负责限速与重试。
    """

    BASE_URL_TEMPLATE = "https://consumer.huawei.com/{region}/"

    def __init__(
        self,
        *,
        region: str = "cn",
        timeout: int = 30,
        session: requests.Session | None = None,
        user_agent: str | None = None,
        min_request_interval: float = 0.8,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        logger: logging.Logger | None = None,
    ) -> None:
        self.region = region.strip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent or self._default_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logger or logging.getLogger(__name__)
        self._last_request_ts = 0.0

    @property
    def base_url(self) -> str:
        return self.BASE_URL_TEMPLATE.format(region=self.region)

    def _default_user_agent(self) -> str:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < self.min_request_interval:
            sleep_for = self.min_request_interval - elapsed
            self.logger.debug("Sleeping %.2fs to respect request interval", sleep_for)
            time.sleep(sleep_for)

    def fetch_text(self, url: str) -> str:
        """Fetch a URL and return the response text with retry/throttling."""
        return self.fetch_response(url).text

    def fetch_response(self, url: str) -> requests.Response:
        """Fetch a URL and return the final response with retry/throttling.

        Redirects are followed; inspect ``response.url`` for the final URL.
        """
        attempts = max(1, self.max_retries)
        for attempt in range(1, attempts + 1):
            self._throttle()
            try:
                response = self.session.get(url, timeout=self.timeout)
                self._last_request_ts = time.monotonic()
            except requests.RequestException as exc:
                if attempt >= attempts:
                    raise ConsumerClientError(f"Request failed: {url}: {exc}") from exc
                sleep_for = self.backoff_factor * attempt
                self.logger.warning(
                    "Request error on attempt %s/%s for %s: %s. Retrying in %.2fs",
                    attempt,
                    attempts,
                    url,
                    exc,
                    sleep_for,
                )
                time.sleep(sleep_for)
                continue

            if response.status_code == 404:
                raise ConsumerHttpError(404, url)
            if response.status_code in {403, 429, 500, 502, 503, 504}:
                if attempt >= attempts:
                    raise ConsumerRateLimitError(
                        f"HTTP {response.status_code} for {url} after {attempts} attempts"
                    )
                sleep_for = self.backoff_factor * attempt
                self.logger.warning(
                    "HTTP %s on attempt %s/%s for %s. Retrying in %.2fs",
                    response.status_code,
                    attempt,
                    attempts,
                    url,
                    sleep_for,
                )
                time.sleep(sleep_for)
                continue
            if response.status_code >= 400:
                raise ConsumerHttpError(response.status_code, url)
            return response

        raise ConsumerClientError(f"Request failed unexpectedly: {url}")

    def fetch_page(self, path: str) -> str:
        """Fetch a site-relative path such as ``phones/mate-x7/specs/``."""
        path = path.lstrip("/")
        return self.fetch_text(f"{self.base_url}{path}")

    def fetch_page_with_final_url(self, path: str) -> tuple[str, str]:
        """Fetch a path and return ``(final_url, text)`` after redirects."""
        path = path.lstrip("/")
        response = self.fetch_response(f"{self.base_url}{path}")
        return response.url, response.text


class ConsumerSitemap:
    """Fetch and parse the region sitemap for supplementary product URLs."""

    LOC_PATTERN = re.compile(r"<loc>([^<]+)</loc>")

    def __init__(self, client: ConsumerClient) -> None:
        self.client = client
        self.logger = client.logger

    def fetch_specs_urls(self, category_paths: set[str]) -> list[str]:
        """Return site-relative product paths discovered from the sitemap.

        Any sitemap URL shaped like ``{category}/{slug}/...`` is treated as a
        product candidate (``specs/``/``buy/`` sub-pages included); only URLs
        under the configured category paths are kept.
        """
        try:
            text = self.client.fetch_text(f"{self.client.base_url}sitemap.xml")
        except ConsumerClientError as exc:
            self.logger.warning("Unable to fetch sitemap, skipped: %s", exc)
            return []

        paths: list[str] = []
        prefix = self.client.base_url
        for match in self.LOC_PATTERN.finditer(text):
            url = match.group(1).strip()
            if not url.startswith(prefix):
                continue
            rel = url[len(prefix):]
            segments = [part for part in rel.split("/") if part]
            if len(segments) < 2:
                continue
            if segments[0] not in category_paths:
                continue
            paths.append(f"{segments[0]}/{segments[1]}/")
        self.logger.info("Sitemap yielded %s candidate product paths", len(paths))
        return paths
