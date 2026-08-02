"""
Model Configuration System
JSON-based centralized configuration for all AI models including temperature, max_tokens, and other model-specific settings
Supports multiple providers: OpenAI, Groq, etc.
"""

import json
import os
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class ModelSettings:
    """Settings for a specific AI model"""
    temperature: Optional[float] = None  # None means use default
    max_tokens: Optional[int] = None     # None means use default
    supports_streaming: bool = True
    supports_function_calling: bool = True
    max_context_length: int = 4096
    model_type: str = "gpt"  # gpt, claude, gemini, llama, etc.
    provider: str = "openai"  # openai, groq, anthropic, etc.
    reasoning_effort: Optional[str] = None  # "low", "medium", "high"
    reasoning_summary: Optional[str] = None  # reserved for future use

    def to_llm_kwargs(self) -> Dict[str, Any]:
        """Convert to kwargs that can be passed to LangChain LLM constructors"""
        kwargs = {}

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens

        # Use flat reasoning_effort with Chat Completions API
        # (Responses API is not compatible with LangGraph/DeepAgent)
        if self.reasoning_effort is not None:
            kwargs["reasoning_effort"] = self.reasoning_effort

        return kwargs


def create_llm_instance(model_name: str, model_config: ModelSettings, **override_kwargs):
    """
    Create appropriate LLM instance based on provider
    Returns the configured LLM instance ready for use with LangChain agents
    """
    provider = model_config.provider.lower()
    
    # Get base kwargs from model config
    llm_kwargs = model_config.to_llm_kwargs()
    llm_kwargs.update(override_kwargs)
    
    # For Groq models with namespace (e.g., 'openai/gpt-oss-120b', 'meta-llama/llama-4-maverick-17b-128e-instruct'),
    # keep the full model name as Groq API expects it
    # For other providers or simple model names, use as-is
    actual_model_name = model_name
    
    # Add model name (different providers may expect different parameter names)
    if provider == "groq":
        llm_kwargs["model_name"] = actual_model_name  # Groq uses model_name with full namespace
    else:
        llm_kwargs["model"] = actual_model_name  # OpenAI uses model
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        
        # Get OpenAI API key from environment or override
        if "openai_api_key" not in llm_kwargs:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                llm_kwargs["openai_api_key"] = api_key

        if "base_url" not in llm_kwargs:
            base_url = os.getenv("OPENAI_BASE_URL")
            if base_url:
                llm_kwargs["base_url"] = base_url
        
        return ChatOpenAI(**llm_kwargs)
        
    elif provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError:
            raise ImportError(
                "langchain-groq package is required for Groq models. "
                "Install it with: pip install langchain-groq"
            )

        # Get Groq API key from environment or override
        if "api_key" not in llm_kwargs and "groq_api_key" not in llm_kwargs:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                llm_kwargs["api_key"] = api_key
        
        return ChatGroq(**llm_kwargs)
        
    elif provider == "xai":
        from langchain_openai import ChatOpenAI

        # xAI uses OpenAI-compatible API
        # Get xAI API key from environment or override
        if "openai_api_key" not in llm_kwargs and "api_key" not in llm_kwargs:
            api_key = os.getenv("XAI_API_KEY")
            if api_key:
                llm_kwargs["openai_api_key"] = api_key

        # Set xAI base URL
        if "base_url" not in llm_kwargs:
            llm_kwargs["base_url"] = "https://api.x.ai/v1"

        return ChatOpenAI(**llm_kwargs)

    elif provider == "deepinfra":
        from langchain_openai import ChatOpenAI

        # DeepInfra uses OpenAI-compatible API
        if "openai_api_key" not in llm_kwargs and "api_key" not in llm_kwargs:
            api_key = os.getenv("DEEPINFRA_API_KEY")
            if api_key:
                llm_kwargs["openai_api_key"] = api_key

        if "base_url" not in llm_kwargs:
            llm_kwargs["base_url"] = "https://api.deepinfra.com/v1/openai"

        return ChatOpenAI(**llm_kwargs)

    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: openai, groq, xai, deepinfra")


class ModelConfigManager:
    """Manages model configurations loaded from JSON file"""
    
    def __init__(self):
        self._model_configs: Dict[str, Dict[str, Any]] = {}  # Store full model data
        self._fallback_config: Optional[ModelSettings] = None
        self._default_model: Optional[str] = None
        self._categories: Dict[str, Dict[str, Any]] = {}
    
    def get_model_config(self, model_name: str) -> ModelSettings:
        """Get configuration for a specific model"""
        model_name_lower = model_name.lower()
        
        # Try exact match first
        if model_name_lower in self._model_configs:
            model_data = self._model_configs[model_name_lower]
            settings = model_data.get('settings', {})
            # Include provider from top-level model data
            settings['provider'] = model_data.get('provider', 'openai')
            return ModelSettings(**settings)
        
        # Fall back to fallback config if available
        if self._fallback_config:
            return self._fallback_config
        
        # Final fallback to basic config
        return ModelSettings()
    
    def get_llm_kwargs(self, model_name: str, **override_kwargs) -> Dict[str, Any]:
        """Get LLM kwargs for a specific model, with optional overrides"""
        config = self.get_model_config(model_name)
        kwargs = config.to_llm_kwargs()
        
        # Apply overrides
        kwargs.update(override_kwargs)
        
        # Add model name (provider-specific)
        if config.provider.lower() == "groq":
            kwargs["model_name"] = model_name
        else:
            kwargs["model"] = model_name
        
        return kwargs
    
    def create_llm(self, model_name: str, **override_kwargs):
        """Create LLM instance for the specified model"""
        config = self.get_model_config(model_name)
        return create_llm_instance(model_name, config, **override_kwargs)
    
    def get_provider(self, model_name: str) -> str:
        """Get the provider for a specific model"""
        config = self.get_model_config(model_name)
        return config.provider
    
    def supports_streaming(self, model_name: str) -> bool:
        """Check if a model supports streaming"""
        config = self.get_model_config(model_name)
        return config.supports_streaming
    
    def supports_function_calling(self, model_name: str) -> bool:
        """Check if a model supports function calling"""
        config = self.get_model_config(model_name)
        return config.supports_function_calling
    
    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all available models with their metadata for UI"""
        result = {}
        for model_name, model_data in self._model_configs.items():
            if model_data.get('enabled', True):
                settings = model_data.get('settings', {})
                settings['provider'] = model_data.get('provider', 'openai')
                config = ModelSettings(**settings)
                
                result[model_name] = {
                    "settings": config,
                    "display_name": model_data.get('display_name', model_name.title()),
                    "description": model_data.get('description', ''),
                    "category": model_data.get('category', 'other'),
                    "provider": model_data.get('provider', 'openai'),
                    "enabled": model_data.get('enabled', True),
                    "ui": model_data.get('ui', {})
                }
        return result
    
    def get_models_by_provider(self, provider: str) -> Dict[str, Dict[str, Any]]:
        """Get all models for a specific provider"""
        all_models = self.get_available_models()
        return {
            name: data for name, data in all_models.items() 
            if data.get('provider', '').lower() == provider.lower()
        }
    
    def get_categories(self) -> Dict[str, Dict[str, Any]]:
        """Get model categories for UI organization"""
        return self._categories.copy()
    
    def get_default_model(self) -> Optional[str]:
        """Get the default model name"""
        return self._default_model
    
    def load_from_file(self, config_file_path: str):
        """Load model configurations from a JSON file"""
        if not os.path.exists(config_file_path):
            raise FileNotFoundError(f"Model configuration file not found: {config_file_path}")
        
        try:
            with open(config_file_path, 'r') as f:
                config_data = json.load(f)
            
            # Load models (store full model data including provider info)
            models = config_data.get('models', {})
            for model_name, model_data in models.items():
                self._model_configs[model_name.lower()] = model_data
            
            # Load categories
            self._categories = config_data.get('categories', {})
            
            # Load default model
            self._default_model = config_data.get('default_model')
            
            # Load fallback settings
            fallback = config_data.get('fallback_settings', {})
            if fallback:
                self._fallback_config = ModelSettings(**fallback)
                
        except Exception as e:
            raise Exception(f"Failed to load model configuration from {config_file_path}: {e}")
    
    def list_configured_models(self) -> Dict[str, ModelSettings]:
        """Get all configured models as ModelSettings objects"""
        result = {}
        for model_name, model_data in self._model_configs.items():
            settings = model_data.get('settings', {})
            settings['provider'] = model_data.get('provider', 'openai')
            result[model_name] = ModelSettings(**settings)
        return result


# Global model config manager instance
model_config_manager = ModelConfigManager()


def get_model_config(model_name: str) -> ModelSettings:
    """Convenience function to get model configuration"""
    return model_config_manager.get_model_config(model_name)


def get_llm_kwargs(model_name: str, **kwargs) -> Dict[str, Any]:
    """Convenience function to get LLM kwargs for a model"""
    return model_config_manager.get_llm_kwargs(model_name, **kwargs)


def get_available_models() -> Dict[str, Dict[str, Any]]:
    """Convenience function to get all available models for UI"""
    return model_config_manager.get_available_models()


def get_categories() -> Dict[str, Dict[str, Any]]:
    """Convenience function to get model categories for UI"""
    return model_config_manager.get_categories()


def get_default_model() -> Optional[str]:
    """Convenience function to get default model"""
    return model_config_manager.get_default_model()


def init_model_config(config_file_path: str):
    """Initialize model configuration system from JSON file"""
    model_config_manager.load_from_file(config_file_path)
    
    model_count = len(model_config_manager.list_configured_models())
    print(f"[MODEL CONFIG] Initialized with {model_count} model configurations from {config_file_path}")
    
    # Log some example configurations
    default_model = model_config_manager.get_default_model()
    if default_model:
        print(f"[MODEL CONFIG] Default model: {default_model}")
    
    for model_name in ["gpt-4o", "gpt-5-nano", "o1-mini"]:
        if model_name.lower() in model_config_manager._model_configs:
            config = model_config_manager.get_model_config(model_name)
            print(f"[MODEL CONFIG] {model_name}: temp={config.temperature}, streaming={config.supports_streaming}")
