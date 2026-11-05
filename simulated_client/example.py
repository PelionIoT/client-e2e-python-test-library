"""Stand in for mbedCloudClientExample.elf with a simulated device.

The suite starts the binary named by --local_binary and matches lines of its
output. A real example registers by itself, prints its device id and keeps its
resources, so this program does too, over testapp.py and one device-simulator
device. It bootstraps and registers against the stage over real TLS.

Factory reset and reboot come from the cloud as /3/0/5 and /3/0/4. Testapp holds
the shell of the system tests, so stdin stays connected but drives nothing here.
"""
import asyncio
import logging
import os

from aiocoap.message import Message
from aiocoap.numbers.codes import Code
from aiocoap.numbers.types import Type

import testapp
from base_resource import BaseResource
from bootstrap import Bootstrap


class FactoryReset(BaseResource):
    """/3/0/5: storage goes, so the next boot bootstraps again as a new developer device."""

    async def render_post(self, request):
        self.obj.set_message_time()
        self.obj.app.factory_reset = True
        return Message(mid=request.mid, mtype=Type.ACK, code=Code.CHANGED)


class Example(testapp.Testapp):
    def __init__(self, loop):
        super().__init__(loop)
        self.factory_reset = False
        # Object 3 of the simulator's model has no factory reset resource.
        self.device.model.data['3']['0']['5'] = ''

    def registered(self):
        super().registered()
        testapp.say('Client registered')
        testapp.say('Device ID: {}'.format(self.device.id))

    async def rebooted(self):
        await super().rebooted()
        await self.setup()


class ExampleDevice(testapp.SimulatedDevice):
    def reboot_device(self):
        if not self.app.factory_reset:
            super().reboot_device()
            return
        self.app.factory_reset = False
        self.lwm2m_object.deregister = True
        asyncio.ensure_future(self.bootstrap_again())

    async def bootstrap_again(self):
        await asyncio.sleep(1)
        old = self.lwm2m_object
        for node in old.observation_pool:
            node.cancel_observation()
        old.remote_ep = None
        await old.protocol.shutdown()
        self.lwm2m_object = None
        self.bootstrapped = False
        self.bootstrap_object = Bootstrap(self.config, self)
        await self.app.setup()


def add_example_resources(original):
    def set_resource_pool(self):
        original(self)
        self.resource_pool[('3', '0', '5')] = FactoryReset(self.config, ('3', '0', '5'), self, False)
        # The registration offers every resource for auto-observation, and the cloud subscribes on that token.
        if ('1', '0', '1') not in self.aobs_path['1']['observation_list']:
            self.aobs_path['1']['observation_list'].append(('1', '0', '1'))
    return set_resource_pool


def main():
    testapp.Lwm2m.set_resource_pool = add_example_resources(testapp.Lwm2m.set_resource_pool)
    testapp.SimulatedDevice = ExampleDevice
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(filename=os.environ.get('SIMULATED_CLIENT_LOG', '/tmp/simulated-client.log'),
                        level=logging.INFO, format='%(asctime)s %(process)d %(name)s %(message)s')
    logging.getLogger('coap').setLevel(logging.WARNING)
    os.environ['AIOCOAP_CLIENT_TRANSPORT'] = 'udptls' if testapp.TRANSPORT.startswith('UDP') else 'tlsclient'
    loop = asyncio.get_event_loop()
    app = Example(loop)
    asyncio.ensure_future(app.setup())
    loop.run_forever()


if __name__ == '__main__':
    main()
