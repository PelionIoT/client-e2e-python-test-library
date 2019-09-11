import logging

logging.basicConfig(format="%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

PATTERN = '1:2:3:4'
RESOURCE_PATH = '3201/0/5853'


def test_01_get_device_id(cloud, client):
    log.info('Device registered to cloud with device id: {}'.format(client.endpoint_id()))
    cloud.device_directory.get_device(client.endpoint_id(), expected_status_code=200)


def test_02_subscribe_resource(cloud, client):
    r = cloud.connect.set_subscription_for_resource(client.endpoint_id(), '3200/0/5501', expected_status_code=202)
    log.info('Set subscription for resource "3200/0/5501". Async-id: "{}"'.format(r.json()['async-response-id']))
    client.wait_for_output(b'Message status callback: (3200/0/5501) subscribed', timeout=60)


def test_03_get_resource(cloud, client, websocket, temp_api_key):
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key'])}
    r = cloud.connect.get_device_resource_value(client.endpoint_id(), RESOURCE_PATH, headers=headers)
    async_id = r.json()['async-response-id']
    log.info('Get value from resource "{}". Async-id: "{}"'.format(RESOURCE_PATH, async_id))

    async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=30, assert_errors=True)
    assert async_response['decoded_payload'] == b'500:500:500:500', 'Invalid payload received from the device!'


def test_04_put_resource(cloud, client, websocket, temp_api_key):
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key']), 'Content-type': 'text/plain'}
    r = cloud.connect.set_device_resource_value(client.endpoint_id(), RESOURCE_PATH, PATTERN, headers=headers)
    async_id = r.json()['async-response-id']
    log.info('Put value "{}" to resource "{}". Async-id: "{}"'.format(PATTERN, RESOURCE_PATH, async_id))

    client.wait_for_output('PUT received, new value: {}'.format(PATTERN).encode('ascii'), 60)
    async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=30, assert_errors=True)
    assert async_response['decoded_payload'] == b'', 'Invalid payload received from the device!'


def test_05_get_modified_resource(cloud, client, websocket, temp_api_key):
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key'])}
    r = cloud.connect.get_device_resource_value(client.endpoint_id(), RESOURCE_PATH, headers=headers)
    async_id = r.json()['async-response-id']
    log.info('Get value from resource "{}". Async-id: "{}"'.format(RESOURCE_PATH, async_id))

    async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=30, assert_errors=True)
    assert async_response['decoded_payload'] == PATTERN.encode('ascii'), \
        'Invalid payload received from the device!'
