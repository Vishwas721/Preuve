import httpx

from app.llm.base import LLMProvider, LLMUnavailableError, T, parse_structured

_JSON_SYSTEM = (
    "Respond only with a single JSON object that matches the requested schema. "
    "Do not add commentary."
)


class OllamaProvider(LLMProvider):
    """Local model served by Ollama (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        num_ctx: int = 8192,
        timeout_s: float = 180.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_s, transport=transport)

    async def _chat(
        self, prompt: str, system: str | None, temperature: float, fmt: dict | None
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": self.num_ctx},
        }
        if fmt is not None:
            payload["format"] = fmt
        try:
            resp = await self._client.post("/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Ollama unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise LLMUnavailableError(f"Ollama error {resp.status_code}: {resp.text[:300]}")
        return resp.json()["message"]["content"]

    async def generate_text(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> str:
        return await self._chat(prompt, system, temperature, fmt=None)

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        full_system = f"{system}\n\n{_JSON_SYSTEM}" if system else _JSON_SYSTEM
        raw = await self._chat(prompt, full_system, temperature, fmt=schema.model_json_schema())
        return parse_structured(raw, schema)

    async def is_available(self) -> bool:
        try:
            resp = await self._client.get("/api/tags", timeout=3.0)
            resp.raise_for_status()
        except httpx.HTTPError:
            return False
        names = {m.get("name") for m in resp.json().get("models", [])}
        return self.model in names
