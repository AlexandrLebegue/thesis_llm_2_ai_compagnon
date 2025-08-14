from typing import Dict, Callable, Any, List
import inspect
from dataclasses import dataclass

@dataclass
class ToolDefinition:
    name: str
    func: Callable
    description: str
    parameters: Dict[str, Any]
    returns: str

class ToolRegistry:
    """Registry for SmolAgents tools"""
    
    def __init__(self):
        self.tools = {}
    
    def register(self, name: str, description: str = None):
        """Decorator to register a tool"""
        def decorator(func):
            # Extract function signature
            sig = inspect.signature(func)
            parameters = {}
            
            for param_name, param in sig.parameters.items():
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else Any
                param_info = {
                    'type': param_type,
                    'required': param.default == inspect.Parameter.empty,
                    'default': param.default if param.default != inspect.Parameter.empty else None
                }
                parameters[param_name] = param_info
            
            # Create tool definition
            tool_def = ToolDefinition(
                name=name,
                func=func,
                description=description or func.__doc__ or '',
                parameters=parameters,
                returns=sig.return_annotation if sig.return_annotation != inspect.Signature.empty else Any
            )
            
            self.tools[name] = tool_def
            return func
        return decorator
    
    def get_tool(self, name: str) -> ToolDefinition:
        """Get tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tools"""
        return list(self.tools.keys())
    
    def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool with given parameters"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        
        # Validate parameters
        for param_name, param_info in tool.parameters.items():
            if param_info['required'] and param_name not in kwargs:
                raise ValueError(f"Required parameter '{param_name}' missing for tool '{name}'")
        
        return tool.func(**kwargs)

# Global registry instance
tool_registry = ToolRegistry()