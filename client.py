import json
import logging
import time
from typing import Any, Optional
from urllib.parse import urljoin

import allure
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from exceptions import AuthenticationError, PermissionDeniedError, OperationTimeoutError

logger = logging.getLogger(__name__)


class YandexDiskApiClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: tuple[float, float] = (3.05, 15.0),
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self._token = token.strip()
        self.session = self._create_resilient_session()

    def _create_resilient_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "PUT", "POST", "DELETE"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "Authorization": f"OAuth {self._token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "YandexDisk-AutoTests-Runner/1.0",
            }
        )
        return session

    @staticmethod
    def _mask_headers(headers: dict[str, Any]) -> dict[str, str]:
        masked = {}
        for key, value in headers.items():
            if key.lower() == "authorization":
                masked[key] = "OAuth [PROTECTED]"
            else:
                masked[key] = str(value)
        return masked

    def _send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        url = urljoin(self.base_url, endpoint.lstrip("/"))
        request_step_name = f"HTTP {method.upper()} {endpoint}"

        with allure.step(request_step_name):
            req_headers = dict(self.session.headers)
            masked_headers = self._mask_headers(req_headers)

            req_log_payload = {
                "method": method.upper(),
                "url": url,
                "params": params or {},
                "headers": masked_headers,
                "json": json_data or {},
            }
            allure.attach(
                json.dumps(req_log_payload, indent=2, ensure_ascii=False),
                name="Request Data",
                attachment_type=allure.attachment_type.JSON,
            )

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
            )

            res_log_payload = {
                "status_code": response.status_code,
                "elapsed_seconds": response.elapsed.total_seconds(),
                "headers": dict(response.headers),
            }
            allure.attach(
                json.dumps(res_log_payload, indent=2, ensure_ascii=False),
                name="Response Context",
                attachment_type=allure.attachment_type.JSON,
            )

            if response.text:
                try:
                    formatted_body = json.dumps(response.json(), indent=2, ensure_ascii=False)
                    attachment_type = allure.attachment_type.JSON
                except ValueError:
                    formatted_body = response.text
                    attachment_type = allure.attachment_type.TEXT

                allure.attach(
                    formatted_body,
                    name="Response Body",
                    attachment_type=attachment_type,
                )

            if response.status_code == 401:
                raise AuthenticationError(
                    f"Ошибка 401 Unauthorized: Токен недействителен или истек. Ответ: {response.text}"
                )
            if response.status_code == 403:
                raise PermissionDeniedError(
                    f"Ошибка 403 Forbidden: Недостаточно прав у OAuth-токена. Ответ: {response.text}"
                )

            return response

    def check_auth(self) -> requests.Response:
        return self._send_request(method="GET", endpoint="v1/disk")

    def create_folder(self, path: str) -> requests.Response:
        return self._send_request(
            method="PUT",
            endpoint="v1/disk/resources",
            params={"path": path},
        )

    def get_resource(self, path: str) -> requests.Response:
        return self._send_request(
            method="GET",
            endpoint="v1/disk/resources",
            params={"path": path},
        )

    def copy_resource(
        self,
        from_path: str,
        to_path: str,
        overwrite: bool = False,
    ) -> requests.Response:
        return self._send_request(
            method="POST",
            endpoint="v1/disk/resources/copy",
            params={
                "from": from_path,
                "path": to_path,
                "overwrite": str(overwrite).lower(),
            },
        )

    def delete_resource(self, path: str, permanently: bool = True) -> requests.Response:
        return self._send_request(
            method="DELETE",
            endpoint="v1/disk/resources",
            params={
                "path": path,
                "permanently": str(permanently).lower(),
            },
        )

    def get_operation_status(self, operation_id: str) -> requests.Response:
        return self._send_request(
            method="GET",
            endpoint=f"v1/disk/operations/{operation_id}",
        )

    def wait_for_operation(self, operation_url_or_id: str, timeout_seconds: float = 30.0) -> None:
        operation_id = operation_url_or_id.split("/")[-1]
        start_time = time.monotonic()
        poll_interval = 0.5

        with allure.step(f"Ожидание завершения асинхронной операции {operation_id}"):
            while time.monotonic() - start_time < timeout_seconds:
                response = self.get_operation_status(operation_id)
                if response.status_code == 200:
                    status = response.json().get("status")
                    if status == "success":
                        return
                    if status == "failed":
                        raise YandexDiskApiException(
                            f"Асинхронная операция {operation_id} завершилась со статусом 'failed'"
                        )
                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, 3.0)

            raise OperationTimeoutError(
                f"Превышено максимальное время ожидания операции {operation_id} ({timeout_seconds} c)"
            )