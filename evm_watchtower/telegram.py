from __future__ import annotations

import httpx


def render_event_message(event: dict) -> str:
    details = event.get("details", {})
    return (
        "EVM Watchtower alert\n"
        f"Chain: {event['chain_key']}\n"
        f"Address: {event['watched_address']}\n"
        f"Action: {event['action']} ({event['direction']})\n"
        f"Summary: {event['summary']}\n"
        f"Tx: {details.get('explorer', event['tx_hash'])}"
    )


async def send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        )
    response.raise_for_status()

