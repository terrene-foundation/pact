# Streaming Responses

Real-time output streaming for AI agents.

## Concept

Streaming lets agents emit partial results during execution, enabling:
- Real-time UI updates
- Progress indicators
- Token-by-token LLM output
- Event-driven architectures

## StreamHandler

Define how to handle streaming events.

```python
from kailash_kaizen.streaming import StreamHandler

class PrintHandler(StreamHandler):
    def on_token(self, token: str):
        print(token, end="", flush=True)

    def on_complete(self, full_response: str):
        print(f"\n--- Complete ({len(full_response)} chars) ---")

    def on_error(self, error: Exception):
        print(f"\nError: {error}")
```

## StreamingAgent

Wrap an agent to emit streaming events.

```python
from kailash_kaizen import BaseAgent
from kailash_kaizen.streaming import StreamingAgent

class MyAgent(BaseAgent):
    def run(self, input_text):
        # Simulate streaming by yielding tokens
        words = input_text.split()
        for word in words:
            self.emit_token(word + " ")
        return {"response": input_text.upper()}

agent = MyAgent(name="streamer")
streaming = StreamingAgent(agent, handler=PrintHandler())
result = streaming.run("Hello world from streaming agent")
```

## TokenCollector

Collect all tokens for post-processing.

```python
from kailash_kaizen.streaming import TokenCollector

collector = TokenCollector()

# Collect tokens during execution
collector.add("Hello ")
collector.add("world ")
collector.add("!")

# Get collected output
full_text = collector.text()       # "Hello world !"
token_count = collector.count()    # 3
tokens = collector.tokens()        # ["Hello ", "world ", "!"]
```

## Channel-Based Streaming

```python
from kailash_kaizen.streaming import ChannelStreamHandler
import queue

# Create a channel for streaming events
event_queue = queue.Queue()
handler = ChannelStreamHandler(event_queue)

# Events are pushed to the queue
# Consumer can read from another thread
streaming = StreamingAgent(agent, handler=handler)

# In another thread:
while True:
    event = event_queue.get()
    if event.type == "token":
        process_token(event.data)
    elif event.type == "complete":
        break
```

## Stream Events

```python
from kailash_kaizen.streaming import StreamEvent

# Stream events have a type and data
event = StreamEvent(type="token", data="Hello ")
event = StreamEvent(type="complete", data="Hello world!")
event = StreamEvent(type="error", data="Connection timeout")
event = StreamEvent(type="metadata", data={"tokens": 150, "model": "gpt-5"})
```

## Web Streaming (with Nexus)

```python
from kailash_nexus import Nexus
from kailash_kaizen.streaming import StreamingAgent

app = Nexus()

@app.route("/chat/stream")
async def stream_chat(message: str):
    agent = MyAgent(name="chat")
    streaming = StreamingAgent(agent)

    async def generate():
        async for token in streaming.stream(message):
            yield f"data: {token}\n\n"

    return generate(), {"Content-Type": "text/event-stream"}
```

## Best Practices

1. **Flush output immediately** -- use `flush=True` for real-time display
2. **Handle errors in stream** -- implement `on_error` to handle mid-stream failures
3. **Use channels for async consumers** -- decouple production from consumption
4. **Buffer for UI** -- collect tokens into words/sentences for smoother display
5. **Set timeouts** -- prevent hanging streams from blocking resources

<!-- Trigger Keywords: streaming, real-time, tokens, stream handler, streaming agent, SSE, server-sent events -->
