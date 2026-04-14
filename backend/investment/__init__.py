"""
Investment Tool Module

Contains investment analysis and recommendations engine
"""

from .investment_recommendation_tool import investment_tool
from .investment_routes import router

__all__ = ["investment_tool", "router"]
