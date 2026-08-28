from __future__ import annotations

import logging
from typing import Dict, List

import httpx

log = logging.getLogger("trip_smart.reports.push")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
BATCH_SIZE = 100

async def send_district_push(tokens: List[str], title: str, body: str, data: Dict) -> None:
    if not tokens:
        return
    messages = [
        {"to": t, "title": title, "body": body, "data": data, "sound": "default"}
        for t in tokens
        if t.startswith("ExponentPushToken") or t.startswith("ExpoPushToken")
    ]
    if not messages:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for i in range(0, len(messages), BATCH_SIZE):
                batch = messages[i : i + BATCH_SIZE]
                resp = await client.post(
                    EXPO_PUSH_URL,
                    json=batch,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                if resp.status_code >= 400:
                    log.warning("Expo push send failed (%s): %s", resp.status_code, resp.text[:300])
    except Exception as e:
        log.warning("Expo push send errored: %s", e)
