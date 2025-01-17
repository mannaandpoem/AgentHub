from typing import List, Literal, Optional, Dict

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.config import LLMSettings, config


class LLM:
    _instances: Dict[str, "LLM"] = {}

    def __new__(cls, config_name: str = "default", llm_config: Optional[LLMSettings] = None):
        if config_name not in cls._instances:
            instance = super().__new__(cls)
            instance.__init__(config_name, llm_config)
            cls._instances[config_name] = instance
        return cls._instances[config_name]

    def __init__(self, config_name: str = "default", llm_config: Optional[LLMSettings] = None):
        if not hasattr(self, 'client'):  # Only initialize if not already initialized
            llm_config = llm_config or config.llm
            llm_config = llm_config.get(config_name, llm_config["default"])
            self.model = llm_config.model
            self.max_tokens = llm_config.max_tokens
            self.temperature = llm_config.temperature
            self.client = AsyncOpenAI(api_key=llm_config.api_key, base_url=llm_config.base_url)

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    async def ask(
            self,
            messages: List[dict],
            system_msgs: Optional[str] = None,
            stream: bool = True,
    ) -> str:
        """
        Send a prompt to the LLM and get the response.

        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            stream (bool): Whether to stream the response.

        Returns:
            str: The generated response.
        """
        # Construct messages
        if system_msgs:
            messages = [{"role": "system", "content": system_msgs}] + messages

        if not stream:
            # For non-streaming requests
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=False,
            )
            return response.choices[0].message.content

        # For streaming requests
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )

        collected_messages = []

        async for chunk in response:
            # Collect each streaming chunk
            chunk_message = chunk.choices[0].delta.content or ""
            collected_messages.append(chunk_message)

            # Optionally print the chunk to the console
            print(chunk_message, end="", flush=True)

        print()  # Newline after streaming
        return "".join(collected_messages).strip()

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    async def ask_tool(
        self,
        messages: List[dict],
        system_msgs: Optional[List[str]] = None,
        timeout: int = 60,
        tools: Optional[List[dict]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        **kwargs,
    ):
        """
        Ask LLM using functions/tools and return the response.

        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            timeout: Request timeout in seconds
            tools: List of tools to use
            tool_choice: Tool choice strategy
            **kwargs: Additional completion arguments

        Returns:
            ChatCompletionMessage: The model's response
        """
        # Add system messages if provided
        if system_msgs:
            messages = [
                {"role": "system", "content": msg} for msg in system_msgs
            ] + messages

        # Set up the completion requirement
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            timeout=timeout,
            **kwargs,
        )

        # Return the first message
        return response.choices[0].message


async def main():
    llm = LLM()
    response = await llm.ask(
        messages=[{"role": "user", "content": "What is the weather today?"}], stream=False
    )
    print(response)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather of an location, the user shoud supply a location first",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        }
                    },
                    "required": ["location"],
                },
            },
        },
    ]
    response = await llm.ask_tool(
        [{"role": "user", "content": "what is the weather today? using tool"}],
        tools=tools,
        tool_choice="auto",
    )
    print(response.tool_calls)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
