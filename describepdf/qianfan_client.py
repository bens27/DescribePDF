"""
Baidu Qianfan client module for DescribePDF.

This module handles direct interactions with Baidu's Qianfan platform via its
OpenAI-compatible v2 Chat Completions API, for VLM (Vision Language Model)
image description and LLM text summarization. Use this provider with an API
key from your Baidu Qianfan account when a model is not available through
OpenRouter.
"""

import requests
import json
import logging
from typing import Dict, Any, List

from .openrouter_client import encode_image_to_base64

# Get logger from config module
logger = logging.getLogger('describepdf')

# Constants
QIANFAN_API_URL = "https://qianfan.baidubce.com/v2/chat/completions"
DEFAULT_TIMEOUT = 300  # 5 minutes

def call_qianfan_api(api_key: str, model: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Make a call to the Qianfan Chat Completions API.

    Args:
        api_key: Baidu Qianfan API key
        model: Model name to use (e.g. 'qianfan-ocr-fast', 'ernie-4.5-turbo-vl')
        messages: List of messages in OpenAI-compatible format

    Returns:
        Dict: The JSON response from the API

    Raises:
        ValueError: If API key is missing
        ConnectionError: If API call fails with error response
        TimeoutError: If API call times out
    """
    if not api_key:
        logger.error("Baidu Qianfan API Key is missing.")
        raise ValueError("Baidu Qianfan API Key is missing.")

    headers: Dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages
    }

    try:
        msg_log = json.dumps(messages)[:200] + ("..." if len(json.dumps(messages)) > 200 else "")
        logger.debug(f"Calling Qianfan API. Model: {model}. Messages: {msg_log}")

        response = requests.post(
            QIANFAN_API_URL,
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        logger.debug(f"API call successful. Status: {response.status_code}.")
        return response.json()

    except requests.exceptions.Timeout:
        logger.error(f"Qianfan API call timed out for model {model}.")
        raise TimeoutError(f"Qianfan API call timed out for model {model}.")

    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', 'N/A') if hasattr(e, 'response') else 'N/A'
        response_text = getattr(e.response, 'text', 'No response') if hasattr(e, 'response') else 'No response'
        logger.error(f"Qianfan API call failed for model {model}. Status: {status_code}. Response: {response_text}")

        error_message = f"Qianfan API Error: {e}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                if 'error' in error_details and 'message' in error_details['error']:
                    error_message = f"Qianfan API Error ({e.response.status_code}): {error_details['error']['message']}"
                else:
                    error_message = f"Qianfan API Error ({e.response.status_code}): {e.response.text[:200]}"
            except json.JSONDecodeError:
                error_message = f"Qianfan API Error ({e.response.status_code}): {e.response.text[:200]}"

        raise ConnectionError(error_message)

def get_vlm_description(api_key: str, model: str, prompt_text: str, image_bytes: bytes, mime_type: str) -> str:
    """
    Get a page description using a VLM through Qianfan.

    Args:
        api_key: Baidu Qianfan API key
        model: VLM model name
        prompt_text: Text prompt
        image_bytes: Bytes of the page image
        mime_type: MIME type of the image ('image/png' or 'image/jpeg')

    Returns:
        str: Generated description

    Raises:
        ValueError: If API key is missing or image encoding fails
        ConnectionError: If API call fails with error response
        TimeoutError: If API call times out
    """
    base64_image = encode_image_to_base64(image_bytes, mime_type)

    messages: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {
                    "type": "image_url",
                    "image_url": {"url": base64_image}
                }
            ]
        }
    ]

    response_json = call_qianfan_api(api_key, model, messages)

    if response_json and 'choices' in response_json and response_json['choices']:
        message = response_json['choices'][0].get('message', {})
        content = message.get('content') if message else None
        if content:
            logger.info(f"Received VLM description for page (Qianfan model: {model}).")
            return str(content)
        logger.warning("Qianfan VLM response structure unexpected or content empty.")
        raise ValueError("VLM returned no usable content")
    else:
        logger.warning(f"Qianfan VLM response JSON structure unexpected: {response_json}")
        raise ValueError("VLM returned unexpected response structure")

def get_llm_summary(api_key: str, model: str, prompt_text: str) -> str:
    """
    Get a summary using an LLM through Qianfan.

    Args:
        api_key: Baidu Qianfan API key
        model: LLM model for summary
        prompt_text: Prompt including the text to summarize

    Returns:
        str: Generated summary

    Raises:
        ValueError: If API key is missing
        ConnectionError: If API call fails with error response
        TimeoutError: If API call times out
    """
    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": prompt_text}
    ]

    response_json = call_qianfan_api(api_key, model, messages)

    if response_json and 'choices' in response_json and response_json['choices']:
        message = response_json['choices'][0].get('message', {})
        content = message.get('content') if message else None
        if content:
            logger.info(f"Received summary (Qianfan model: {model}).")
            return str(content)
        logger.warning("Qianfan LLM summary response structure unexpected or content empty.")
        raise ValueError("LLM returned no usable content")
    else:
        logger.warning(f"Qianfan LLM summary response JSON structure unexpected: {response_json}")
        raise ValueError("LLM returned unexpected response structure")
