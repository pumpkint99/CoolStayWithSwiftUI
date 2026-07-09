"""
기상청 단기예보(getUltraSrtNcst, 초단기실황조회) API를 5분마다 폴링해
smartvillage-api의 POST /api/weatherdata/add 를 호출하는 standalone 스크립트.

Python 3.9.16 대상. 의존성은 requirements.txt 참고 (requests).

사용 예:
    KMA_SERVICE_KEY=... python3 weather_kma_collector2.py
    KMA_SERVICE_KEY=... python3 weather_kma_collector2.py --once   # 1회만 실행(테스트용)

service-key는 공공데이터포털에서 발급받은 "디코딩" 키를 사용할 것.
requests가 params를 자동으로 URL 인코딩하므로, 이미 인코딩된 키를 넣으면
이중 인코딩되어 인증 오류가 발생한다.
"""
import argparse
import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

KMA_API_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
NX = 80
NY = 138
WEATHER_CODE = "wthr_01"
INTERVAL_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = 10
KST = ZoneInfo("Asia/Seoul")
REQUIRED_CATEGORIES = {"T1H", "REH", "VEC", "WSD", "RN1"}


def build_request_params(service_key: str, now: datetime) -> dict:
    return {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 20,
        "dataType": "JSON",
        "base_date": now.strftime("%Y%m%d"),
        "base_time": now.strftime("%H%M"),
        "nx": NX,
        "ny": NY,
    }


def fetch_observation(session: requests.Session, service_key: str, now: datetime):
    params = build_request_params(service_key, now)
    response = session.get(KMA_API_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    header = payload.get("response", {}).get("header", {})
    if header.get("resultCode") != "00":
        logging.warning(
            "KMA API 응답 실패 base_date=%s base_time=%s resultCode=%s resultMsg=%s",
            params["base_date"], params["base_time"],
            header.get("resultCode"), header.get("resultMsg"),
        )
        return None

    items = payload["response"]["body"]["items"]["item"]
    return {item["category"]: item["obsrValue"] for item in items}


def build_weather_data(observation: dict):
    missing = REQUIRED_CATEGORIES - observation.keys()
    if missing:
        logging.warning("필수 카테고리 누락: %s (observation=%s)", missing, observation)
        return None

    try:
        temperature = float(observation["T1H"])
        humidity = int(round(float(observation["REH"])))
        direction = int(round(float(observation["VEC"])))
        speed = int(round(float(observation["WSD"])))
    except (TypeError, ValueError) as exc:
        logging.warning("필수 값 파싱 실패: %s (observation=%s)", exc, observation)
        return None

    try:
        rainfall = int(round(float(observation["RN1"])))
    except (TypeError, ValueError):
        logging.info("RN1 값(%r)이 숫자가 아니어서 0으로 처리", observation["RN1"])
        rainfall = 0

    return {
        "temperature": temperature,
        "humidity": humidity,
        "direction": direction,
        "speed": speed,
        "rainfall": rainfall,
    }


def build_weather_data_request_body(values: dict) -> dict:
    return {
        "device_id": WEATHER_CODE,
        "temperature": values["temperature"],
        "humidity": values["humidity"],
        "wind": {
            "direction": values["direction"],
            "speed": values["speed"],
        },
        "rainfall": values["rainfall"],
        "fine_dust": {
            "pm10": 0,
            "pm2p5": 0,
        },
        "sunshine": 0,
        "solar_radiation": 0,
    }


def send_weather_data(session: requests.Session, api_base_url: str, values: dict) -> None:
    body = build_weather_data_request_body(values)
    response = session.post(f"{api_base_url}/weatherdata/add", json=body, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    result = response.json()
    if isinstance(result, dict) and result.get("result") == "failed":
        raise RuntimeError(f"weatherdata/add 호출 실패: {result.get('message')}")


def run_once(session: requests.Session, api_base_url: str, service_key: str) -> None:
    now = datetime.now(KST)
    observation = fetch_observation(session, service_key, now)
    if observation is None:
        return

    values = build_weather_data(observation)
    if values is None:
        return

    send_weather_data(session, api_base_url, values)
    logging.info("weatherdata/add 호출 완료: values=%s", values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="기상청 초단기실황 API를 폴링해 /api/weatherdata/add 를 호출")
    parser.add_argument("--service-key", default=os.environ.get("KMA_SERVICE_KEY", "f40ddf1085c06815f31a817e32f6bd7b1bf9198570d00d4ecfe2fd2d3e9e31bd"),
                         help="공공데이터포털 서비스키 (미지정 시 KMA_SERVICE_KEY 환경변수 사용)")
    parser.add_argument("--api-base-url", default=os.environ.get("API_BASE_URL", "http://localhost:8080/api"),
                         help="smartvillage-api 기본 URL (미지정 시 API_BASE_URL 환경변수 또는 http://localhost:8080/api)")
    parser.add_argument("--once", action="store_true", help="무한 반복 대신 1회만 실행 (테스트용)")
    args = parser.parse_args()

    if not args.service_key:
        parser.error("--service-key 또는 환경변수 KMA_SERVICE_KEY가 필요합니다")

    logging.info(
        "실행 인자: service_key=%s api_base_url=%s once=%s",
        "****", args.api_base_url, args.once,
    )
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()

    session = requests.Session()
    while True:
        try:
            run_once(session, args.api_base_url, args.service_key)
        except Exception:
            logging.exception("주기 실행 중 오류 발생")

        if args.once:
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
