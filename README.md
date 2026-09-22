# Yandex Disk REST API Automation Testing

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/Pytest-8.x-0A9EDC?logo=pytest)](https://docs.pytest.org/)
[![Allure Report](https://img.shields.io/badge/Allure%20Report-2.30-orange?logo=qameta)](https://allurereport.org/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Автоматизация контрактного и интеграционного тестирования REST API сервиса Яндекс Диск (`https://cloud-api.yandex.net`)

## Архитектура решения
1. **Изоляция данных**: Все тестовые ресурсы создаются с уникальными UUID-префиксами, исключая гонки и взаимное влияние тестов при параллельном запуске.
2. **Безопасность**: Заголовки авторизации (`Authorization: OAuth ***`) принудительно маскируются перед записью в отчеты Allure.
3. **Устойчивость**: Настроен `HTTPAdapter` с автоповторами сетевых сбоев (429, 500, 502, 503, 504) и экспоненциальным бэкоффом.
4. **Гарантированный Teardown**: Очистка тестовых сущностей в облаке выполняется в блоках `try ... finally` с флагом `permanently=true`.

---

## Покрытые методы API
| Метод | Эндпоинт | Тип проверки | Описание |
| :--- | :--- | :--- | :--- |
| **PUT** | `/v1/disk/resources` | Позитивный | Создание новой директории |
| **PUT** | `/v1/disk/resources` | Негативный | Попытка создания дубликата (409 Conflict) |
| **GET** | `/v1/disk/resources` | Позитивный | Чтение метаданных существующей папки |
| **GET** | `/v1/disk/resources` | Негативный | Запрос несуществующего пути (404 Not Found) |
| **POST** | `/v1/disk/resources/copy`| Позитивный | Копирование ресурса в новый путь |
| **DELETE**| `/v1/disk/resources` | Позитивный | Перманентное удаление ресурса |

---

## Структура проекта

```text
yandex_disk_api_tests/
├── .github/
│   └── workflows/
│       └── tests.yml          # CI/CD пайплайн запуска тестов и деплоя Allure на GH Pages
├── .env.example               # Шаблон конфигурации переменных окружения
├── .gitignore                 # Исключение секретов, кэша и виртуального окружения
├── pytest.ini                 # Базовая конфигурация раннера Pytest и путей Allure
├── requirements.txt           # Зафиксированные версионные зависимости проекта
├── exceptions.py              # Кастомные исключения API (Auth, Permissions, Timeout)
├── client.py                  # Сетевой клиент-обертка с resilience и Allure-аттачами
├── conftest.py                # Сессионные и функциональные фикстуры, хуки среды
├── test_disk_api.py           # Контрактные и интеграционные тесты (Smoke & Regression)
└── README.md                  # Полная документация проекта
```

---

---

## Локальный запуск

### 1. Клонирование и установка зависимостей
```bash
git clone https://github.com/universeqa/yandexdisk.git
cd yandexdisk

python -m venv .venv
source .venv/bin/activate  # Для Linux/macOS
# .venv\Scripts\activate   # Для Windows

pip install -r requirements.txt
```
### 2. Конфигурация авторизации (OAuth)
1. Получите ClientID OAuth-приложения на портале [Яндекс OAuth](https://oauth.yandex.ru/).
2. Перейдите по ссылке авторизации и скопируйте выданный токен:
   `https://oauth.yandex.ru/authorize?response_type=token&client_id=<ClientID>`
   * *(Необходимые права доступа: `cloud_api:disk.read`, `cloud_api:disk.write`, `cloud_api:disk.info`).*
3. Создайте локальный файл `.env` на основе шаблона:
   * **Linux / macOS:** `cp .env.example .env`
   * **Windows:** `copy .env.example .env`
4. Внесите скопированный токен в `.env`:
   ```env
   YANDEX_DISK_TOKEN=y0_AgAAAA...
   ```
### 3. Выполнение тестов
#### Базовые команды запуска
```bash
# Стандартный последовательный запуск всех тестов
pytest

# Запуск с подробным логированием выполнения каждого теста
pytest -v -s

# Быстрый запуск в 4 параллельных потока (pytest-xdist)
pytest -n 4
```

#### Выборочный запуск по маркерам (Test Suites)
```bash
# Запуск только критических позитивных проверок (Smoke)
pytest -m smoke

# Запуск полного регрессионного набора, включая негативные проверки
pytest -m regression
```

### 4. Просмотр отчета Allure
При каждом прогоне тестов сгенерированные артефакты сохраняются в папку `allure-results`.

```bash
# Запуск тестов со сбором результатов Allure
pytest -n 4 --alluredir=allure-results

# Запуск локального сервера Allure и автоматическое открытие отчета в браузере
allure serve allure-results

# Сборка статичного автономного HTML-пакета (для архивации или отправки)
allure generate allure-results --clean -o allure-report
```

[![Allure Report Overview](.github/assets/allure_report.png)]
> 🔗 **[Открыть интерактивный Allure Report](https://universeqa.github.io/yandexdisk/)**
## Настройка CI/CD в GitHub Actions

В проекте настроен автоматизированный конвейер непрерывной интеграции (`.github/workflows/tests.yml`). 

При каждом `push` или `pull request` в ветки `main`/`master` runner запускает тесты в распределенном режиме, скачивает исторические данные Allure, собирает актуальный отчет с графиками трендов и развертывает его на **GitHub Pages**.

### Активация пайплайна в вашем репозитории:

1. **Добавление секретного токена:**
   * Откройте репозиторий на GitHub: **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
   * Нажмите **New repository secret**.
   * Имя: `YANDEX_DISK_TOKEN`.
   * Значение: ваш действующий OAuth-токен.
   * Нажмите **Add secret**.

2. **Включение GitHub Pages для хостинга отчетов:**
   * Перейдите в **Settings** $\rightarrow$ **Pages**.
   * В блоке **Build and deployment** $\rightarrow$ **Source** выберите **Deploy from a branch**.
   * Выберите ветку: `gh-pages`, каталог: `/ (root)`.
   * Сохраните изменения. Отчет будет доступен по адресу: `https://<username>.github.io/<repo-name>/`.

---
