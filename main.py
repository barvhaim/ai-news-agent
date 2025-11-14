import logging
import chainlit as cl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Morning routine ideation",
            message="Can you help me create a personalized morning routine that would help increase my productivity throughout the day? Start by asking me about my current habits and what activities energize me in the morning.",
        ),
        cl.Starter(
            label="Travel itinerary planning",
            message="I want to plan a week-long trip to Japan. Can you help me create an itinerary that includes must-see attractions, local cuisine recommendations, and cultural experiences? Start by asking me about my interests and travel preferences.",
        ),
        cl.Starter(
            label="Fitness goal setting",
            message="I want to set achievable fitness goals for the next three months. Can you help me create a workout plan and suggest healthy eating habits? Start by asking me about my current fitness level and dietary preferences.",
        ),
    ]


@cl.on_chat_start
def on_chat_start():
    logger.info("Chat started")


@cl.on_message
async def on_message(message: str):
    response = f"You said: {message}"
    await cl.Message(content=response).send()
