import os
from typing import Any
import chainlit as cl
from dotenv import load_dotenv
from beeai_framework.agents.react import ReActAgent
from beeai_framework.backend import ChatModel, ChatModelParameters
from beeai_framework.errors import FrameworkError
from beeai_framework.emitter import EmitterOptions, EventMeta
from beeai_framework.memory import TokenMemory
from beeai_framework.tools import AnyTool
from beeai_framework.tools.weather import OpenMeteoTool


load_dotenv()

def _get_llm():
    llm = ChatModel.from_name(
        f'openai:{os.getenv("OPENAI_CHAT_MODEL")}',
        ChatModelParameters(temperature=0),
    )
    return llm

def _create_agent():
    llm = _get_llm()
    tools: list[AnyTool] = [
        OpenMeteoTool(),
    ]
    agent = ReActAgent(llm=llm, tools=tools, memory=TokenMemory(llm))
    return agent


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Weather in Sderot",
            message="What's the weather like in Sderot today?",
        ),
    ]


@cl.on_chat_start
def on_chat_start():
    print("A new chat has started.")
    cl.user_session.set("current_thread", None)
    cl.user_session.set("agent", _create_agent())
    cl.user_session.set("last_tool_used", None)


@cl.on_chat_end
def on_chat_end():
    print("A new chat has ended.")
    cl.user_session.set("current_thread", None)
    cl.user_session.set("last_tool_used", None)


async def _process_agent_events(data: Any, event: EventMeta) -> None:
    """Process agent events and log appropriately"""

    if event.name == "error":
        await cl.Message(
            content=f"**Agent Error:** {FrameworkError.ensure(data.error).explain()}"
        ).send()
    elif event.name == "retry":
        print("Agent is retrying the action...")
    if event.name == "update":
        if data.update.key == "thought":
            await cl.Message(content=f"**Agent Thought:** {data.update.parsed_value}").send()

        elif data.update.key == "tool_name":
            cl.user_session.set(
                "last_tool_used",
                {"tool_name": data.update.parsed_value, "input": None, "output": None},
            )

        elif data.update.key == "tool_input":
            last_tool_used = cl.user_session.get("last_tool_used")
            if last_tool_used:
                last_tool_used["input"] = data.update.parsed_value
                cl.user_session.set("last_tool_used", last_tool_used)
        elif data.update.key == "tool_output":
            last_tool_used = cl.user_session.get("last_tool_used")
            if last_tool_used:
                last_tool_used["output"] = data.update.parsed_value
                cl.user_session.set("last_tool_used", last_tool_used)
                async with cl.Step(name=last_tool_used["tool_name"]) as step:
                    step.input = last_tool_used["input"]
                    step.output = last_tool_used["output"]
                cl.user_session.set("last_tool_used", None)
        else:
            print(f"Agent {data.update.key}: {data.update.parsed_value}")
    elif event.name == "start":
        print("Agent is starting new iteration...")
    elif event.name == "success":
        print("Agent successfully completed an action.")


@cl.on_message
async def on_message(message: cl.Message):
    agent = cl.user_session.get("agent")

    response = await agent.run(
        message.content, max_retries_per_step=3, total_max_retries=10, max_iterations=20
    ).on("*", _process_agent_events, EmitterOptions(match_nested=False))

    await cl.Message(content=response.last_message.text).send()
