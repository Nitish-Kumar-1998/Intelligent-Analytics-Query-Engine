"""
llm_client.py
-------------
Provider-agnostic LLM wrapper, free-tier providers only.
Switch providers by setting LLM_PROVIDER env var to "gemini" or "groq" —
no code changes needed in planner.py or sql_generator.py.

Required env vars per provider:
  gemini -> GEMINI_API_KEY   (https://aistudio.google.com/apikey)
  groq   -> GROQ_API_KEY     (https://console.groq.com/keys)
"""

import os
import time

PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()

_client = None


def _get_gemini_client():
    from google import genai
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def _get_groq_client():
    from groq import Groq
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))


def get_client():
    global _client
    if _client is None:
        if PROVIDER == "gemini":
            _client = _get_gemini_client()
        elif PROVIDER == "groq":
            _client = _get_groq_client()
        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}. Use 'gemini' or 'groq'.")
    return _client


def _call_once(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    client = get_client()

    if PROVIDER == "gemini":
        from google.genai import types
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )
        return response.text.strip()

    elif PROVIDER == "groq":
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1000, retries: int = 3) -> str:
    """
    Sends one message to whichever free provider is configured and
    returns the plain text response. Retries on transient server errors
    (503, timeouts) with a short backoff, since free-tier APIs sometimes
    have brief availability blips.
    """
    last_error = None
    for attempt in range(retries):
        try:
            return _call_once(system_prompt, user_prompt, max_tokens)
        except Exception as e:
            last_error = e
            wait_time = 2 * (attempt + 1)  # 2s, 4s, 6s
            print(f"  [retry] LLM call failed ({e}), retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise RuntimeError(f"LLM call failed after {retries} attempts. Last error: {last_error}")