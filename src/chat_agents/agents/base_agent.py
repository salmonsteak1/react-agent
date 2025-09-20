from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


SUPPORTED_PROVIDERS = ["openai"]


class BaseAgent(ABC):
    """Abstract base class for AI agents with tool calling capabilities."""
    
    PROVIDER: str = ""
    MODEL: str = ""
    NAME: str = "BaseAgent"
    TOOLS: List[Dict[str, Any]] = []
    INSTRUCTIONS: str = ""
    
    def __init__(self):
        self.validate_configuration()
    
    def validate_configuration(self):
        """Validate that the agent is properly configured."""
        if not self.PROVIDER:
            raise ValueError(f"{self.__class__.__name__} must define PROVIDER")
        if self.PROVIDER not in SUPPORTED_PROVIDERS:
            raise ValueError(f"{self.__class__.__name__} must define a supported provider: {SUPPORTED_PROVIDERS}")
        if not self.MODEL:
            raise ValueError(f"{self.__class__.__name__} must define MODEL")
        if not self.NAME:
            raise ValueError(f"{self.__class__.__name__} must define NAME")
        if not self.INSTRUCTIONS:
            raise ValueError(f"{self.__class__.__name__} must define INSTRUCTIONS")
