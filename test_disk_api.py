import uuid
import allure
import pytest
from client import YandexDiskApiClient


@allure.epic("Яндекс Диск: REST API")
@allure.feature("Управление ресурсами хранилища")
@pytest.mark.disk_api
class TestYandexDiskResources:

    @allure.story("Создание новой директории (PUT) - Happy Path")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_create_folder_put(self, disk_client: YandexDiskApiClient) -> None:
        folder_name = f"test_dir_put_{uuid.uuid4().hex[:8]}"

        try:
            with allure.step("Отправка запроса PUT на создание директории"):
                response = disk_client.create_folder(path=folder_name)

            with allure.step("Проверка статуса и контракта ответа создания"):
                assert response.status_code == 201, (
                    f"Ожидался статус 201 Created, получен {response.status_code}: {response.text}"
                )
                payload = response.json()
                assert "href" in payload, "В ответе отсутствует обязательное поле 'href'"
                assert payload.get("method") == "GET", "Ожидался метод перехода 'GET'"

            with allure.step("Верификация фактического существования папки через GET"):
                verify_response = disk_client.get_resource(path=folder_name)
                assert verify_response.status_code == 200, (
                    f"Созданный ресурс не найден. Статус {verify_response.status_code}"
                )
                verify_data = verify_response.json()
                assert verify_data.get("type") == "dir", "Тип созданного ресурса должен быть 'dir'"
                assert verify_data.get("name") == folder_name, "Имя созданного ресурса не совпадает"
        finally:
            with allure.step("Гарантированная очистка созданной папки"):
                del_res = disk_client.delete_resource(path=folder_name, permanently=True)
                if del_res.status_code == 202:
                    disk_client.wait_for_operation(del_res.json()["href"])

    @allure.story("Создание уже существующей директории (PUT) - Negative Path")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    def test_create_duplicate_folder_conflict(
        self,
        disk_client: YandexDiskApiClient,
        isolated_folder: str,
    ) -> None:
        with allure.step("Попытка повторного создания существующей папки"):
            response = disk_client.create_folder(path=isolated_folder)

        with allure.step("Проверка ошибки 409 Conflict"):
            assert response.status_code == 409, (
                f"Ожидался статус 409 Conflict, получен {response.status_code}: {response.text}"
            )
            error_data = response.json()
            assert error_data.get("error") == "DiskPathPointsToExistentDirectoryError", (
                f"Неожиданный код ошибки: {error_data.get('error')}"
            )

    @allure.story("Получение метаданных о папке (GET) - Happy Path")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_get_resource_meta_get(
        self,
        disk_client: YandexDiskApiClient,
        isolated_folder: str,
    ) -> None:
        with allure.step("Запрос метаинформации о существующей директории"):
            response = disk_client.get_resource(path=isolated_folder)

        with allure.step("Валидация атрибутов папки в ответе"):
            assert response.status_code == 200, (
                f"Не удалось получить метаданные. Статус: {response.status_code}"
            )
            body = response.json()
            assert body.get("type") == "dir", "Поле 'type' должно иметь значение 'dir'"
            assert body.get("name") == isolated_folder, "Поле 'name' не совпадает с запрашиваемым"
            assert body.get("path") == f"disk:/{isolated_folder}", "Некорректный URI путь в 'path'"
            assert "_embedded" in body, "Отсутствует блок служебных метаданных '_embedded'"

    @allure.story("Получение метаданных несуществующего ресурса (GET) - Negative Path")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    def test_get_nonexistent_resource_not_found(self, disk_client: YandexDiskApiClient) -> None:
        non_existent_path = f"non_existent_{uuid.uuid4().hex[:10]}"

        with allure.step("Запрос несуществующего пути"):
            response = disk_client.get_resource(path=non_existent_path)

        with allure.step("Проверка ошибки 404 Not Found"):
            assert response.status_code == 404, (
                f"Ожидался статус 404 Not Found, получен {response.status_code}"
            )
            assert response.json().get("error") == "DiskNotFoundError"

    @allure.story("Копирование директории (POST) - Happy Path")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.smoke
    def test_copy_resource_post(
        self,
        disk_client: YandexDiskApiClient,
        isolated_folder: str,
    ) -> None:
        destination_folder = f"{isolated_folder}_copied_{uuid.uuid4().hex[:6]}"

        try:
            with allure.step("Копирование директории в новый путь через POST"):
                response = disk_client.copy_resource(
                    from_path=isolated_folder,
                    to_path=destination_folder,
                    overwrite=False,
                )

            with allure.step("Проверка статуса операции копирования"):
                assert response.status_code in (201, 202), (
                    f"Неверный статус копирования: {response.status_code}. Ответ: {response.text}"
                )
                if response.status_code == 202:
                    disk_client.wait_for_operation(response.json()["href"])

            with allure.step("Верификация доступности целевого ресурса через GET"):
                verify_response = disk_client.get_resource(path=destination_folder)
                assert verify_response.status_code == 200, "Скопированный ресурс недоступен"
                verify_data = verify_response.json()
                assert verify_data.get("type") == "dir", "Скопированный ресурс не является папкой"
                assert verify_data.get("name") == destination_folder, "Имя копии не совпадает"
        finally:
            with allure.step("Очистка созданной копии"):
                del_copy = disk_client.delete_resource(path=destination_folder, permanently=True)
                if del_copy.status_code == 202:
                    disk_client.wait_for_operation(del_copy.json()["href"])

    @allure.story("Удаление директории (DELETE) - Happy Path")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_delete_resource_delete(self, disk_client: YandexDiskApiClient) -> None:
        target_folder = f"test_dir_to_delete_{uuid.uuid4().hex[:8]}"

        with allure.step("Предварительное создание удаляемой директории"):
            create_res = disk_client.create_folder(path=target_folder)
            assert create_res.status_code == 201, "Не удалось создать папку под удаление"

        with allure.step("Вызов DELETE для созданной папки без перемещения в Корзину"):
            delete_response = disk_client.delete_resource(path=target_folder, permanently=True)

        with allure.step("Проверка статуса подтверждения удаления"):
            assert delete_response.status_code in (202, 204), (
                f"Ожидался статус 204 No Content или 202 Accepted, "
                f"получен {delete_response.status_code}: {delete_response.text}"
            )
            if delete_response.status_code == 202:
                disk_client.wait_for_operation(delete_response.json()["href"])

        with allure.step("Проверка отсутствия удаленного ресурса через GET"):
            check_response = disk_client.get_resource(path=target_folder)
            assert check_response.status_code == 404, (
                f"Ресурс все еще существует! Статус: {check_response.status_code}"
            )
            error_body = check_response.json()
            assert error_body.get("error") == "DiskNotFoundError", (
                f"Неожиданный код ошибки в теле ответа: {error_body}"
            )