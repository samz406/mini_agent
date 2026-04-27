# Chapter 1: LLM Client Abstraction

## What You'll Learn

This chapter teaches you how to build a clean, reusable abstraction layer over any LLM API. Rather than calling OpenAI directly everywhere in your code, you'll create an interface that can be swapped out for any provider.

## Core Concepts

### 1. Abstract Base Class (ABC) Pattern
The `BaseLLMClient` abstract class defines a contract: any LLM client must implement `complete()` and `stream()`. This lets you swap OpenAI for Anthropic, a local model, or a mock without changing any downstream code.

### 2. Retry Logic with Exponential Backoff
LLM APIs rate-limit you. Naive code crashes; production code retries. We implement exponential backoff: wait 1s, then 2s, then 4s before giving up. This handles transient failures gracefully.

### 3. Streaming
Instead of waiting for the entire response, `stream()` returns an `Iterator[str]` that yields tokens as they arrive. This is essential for good UX—users see output immediately instead of waiting.

### 4. The `Message` Dataclass
A simple `Message(role, content)` struct decouples your agent logic from API-specific formats. The client handles conversion to whatever format the API needs.

## Code Walkthrough

```python
# 1. Define the contract
class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, messages: list[Message]) -> Message: ...
    
    @abstractmethod  
    def stream(self, messages: list[Message]) -> Iterator[str]: ...

# 2. Implement for OpenAI
class OpenAIClient(BaseLLMClient):
    def complete(self, messages):
        # Retry on rate limit with exponential backoff
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(...)
                return Message(role="assistant", content=response.choices[0].message.content)
            except RateLimitError:
                time.sleep(2 ** attempt)
```

## How to Run

```bash
cd chapters/ch01_llm_client
export OPENAI_API_KEY=sk-your-key-here
python llm_client.py
```

You should see the assistant respond to "Hello! What can you do?" and then stream a second response token by token.
