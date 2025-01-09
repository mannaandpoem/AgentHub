import asyncio

from app.agent.midwit import MidwitAgent


async def main():
    # agent = CodeActAgent()
    agent = MidwitAgent()
    while True:
        try:
            prompt = input("\nEnter your prompt (or 'exit' to quit): ")
            if prompt.lower() == "exit":
                print("Goodbye!")
                break
            print("\nProcessing your request...\n")
            await agent.run(prompt)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
