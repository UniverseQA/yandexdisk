import os
import platform
import sys
import uuid
from typing import Generator

from dotenv import load_dotenv
import pytest

from client import YandexDiskApiClient
from exceptions import AuthenticationError, PermissionDeniedError

# Автоматическая загрузка переменных из файла .env при запуске тестов
load_dotenv()

DEFAULT_BASE_URL = "https://cloud-api.yandex.net"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--token",
        action="store",
        default=os.getenv("YANDEX_DISK_TOKEN"),
        help="OAuth-токен Яндекс Диска (по умолчанию берется из .env или переменной окружения)",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    results_dir = os.path.join(session.config.rootpath, "allure-results")
    os.makedirs(results_dir, exist_ok=True)
    env_file_path = os.path.join(results_dir, "environment.properties")

    with open(env_file_path, "w", encoding="utf-8") as f:
        f.write(f"Python.Version={sys.version.split()[0]}\n")
        f.write(f"Platform={platform.system()} {platform.release()}\n")
        f.write(f"Base.URL={DEFAULT_BASE_URL}\n")
        f.write("Scope=cloud_api:disk.read cloud_api:disk.write\n")


@pytest.fixture(scope="session")
def disk_client(request: pytest.FixtureRequest) -> Generator[YandexDiskApiClient, None, None]:
    token = request.config.getoption("--token")
    if not token or token == "y0_AgAAAA...":
        pytest.exit(
            "\n[ОШИБКА АВТОРИЗАЦИИ]: OAuth-токен не задан!\n"
            "1. Получите токен по ссылке: https://oauth.yandex.ru/authorize?response_type=token&client_id=<ClientID>\n"
            "2. Укажите его в файле .env (YANDEX_DISK_TOKEN=ваш_токен) или передайте флаг --token=<token>\n"
        )

    client = YandexDiskApiClient(
        base_url=DEFAULT_BASE_URL,
        token=token,
        timeout=(3.05, 15.0),
    )

    try:
        auth_response = client.check_auth()
        assert auth_response.status_code == 200, "Сервер вернул статус отличный от 200 на проверку токена"
    except AuthenticationError as e:
        pytest.exit(f"\n[ОШИБКА]: Недействительный токен (401 Unauthorized): {e}")
    except PermissionDeniedError as e:
        pytest.exit(f"\n[ОШИБКА]: Недостаточно прав токена (403 Forbidden): {e}")
    except Exception as e:
        pytest.exit(f"\n[СЕТЕВАЯ ОШИБКА]: Не удалось связаться с сервером API Яндекс Диска: {e}")

    yield client
    client.session.close()


@pytest.fixture(scope="function")
def isolated_folder(disk_client: YandexDiskApiClient) -> Generator[str, None, None]:
    unique_folder_name = f"pytest_isolated_{uuid.uuid4().hex[:8]}"

    response = disk_client.create_folder(path=unique_folder_name)
    assert response.status_code == 201, (
        f"Ошибка Arrange: Не удалось создать директорию '{unique_folder_name}'. "
        f"Ответ: {response.text}"
    )

    try:
        yield unique_folder_name
    finally:
        try:
            del_response = disk_client.delete_resource(path=unique_folder_name, permanently=True)
            if del_response.status_code == 202:
                operation_href = del_response.json().get("href")
                if operation_href:
                    disk_client.wait_for_operation(operation_href)
            elif del_response.status_code not in (200, 204, 404):
                pytest.fail(
                    f"Ошибка Teardown: Не удалось удалить '{unique_folder_name}'. "
                    f"Код: {del_response.status_code}"
                )
        except Exception as ex:
            pytest.fail(f"Критический сбой в фазе Teardown: {ex}")