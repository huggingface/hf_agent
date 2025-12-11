import asyncio
import os

from amp_sdk import AmpOptions, execute

prompt = """
what account am I logged in as?
"""


async def main():
    # Use the toolbox directory to share tools with Amp
    toolbox_dir = os.path.join(os.getcwd(), "toolbox")
    messages = []
    async for message in execute(
        prompt,
        AmpOptions(
            cwd=os.getcwd(),
            toolbox=toolbox_dir,
            visibility="workspace",
            dangerously_allow_all=True,
        ),
    ):
        messages.append(message)

    for msg in messages:
        print(msg.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
