"""LiteLLM adapter implementing ILLMProvider."""

import asyncio
import json
from typing import Dict, List, Optional, Type

import litellm
from litellm import completion, embedding
from pydantic import BaseModel, ValidationError

from src.config import settings
from src.domain.interfaces import ILLMProvider


class LiteLLMAdapter(ILLMProvider):
    """LiteLLM adapter for LLM operations."""

    def __init__(self, model: Optional[str] = None):
        """Initialize adapter with model configuration.

        Args:
            model: Model name (defaults to config setting).
        """
        self.model = model or settings.litellm_model

        # Configure LiteLLM
        if settings.openai_api_key:
            litellm.api_key = settings.openai_api_key

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate a chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model name (overrides default).
            temperature: Sampling temperature.

        Returns:
            Generated text response.

        Raises:
            Exception: If completion fails after retries.
        """
        model_name = model or self.model
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Run blocking completion in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: completion(
                        model=model_name,
                        messages=messages,
                        temperature=temperature,
                    ),
                )

                # Extract content from response
                if hasattr(response, "choices") and len(response.choices) > 0:
                    return response.choices[0].message.content or ""

                return ""

            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        return ""

    async def structured_completion(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> BaseModel:
        """Generate a structured completion using JSON schema.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            response_model: Pydantic model class for structured output.
            model: Model name (overrides default).
            temperature: Sampling temperature.

        Returns:
            Instance of response_model with parsed structured data.

        Raises:
            Exception: If completion fails after retries or parsing fails.
        """
        model_name = model or self.model
        max_retries = 3
        retry_delay = 1.0

        # Generate JSON schema from Pydantic model
        schema = response_model.model_json_schema()
        
        # Simplify schema for prompt (remove metadata, keep structure)
        simplified_schema = {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", [])
        }
        
        # Add instruction to response format for OpenAI-compatible models
        # For other models, we'll parse JSON from response
        use_json_mode = model_name and (
            "gpt-4" in model_name.lower() 
            or "gpt-3.5" in model_name.lower()
            or "o1" in model_name.lower()
        )

        for attempt in range(max_retries):
            try:
                # Prepare completion parameters
                completion_kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                # Use response_format for OpenAI models (JSON mode)
                if use_json_mode:
                    completion_kwargs["response_format"] = {"type": "json_object"}
                    # For OpenAI JSON mode, we don't need to add schema to prompt
                    # Just ensure the user message asks for JSON format
                    enhanced_messages = messages.copy()
                    
                    # Get field names from schema for instruction
                    field_names = list(simplified_schema.get("properties", {}).keys())
                    field_list = ", ".join(f'"{f}"' for f in field_names)
                    
                    # Add simple JSON format reminder to last user message
                    json_reminder = f"\n\nRespond with a JSON object containing these fields: {field_list}. Return actual data values, not a schema definition."
                    
                    if enhanced_messages and enhanced_messages[-1].get("role") == "user":
                        enhanced_messages[-1]["content"] += json_reminder
                    
                    completion_kwargs["messages"] = enhanced_messages
                else:
                    # For non-OpenAI models, add instruction to user message
                    enhanced_messages = messages.copy()
                    field_names = list(simplified_schema.get("properties", {}).keys())
                    field_list = ", ".join(f'"{f}"' for f in field_names)
                    
                    json_instruction = f"""

CRITICAL: Respond with ONLY valid JSON containing ACTUAL DATA VALUES, not the schema structure.
Do NOT return the schema definition. Return actual data that matches the schema.

Required fields: {field_list}

Example of CORRECT response (actual data):
{{"title": "Example title", "description": "Example description", "acceptance_criteria": ["Criterion 1"]}}

Example of WRONG response (schema structure - DO NOT DO THIS):
{{"type": "object", "properties": {{"title": {{"type": "string"}}}}}}

Return ONLY the data values, not the schema definition.
"""
                    if enhanced_messages and enhanced_messages[-1].get("role") == "user":
                        enhanced_messages[-1]["content"] += json_instruction
                    else:
                        enhanced_messages.append({
                            "role": "user",
                            "content": json_instruction
                        })
                    completion_kwargs["messages"] = enhanced_messages

                # Run blocking completion in executor
                loop = asyncio.get_event_loop()
                
                def _completion():
                    return completion(**completion_kwargs)
                
                response = await loop.run_in_executor(None, _completion)

                # Extract content from response
                if not (hasattr(response, "choices") and len(response.choices) > 0):
                    raise ValueError("No choices in response")
                
                content = response.choices[0].message.content or ""
                if not content:
                    raise ValueError("Empty response content")

                # Parse JSON from response
                try:
                    # Try to extract JSON if wrapped in markdown code blocks
                    if "```json" in content:
                        json_start = content.find("```json") + 7
                        json_end = content.find("```", json_start)
                        if json_end > json_start:
                            content = content[json_start:json_end].strip()
                    elif "```" in content:
                        json_start = content.find("```") + 3
                        json_end = content.find("```", json_start)
                        if json_end > json_start:
                            content = content[json_start:json_end].strip()
                    
                    # Remove any leading/trailing whitespace
                    content = content.strip()
                    
                    # Check if content looks like a schema definition (common mistake)
                    if '"properties"' in content and '"type": "object"' in content:
                        # LLM returned schema instead of data - try to extract example or fail
                        raise ValueError(
                            "LLM returned JSON schema instead of data. "
                            "This usually means the model misunderstood the instruction. "
                            f"Response: {content[:500]}"
                        )
                    
                    # Parse JSON
                    parsed_data = json.loads(content)
                    
                    # Check if parsed_data is actually the schema (has 'properties' key at top level)
                    if isinstance(parsed_data, dict) and "properties" in parsed_data and "type" in parsed_data:
                        raise ValueError(
                            "LLM returned JSON schema instead of data. "
                            "The response contains schema structure rather than actual data values."
                        )
                    
                    # Normalize data before validation (handle common LLM variations)
                    if isinstance(parsed_data, dict):
                        # Normalize InvestCritique violations if present
                        if "violations" in parsed_data and isinstance(parsed_data["violations"], list):
                            for v in parsed_data["violations"]:
                                if isinstance(v, dict) and "criterion" in v:
                                    v["criterion"] = str(v["criterion"]).upper()
                    
                    # Try to validate and create Pydantic model instance
                    try:
                        return response_model(**parsed_data)
                    except ValidationError as validation_error:
                        # If validation fails, try to transform the data for structured models
                        # This handles cases where LLM returns different field names
                        from src.domain.schema import (
                            InvestViolation,
                            InvestCritique,
                            FeasibilityAssessment,
                            TechnicalDependency,
                            TechnicalConcern,
                        )
                        
                        if response_model == InvestCritique and isinstance(parsed_data, dict) and "violations" in parsed_data:
                                # Transform violations if present
                                transformed_violations = []
                                for v in parsed_data["violations"]:
                                    if isinstance(v, dict):
                                        try:
                                            # Normalize criterion to uppercase first
                                            if "criterion" in v:
                                                v["criterion"] = str(v["criterion"]).upper()
                                            elif "INVEST_criterion" in v:
                                                criterion_val = str(v["INVEST_criterion"])
                                                # Map full names to letters if needed
                                                criterion_map = {
                                                    "independent": "I", "i": "I",
                                                    "negotiable": "N", "n": "N",
                                                    "valuable": "V", "v": "V",
                                                    "estimable": "E", "e": "E",
                                                    "small": "S", "s": "S",
                                                    "testable": "T", "t": "T",
                                                }
                                                v["criterion"] = criterion_map.get(criterion_val.lower(), criterion_val.upper())
                                            # Use the from_llm_response method to handle field name variations
                                            transformed_violations.append(InvestViolation.from_llm_response(v))
                                        except Exception as e:
                                            # If transformation fails, try direct creation as fallback
                                            try:
                                                # Ensure criterion is uppercase
                                                if "criterion" in v:
                                                    v["criterion"] = str(v["criterion"]).upper()
                                                transformed_violations.append(InvestViolation(**v))
                                            except Exception:
                                                # Last resort: create with minimal required fields
                                                criterion_val = str(v.get("criterion") or v.get("INVEST_criterion", "S")).upper()
                                                transformed_violations.append(InvestViolation(
                                                    criterion=criterion_val[0] if len(criterion_val) > 0 else "S",
                                                    severity=(v.get("severity") or v.get("Severity", "critical")).lower(),
                                                    description=v.get("description") or v.get("Evidence", "Violation"),
                                                ))
                                parsed_data["violations"] = [v.model_dump() for v in transformed_violations]
                                
                                # Try again with transformed data
                                try:
                                    return InvestCritique(**parsed_data)
                                except ValidationError as e2:
                                    # If still fails, raise with more context
                                    raise ValueError(
                                        f"Response does not match schema after transformation: {e2}. "
                                        f"Original error: {validation_error}. Parsed data: {parsed_data}"
                                    )
                        elif response_model == InvestViolation and isinstance(parsed_data, dict):
                            # Transform single violation
                            try:
                                return InvestViolation.from_llm_response(parsed_data)
                            except Exception:
                                pass  # Will raise original error below
                        elif response_model == FeasibilityAssessment and isinstance(parsed_data, dict):
                            from src.domain.schema import TechnicalDependency, TechnicalConcern
                            
                            # Transform dependencies if present
                            if "dependencies" in parsed_data:
                                transformed_deps = []
                                for dep in parsed_data["dependencies"]:
                                    if isinstance(dep, dict):
                                        try:
                                            transformed_deps.append(TechnicalDependency.from_llm_response(dep))
                                        except Exception:
                                            # Fallback: try direct creation
                                            try:
                                                transformed_deps.append(TechnicalDependency(**dep))
                                            except Exception:
                                                # Last resort: create with minimal fields
                                                dep_type = dep.get("dependency_type") or dep.get("type", "other")
                                                transformed_deps.append(TechnicalDependency(
                                                    dependency_type=dep_type,
                                                    description=dep.get("description") or dep.get("detail") or f"{dep_type} dependency",
                                                    blocking=dep.get("blocking", False),
                                                ))
                                    else:
                                        transformed_deps.append(dep)
                                parsed_data["dependencies"] = [d.model_dump() for d in transformed_deps]
                            
                            # Transform concerns if present
                            if "concerns" in parsed_data:
                                transformed_concerns = []
                                for concern in parsed_data["concerns"]:
                                    if isinstance(concern, dict):
                                        try:
                                            transformed_concerns.append(TechnicalConcern.from_llm_response(concern))
                                        except Exception:
                                            # Fallback: try direct creation
                                            try:
                                                transformed_concerns.append(TechnicalConcern(**concern))
                                            except Exception:
                                                # Last resort: create with minimal fields
                                                transformed_concerns.append(TechnicalConcern(
                                                    severity=(concern.get("severity") or "medium").lower(),
                                                    description=concern.get("description") or concern.get("detail") or "Technical concern",
                                                    recommendation=concern.get("recommendation") or concern.get("suggestion"),
                                                ))
                                    else:
                                        transformed_concerns.append(concern)
                                parsed_data["concerns"] = [c.model_dump() for c in transformed_concerns]
                            
                            # Try again with transformed data
                            try:
                                return FeasibilityAssessment(**parsed_data)
                            except ValidationError as e2:
                                # If still fails, raise with more context
                                raise ValueError(
                                    f"Response does not match schema after transformation: {e2}. "
                                    f"Original error: {validation_error}. Parsed data: {parsed_data}"
                                )
                        
                        # If transformation didn't work or wasn't applicable, raise original error
                        raise ValueError(f"Response does not match schema: {validation_error}. Parsed data: {parsed_data}")
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse JSON from response: {e}. Content: {content[:500]}")

            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        raise ValueError("Failed to get structured completion after retries")

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.

        Raises:
            Exception: If embedding fails after retries.
        """
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Run blocking embedding in executor
                # Need to capture variables for executor
                model_name = settings.embedding_model
                text_input = text
                
                def _get_embedding():
                    from litellm import embedding as litellm_embedding
                    return litellm_embedding(
                        model=model_name,
                        input=[text_input],
                    )
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, _get_embedding)

                # Extract embedding from response
                # LiteLLM returns EmbeddingResponse object with data attribute
                if hasattr(response, "data") and isinstance(response.data, list) and len(response.data) > 0:
                    if isinstance(response.data[0], dict) and "embedding" in response.data[0]:
                        embedding = response.data[0]["embedding"]
                        if embedding and len(embedding) > 0:
                            return embedding
                    elif isinstance(response.data[0], list):
                        embedding = response.data[0]
                        if embedding and len(embedding) > 0:
                            return embedding
                
                # Fallback: try list format (older LiteLLM versions)
                if isinstance(response, list) and len(response) > 0:
                    if isinstance(response[0], dict) and "embedding" in response[0]:
                        embedding = response[0]["embedding"]
                        if embedding and len(embedding) > 0:
                            return embedding
                    elif isinstance(response[0], list):
                        embedding = response[0]
                        if embedding and len(embedding) > 0:
                            return embedding
                
                # If we get here, the response format is unexpected
                raise ValueError(
                    f"Unexpected embedding response format: {type(response)}. "
                    f"Response: {str(response)[:200]}"
                )

            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        return []
