# Pelion E2E Python test library

Pelion E2E tests verify that a target platform can perform essential Device Management Client operations.
The library is designed to be used with the [pytest test framework](https://docs.pytest.org/en/latest/).

## Prerequisites

Python 3.5 or later.

## Installation

```bash
$ git clone https://github.com/ArmMbed/pelion-e2e-python-test-library.git
$ pip install wheel
$ python3 setup.py bdist_wheel
$ cd dist/
$ pip install -I pelion_test_lib*.whl
```

## Basic usage

- Build the [Device Management Client example application](https://developer.pelion.com/docs/device-management/current/connecting/mbed-os.html) for your board and flash it.
- Set `PELION_CLOUD_API_KEY` environment variable with your [access key](https://developer.pelion.com/docs/device-management/current/user-account/application-access-keys.html).
    - Linux: `export PELION_CLOUD_API_KEY=<access_key_here>`
    - Windows: `set PELION_CLOUD_API_KEY=<access_key_here>`
- Test run will create temporary API key for the WebSocket callback channel by default. If you want to prevent that and use only the exported API key, add `--use_one_apikey` startup argument.
- Tests use [Mbed LS](https://github.com/ARMmbed/mbed-os-tools/tree/master/packages/mbed-ls) to select the board from the serial port.
  - If you have only one board connected to the serial port, you don't need to select the device for the tests.
  - If there are multiple boards connected to the serial port, run `mbedls` to check the target board's ID, and use it in the test run's argument `--target_id=[id]`.

  ```bash
  $ mbedls
  +---------------+----------------------+-------------+--------------+--------------------------------------------------+-----------------+
  | platform_name | platform_name_unique | mount_point | serial_port  | target_id                                        | daplink_version |
  +---------------+----------------------+-------------+--------------+--------------------------------------------------+-----------------+
  | K64F          | K64F[0]              | D:          | /dev/ttyACM0 | 0240000032044e4500257009997b00386781000097969900 | 0244            |
  +---------------+----------------------+-------------+--------------+--------------------------------------------------+-----------------+

  ```

- Tests can be also run with [Linux build of the Device Management Client](https://www.pelion.com/docs/device-management/current/connecting/linux-on-pc.html) by giving the compiled binary in the `--local_binary=./mbedCloudClientExample.elf` argument. **Note,** update test is not supported with Linux build.

### Running a test set

To run a test set for Device Management Client use the command:

```bash
pytest tests/dev-client-tests.py
```
Read later instructions how to setup the update test to go with the test set.

### Running a single test

To run a single test from the set, use the [`-k` argument](https://docs.pytest.org/en/latest/example/markers.html?highlight=keyword#using-k-expr-to-select-tests-based-on-their-name) to set the test name as a keyword:

```bash
pytest tests/dev-client-tests.py -k get_resource
```

### Running the update test
Before running the update test, make sure you create update-related configuration and initialize the developer environment proparly as describe [here](https://developer.pelion.com/docs/device-management/current/connecting/mbed-os.html).
Update test uses the same manifest-dev-tool to create the actual manifest for update campaign.
Running the update test provide mandatory update image path and optional manifest-dev-tool init path arguments at startup:
- `--update_bin=/home/user/mbed-cloud-client-example_update.bin` absolute path for the update image
- `--manifest_tool=/home/user/mbed-os-example-pelion` absolute path where manifest-dev-tool init is executed - defaults to current working directory

If you want to leave the firmware image, manifest and campaign to your account after the test, add `--no_cleanup` startup argument.
New manifest-tool 2.0.0 supports two different versions of manifest schemas. Update test's manifest creation defaults to 'v1' manifest version, but you can set the version e.g to 'v3' by the `--manifest_version=v3` startup argument.
Supported versions at the moment are 'v1' and 'v3'.


### Results output

Add the startup arguments to adjust the generated output:
- `--log-cli-level=DEBUG` adds more details
- `--html=results.html` generates an HTML report
- `--junitxml=junit.xml` provides output for CI systems, for example Jenkins

The library also writes a separate `client.log` file from the Device Management Client output.

### Customized test runs

There are many ways to configure the test runs. Refer to the [full pytest documentation](https://docs.pytest.org/en/latest/contents.html) for more information.

## Current tests

| Test name                       | Main functions                                        | Notes                        |
| ------------------------------- | ------------------------------------------------------| -----------------------------|
| `test_01_get_device_id`         | Verify that the device is registered.                 |                              |
| `test_02_get_resource`          | Verify that the device responds to GET.               | Uses Resource `/1/0/1`       |
| `test_03_put_resource`          | Verify that the device responds to PUT.               | Uses Resource `/1/0/1`       |
| `test_04_subscribe_resource`    | Verify the notification from the subscribed resource. | Uses Resource `/1/0/1`       |
| `test_05_factory_reset`         | Verify the client's factory reset behaviour.          |                              |
| `test_06_update_device`         | Verify the device firmware update.                    |                              |


## License

See the [license](https://github.com/ARMmbed/pelion-e2e-python-test-library/blob/master/LICENSE) agreement.
