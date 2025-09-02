import yetter
import asyncio

YOUR_API_KEY = ""

async def main():
    yetter.configure(api_key=YOUR_API_KEY)
    result = await yetter.subscribe("ytr-ai/qwen/image/t2i", args={"prompt": "A beautiful landscape with a river and mountains", "num_images": 2}, on_queue_update=print)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
