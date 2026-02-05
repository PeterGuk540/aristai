import asyncio

from api.services.ui_action_broker import UiActionBroker


def test_broker_publish_and_listen():
    async def run():
        broker = UiActionBroker()
        payload = {"type": "ui.navigate", "payload": {"path": "/courses"}}
        await broker.publish(1, payload)
        queue = await broker.subscribe(1)
        message = await asyncio.wait_for(queue.get(), timeout=1)
        assert message == payload

    asyncio.run(run())
