import aiohttp, logging, traceback

import config as config
from .schemas import TextAnswer

BASE_URL = "https://api-ru.hydraai.ru/v1"

class TextAI:
    """Текстовые/мультимодальные запросы к LLM (HydraAI)."""

    @staticmethod
    def _headers() -> dict:
        return {"Authorization": f"Bearer {config.HYDRAI_TOKEN}"}

    @classmethod
    async def from_text(cls, messages: list, model: str) -> TextAnswer:
        try:
            async with aiohttp.ClientSession(headers=cls._headers()) as session:
                async with session.post(f"{BASE_URL}/chat/completions", json={"model": model, "messages": messages}) as response:
                    if response.status != 200:
                        logging.error(f"Hydra AI API: {response.status} - {await response.text()}")
                        return TextAnswer(success=False, error_text=f"status {response.status}")

                    data = await response.json()
                    answer = data['choices'][0]['message']['content']
                    token_used = int(data['usage']['total_tokens'])
                    return TextAnswer(success=True, answer=answer, token_consumed=token_used)

        except Exception:
            logging.error(traceback.format_exc())
            return TextAnswer(success=False, error_text="exception")

    @classmethod
    async def from_image(cls, messages: list, caption: str, base64_img: str, model: str) -> TextAnswer:
        temp_messages = messages.copy()
        temp_messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}", "detail": 'low'}},
            ],
        })

        try:
            async with aiohttp.ClientSession(headers=cls._headers()) as session:
                async with session.post(f"{BASE_URL}/chat/completions", json={"model": model, "messages": temp_messages}) as response:
                    if response.status != 200:
                        logging.error(f"Hydra AI API (vision): {response.status} - {await response.text()}")
                        return TextAnswer(success=False, error_text=f"status {response.status}")

                    data = await response.json()
                    answer = data["choices"][0]["message"]["content"]
                    token_used = int(data['usage']['total_tokens'])
                    return TextAnswer(success=True, answer=answer, token_consumed=token_used)

        except Exception:
            logging.error(traceback.format_exc())
            return TextAnswer(success=False, error_text="exception")
