import yetter
import asyncio

YOUR_API_KEY = ""

async def main():
    yetter.configure(api_key=YOUR_API_KEY)
    upload_url = await yetter.upload_file("your_file_name")
    result = await yetter.run("ytr-ai/qwen/image/t2i", args={"prompt": "A beautiful landscape with a river and mountains for stream", "input_url": upload_url})
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
