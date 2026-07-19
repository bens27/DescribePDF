"""
Configuration module for DescribePDF.

This module manages loading configuration from environment variables
and prompt templates from files.
"""
import os
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv, dotenv_values
import pathlib

# Setup central logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s] - %(message)s')
logger = logging.getLogger('describepdf')

# Directory containing prompt templates (making path absolute by using current file location)
SCRIPT_DIR = pathlib.Path(__file__).parent.parent.absolute()
PROMPTS_DIR = pathlib.Path(SCRIPT_DIR) / "prompts"

# Directory for user-saved prompt overrides. The factory prompts in PROMPTS_DIR
# are never modified; user files shadow them template-by-template.
USER_DIR = pathlib.Path(os.getenv("DESCRIBEPDF_USER_DIR", str(pathlib.Path.home() / ".describepdf")))
USER_PROMPTS_DIR = USER_DIR / "prompts"

# Free-form user notes kept alongside the prompt overrides but independent of
# them: restoring or reloading prompt defaults never touches this file.
FUTURE_IDEAS_FILE = USER_DIR / "future_ideas.md"

# Settings saved from the UI. Loaded on startup after the working-directory
# .env, which therefore takes precedence for keys present in both.
USER_ENV_FILE = USER_DIR / ".env"

# Default configuration values

# Default configuration values
DEFAULT_CONFIG: Dict[str, Any] = {
    "openrouter_api_key": None,
    "or_vlm_model": "qwen/qwen2.5-vl-72b-instruct",
    "or_summary_model": "google/gemini-2.5-flash-preview",

    "provider": "openrouter",
    "qianfan_api_key": None,
    
    "ollama_endpoint": "http://localhost:11434",
    "ollama_vlm_model": "llama3.2-vision",
    "ollama_summary_model": "qwen2.5",
    
    "output_language": "English",
    "use_markitdown": False,
    "use_summary": False,
    "page_selection": None,

    "include_descriptions": True,
    "include_transcription": False,
    "summary_in_output": False
}

# Mapping of prompt template identifiers to their file names
PROMPT_FILES: Dict[str, str] = {
    "summary": "summary_prompt.md",
    "vlm_base": "vlm_prompt_base.md",
    "vlm_markdown": "vlm_prompt_with_markdown.md",
    "vlm_summary": "vlm_prompt_with_summary.md",
    "vlm_full": "vlm_prompt_full.md",
    "vlm_transcribe": "vlm_prompt_transcribe.md"
}

# Cache for loaded configuration
_CONFIG_CACHE: Optional[Dict[str, Any]] = None

# Cache for loaded prompts
_PROMPTS_CACHE: Optional[Dict[str, str]] = None

# Cache for factory (shipped) prompts
_FACTORY_PROMPTS_CACHE: Optional[Dict[str, str]] = None

def load_env_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables (.env file).
    
    This function reads configuration values from environment variables,
    falling back to default values when environment variables are not set.
    
    Returns:
        Dict[str, Any]: Dictionary with the loaded configuration
    """
    load_dotenv()
    if USER_ENV_FILE.is_file():
        load_dotenv(USER_ENV_FILE)

    # Start with the default config
    loaded_config = DEFAULT_CONFIG.copy()
    
    # Override defaults with environment variables if present
    if os.getenv("OPENROUTER_API_KEY"):
        loaded_config["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
        
    if os.getenv("DEFAULT_OR_VLM_MODEL"):
        loaded_config["or_vlm_model"] = os.getenv("DEFAULT_OR_VLM_MODEL")
        
    if os.getenv("DEFAULT_OR_SUMMARY_MODEL"):
        loaded_config["or_summary_model"] = os.getenv("DEFAULT_OR_SUMMARY_MODEL")
        
    if os.getenv("DESCRIBEPDF_PROVIDER"):
        loaded_config["provider"] = str(os.getenv("DESCRIBEPDF_PROVIDER")).lower()

    if os.getenv("QIANFAN_API_KEY"):
        loaded_config["qianfan_api_key"] = os.getenv("QIANFAN_API_KEY")

    if os.getenv("OLLAMA_ENDPOINT"):
        loaded_config["ollama_endpoint"] = os.getenv("OLLAMA_ENDPOINT")
        
    if os.getenv("DEFAULT_OLLAMA_VLM_MODEL"):
        loaded_config["ollama_vlm_model"] = os.getenv("DEFAULT_OLLAMA_VLM_MODEL")
        
    if os.getenv("DEFAULT_OLLAMA_SUMMARY_MODEL"):
        loaded_config["ollama_summary_model"] = os.getenv("DEFAULT_OLLAMA_SUMMARY_MODEL")
        
    if os.getenv("DEFAULT_LANGUAGE"):
        loaded_config["output_language"] = os.getenv("DEFAULT_LANGUAGE")
        
    if os.getenv("DEFAULT_USE_MARKITDOWN"):
        loaded_config["use_markitdown"] = str(os.getenv("DEFAULT_USE_MARKITDOWN")).lower() == 'true'
        
    if os.getenv("DEFAULT_USE_SUMMARY"):
        loaded_config["use_summary"] = str(os.getenv("DEFAULT_USE_SUMMARY")).lower() == 'true'
    
    if os.getenv("DEFAULT_PAGE_SELECTION"):
        loaded_config["page_selection"] = os.getenv("DEFAULT_PAGE_SELECTION")

    if os.getenv("DEFAULT_INCLUDE_DESCRIPTIONS"):
        loaded_config["include_descriptions"] = str(os.getenv("DEFAULT_INCLUDE_DESCRIPTIONS")).lower() == 'true'

    if os.getenv("DEFAULT_INCLUDE_TRANSCRIPTION"):
        loaded_config["include_transcription"] = str(os.getenv("DEFAULT_INCLUDE_TRANSCRIPTION")).lower() == 'true'

    if os.getenv("DEFAULT_SUMMARY_IN_OUTPUT"):
        loaded_config["summary_in_output"] = str(os.getenv("DEFAULT_SUMMARY_IN_OUTPUT")).lower() == 'true'

    logger.info("Configuration loaded from environment variables.")
    
    # Log configuration without sensitive data
    log_config = loaded_config.copy()
    for secret in ("openrouter_api_key", "qianfan_api_key"):
        if log_config.get(secret):
            log_config[secret] = f"***{log_config[secret][-5:]}" if len(log_config[secret]) > 5 else "*****"
    logger.debug(f"Effective configuration: {log_config}")
    
    return loaded_config

def _load_prompts_from_dir(directory: pathlib.Path) -> Dict[str, str]:
    """
    Load prompt templates found in a directory.

    Args:
        directory: Directory to read template files from

    Returns:
        Dict[str, str]: Templates found in the directory, keyed per PROMPT_FILES
    """
    templates: Dict[str, str] = {}

    if not directory.is_dir():
        return templates

    for key, filename in PROMPT_FILES.items():
        filepath = directory / filename
        if not filepath.is_file():
            continue
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                templates[key] = f.read()
        except Exception as e:
            logger.error(f"Error reading prompt file {filepath}: {e}")

    return templates

def load_prompt_templates() -> Dict[str, str]:
    """
    Load the effective prompt templates.

    Factory templates from PROMPTS_DIR are loaded first, then any user-saved
    overrides in USER_PROMPTS_DIR shadow them template-by-template. The factory
    files themselves are never modified, so defaults can always be restored.

    Returns:
        Dict[str, str]: Dictionary with loaded prompt templates
    """
    if not PROMPTS_DIR.is_dir():
        logger.error(f"Prompts directory '{PROMPTS_DIR}' not found.")

    templates = _load_prompts_from_dir(PROMPTS_DIR)
    overrides = _load_prompts_from_dir(USER_PROMPTS_DIR)

    if overrides:
        logger.info(f"Applying {len(overrides)} user prompt override(s) from '{USER_PROMPTS_DIR}'.")
        templates.update(overrides)

    logger.info(f"Loaded {len(templates)} prompt templates.")
    return templates

def get_factory_prompts() -> Dict[str, str]:
    """
    Get the factory (shipped) prompt templates, ignoring any user overrides.

    Returns:
        Dict[str, str]: Dictionary with the original prompt templates
    """
    global _FACTORY_PROMPTS_CACHE

    if _FACTORY_PROMPTS_CACHE is None:
        _FACTORY_PROMPTS_CACHE = _load_prompts_from_dir(PROMPTS_DIR)

    return dict(_FACTORY_PROMPTS_CACHE)

def reload_prompts() -> Dict[str, str]:
    """
    Force reload of the effective prompt templates from disk.

    Returns:
        Dict[str, str]: Updated prompt templates
    """
    global _PROMPTS_CACHE
    _PROMPTS_CACHE = load_prompt_templates()
    return dict(_PROMPTS_CACHE)

def save_user_prompts(new_prompts: Dict[str, str]) -> Dict[str, str]:
    """
    Persist prompt templates as the user's new defaults.

    Templates identical to the factory version (or blank) have their override
    removed instead of being written, so the user directory only ever contains
    real customizations and the factory defaults are never lost.

    Args:
        new_prompts: Mapping of template keys to their new default text

    Returns:
        Dict[str, str]: The effective prompt templates after saving
    """
    factory = get_factory_prompts()
    USER_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    for key, text in new_prompts.items():
        if key not in PROMPT_FILES:
            logger.warning(f"Ignoring unknown prompt template key: {key}")
            continue

        override_path = USER_PROMPTS_DIR / PROMPT_FILES[key]
        if text is None or not text.strip() or text == factory.get(key):
            if override_path.exists():
                override_path.unlink()
                logger.info(f"Removed prompt override for '{key}' (back to factory default).")
        else:
            with open(override_path, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"Saved prompt override for '{key}' to '{override_path}'.")

    return reload_prompts()

def reset_user_prompts() -> Dict[str, str]:
    """
    Remove all user prompt overrides, restoring the factory defaults.

    Returns:
        Dict[str, str]: The effective prompt templates after the reset
    """
    for filename in PROMPT_FILES.values():
        override_path = USER_PROMPTS_DIR / filename
        if override_path.exists():
            override_path.unlink()

    logger.info("All user prompt overrides removed; factory defaults restored.")
    return reload_prompts()

def save_user_settings(values: Dict[str, str]) -> Dict[str, Any]:
    """
    Persist settings to the user .env file and apply them immediately.

    Values are merged with any existing saved settings, so the OpenRouter and
    Ollama UIs can each save their own keys without clobbering the other's.
    An empty value removes the key.

    Args:
        values: Mapping of environment variable names to their new values

    Returns:
        Dict[str, Any]: The effective configuration after saving
    """
    existing: Dict[str, str] = {}
    if USER_ENV_FILE.is_file():
        existing = {k: v for k, v in dotenv_values(USER_ENV_FILE).items() if v is not None}

    for key, value in values.items():
        if value is None or str(value).strip() == "":
            existing.pop(key, None)
            os.environ.pop(key, None)
        else:
            existing[key] = str(value).strip()
            os.environ[key] = str(value).strip()

    USER_DIR.mkdir(parents=True, exist_ok=True)
    with open(USER_ENV_FILE, 'w', encoding='utf-8') as f:
        for key, value in existing.items():
            f.write(f"{key}={value}\n")

    logger.info(f"Saved {len(values)} setting(s) to '{USER_ENV_FILE}'.")
    return reload_config()

def reset_user_settings() -> Dict[str, Any]:
    """
    Remove all settings saved from the UI, reverting to built-in defaults
    (or the working-directory .env when running from source).

    Returns:
        Dict[str, Any]: The effective configuration after the reset
    """
    if USER_ENV_FILE.is_file():
        for key in dotenv_values(USER_ENV_FILE):
            os.environ.pop(key, None)
        USER_ENV_FILE.unlink()
        logger.info(f"Removed saved settings file '{USER_ENV_FILE}'.")

    return reload_config()

def load_future_ideas() -> str:
    """
    Load the user's saved "Future Ideas" notes.

    Returns:
        str: The saved notes, or an empty string if none exist
    """
    try:
        if FUTURE_IDEAS_FILE.is_file():
            with open(FUTURE_IDEAS_FILE, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        logger.error(f"Error reading future ideas file {FUTURE_IDEAS_FILE}: {e}")
    return ""

def save_future_ideas(text: str) -> None:
    """
    Persist the user's "Future Ideas" notes.

    Args:
        text: The notes to save
    """
    try:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        with open(FUTURE_IDEAS_FILE, 'w', encoding='utf-8') as f:
            f.write(text if text else "")
    except Exception as e:
        logger.error(f"Error saving future ideas file {FUTURE_IDEAS_FILE}: {e}")

def get_config() -> Dict[str, Any]:
    """
    Get the configuration from .env.
    
    This function loads the configuration only once and returns the cached version
    on subsequent calls, improving efficiency and ensuring consistency.
    
    Returns:
        Dict[str, Any]: Current configuration dictionary
    """
    global _CONFIG_CACHE
    
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = load_env_config()
        
    return _CONFIG_CACHE

def reload_config() -> Dict[str, Any]:
    """
    Force reload of configuration from .env.
    
    This function can be used when configuration needs to be explicitly refreshed.
    
    Returns:
        Dict[str, Any]: Updated configuration dictionary
    """
    global _CONFIG_CACHE
    _CONFIG_CACHE = load_env_config()
    return _CONFIG_CACHE

def get_prompts() -> Dict[str, str]:
    """
    Get the prompt templates.
    
    This function loads the prompt templates only once and returns the cached version
    on subsequent calls, improving efficiency.
    
    Returns:
        Dict[str, str]: Dictionary with loaded prompt templates
    """
    global _PROMPTS_CACHE
    
    if _PROMPTS_CACHE is None:
        _PROMPTS_CACHE = load_prompt_templates()
        
    return _PROMPTS_CACHE

def get_required_prompts_for_config(cfg: Dict[str, Any]) -> Dict[str, str]:
    """
    Get only the prompt templates required for the given configuration.
    
    This function determines which prompt templates are necessary based on the
    provided configuration and returns only those templates.
    
    Args:
        cfg (Dict[str, Any]): Configuration dictionary
        
    Returns:
        Dict[str, str]: Dictionary with required prompt templates
    """
    prompts = dict(get_prompts())

    # Per-run overrides (e.g. edited in the UI) shadow the saved defaults for
    # this conversion only; blank entries fall back to the defaults.
    custom_prompts = cfg.get("custom_prompts") or {}
    for key, text in custom_prompts.items():
        if key in PROMPT_FILES and isinstance(text, str) and text.strip():
            prompts[key] = text

    required_keys: List[str] = []

    has_markdown = cfg.get("use_markitdown", False)
    has_summary = cfg.get("use_summary", False)

    if cfg.get("include_descriptions", True):
        required_keys.append("vlm_base")
        if has_markdown and has_summary:
            required_keys.append("vlm_full")
        elif has_markdown:
            required_keys.append("vlm_markdown")
        elif has_summary:
            required_keys.append("vlm_summary")

    if cfg.get("include_transcription", False):
        required_keys.append("vlm_transcribe")

    if has_summary or cfg.get("summary_in_output", False):
        required_keys.append("summary")
        
    # Check if all required prompts are available
    missing = [key for key in required_keys if key not in prompts]
    if missing:
        logger.error(f"Missing required prompt templates: {', '.join(missing)}")
        return {}
        
    return {key: prompts[key] for key in required_keys if key in prompts}