"""LLM client wrapper supporting OpenAI and Anthropic."""

import os
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """Unified LLM client supporting OpenAI and Anthropic."""

    def __init__(self, provider: str = None, model: str = None):
        """
        Initialize LLM client.

        Args:
            provider: "openai" or "anthropic" (auto-detected from .env if None)
            model: Model name (uses default if None)
        """
        self.provider = provider or self._auto_detect_provider()
        self.model = model or self._get_default_model()
        self.client = self._init_client()

    def _auto_detect_provider(self) -> str:
        """Auto-detect provider based on available API keys."""
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        else:
            raise ValueError(
                "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env"
            )

    def _get_default_model(self) -> str:
        """Get default model for the provider."""
        if self.provider == "openai":
            return os.getenv("LLM_MODEL", "gpt-4o-mini")
        elif self.provider == "anthropic":
            return os.getenv("LLM_MODEL", "claude-3-haiku-20240307")
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _init_client(self):
        """Initialize the appropriate client."""
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.provider == "anthropic":
            import anthropic
            return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate text response from LLM.

        Args:
            prompt: User prompt
            system: System message (optional)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        if self.provider == "openai":
            return self._openai_generate(prompt, system, temperature, max_tokens)
        elif self.provider == "anthropic":
            return self._anthropic_generate(prompt, system, temperature, max_tokens)

    def _openai_generate(
        self, prompt: str, system: Optional[str], temperature: float, max_tokens: int
    ) -> str:
        """OpenAI generation."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    def _anthropic_generate(
        self, prompt: str, system: Optional[str], temperature: float, max_tokens: int
    ) -> str:
        """Anthropic generation."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text.strip()


def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt template from prompts/ directory.

    Args:
        prompt_name: Name of prompt file (with or without .txt extension)

    Returns:
        Prompt template string
    """
    if not prompt_name.endswith(".txt"):
        prompt_name += ".txt"

    prompt_path = os.path.join("prompts", prompt_name)
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


# Singleton instance for reuse
_default_client = None


def get_llm_client() -> LLMClient:
    """Get or create the default LLM client (singleton)."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
