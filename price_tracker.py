import re

import requests

API_URL = "https://yearly-flexible-canvasback.cloudpub.ru/v1/parse"
API_TOKEN = ""


def get_price(url: str) -> tuple[bool, str, float | None]:
    try:
        response = requests.post(
            url=API_URL,
            json={"message": f"Пришли только цену числом (без озон банка и т.д.) в json и больше ничего {url}"},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_TOKEN}"
            },
            timeout=120
        )

        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            return False, f"Сервер вернул ошибку: {data.get('message', '?')}", None
        price = extract_price(data.get("message", ""))

        if price is not None:
            return True, f"Цена товара: {price} ₽", price
        else:
            return True, f"Цена не найдена в ответе: {data.get('message', '')}", None

    except requests.exceptions.Timeout:
        return False, "Сервер не ответил за 120 секунд", None

    except requests.exceptions.ConnectionError:
        return False, "Нет подключения к интернету", None

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 401:
            return False, "Неверный токен доступа", None
        elif status_code == 429:
            return False, "Слишком много запросов, подождите", None
        else:
            return False, f"Ошибка сервера: HTTP {status_code}", None

    except Exception as e:
        return False, f"Что-то пошло не так: {e}", None


def extract_price(text: str) -> float | None:
    if not text:
        return None

    match = re.search(
        r'```json\s*\{\s*"price"\s*:\s*(\d+(?:\.\d+)?)\s*\}\s*```',
        text,
        re.IGNORECASE
    )

    if match:
        return float(match.group(1))

    match = re.search(
        r'\{\s*"price"\s*:\s*(\d+(?:\.\d+)?)\s*\}',
        text,
        re.IGNORECASE
    )

    if match:
        return float(match.group(1))

    patterns = [
        r'цена[:\s]*(\d[\d\s]*(?:[.,]\d+)?)',
        r'price[:\s]*(\d[\d\s]*(?:[.,]\d+)?)',
        r'(\d[\d\s]*(?:[.,]\d+)?)\s*(?:руб|₽)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            price_str = match.group(1)
            price_str = price_str.replace(" ", "").replace(",", ".")

            try:
                return float(price_str)
            except ValueError:
                continue
    return None
