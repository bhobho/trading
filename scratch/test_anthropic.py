import asyncio
import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

async def test_key():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip('"').strip("'")
    if not key:
        print("No key found")
        return
    
    client = AsyncAnthropic(api_key=key)
    try:
        # Try a simple message with Haiku (cheapest)
        message = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
        print(f"Haiku Success: {message.content[0].text}")
    except Exception as e:
        print(f"Haiku Failed: {e}")

    try:
        # Try Sonnet 3.5
        message = await client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
        print(f"Sonnet 3.5 Success: {message.content[0].text}")
    except Exception as e:
        print(f"Sonnet 3.5 Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())
