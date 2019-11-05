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

- Build the [Device Management Client example application](https://www.pelion.com/docs/device-management/current/connecting/device-management-client-tutorials.html) for your board and flash it.
- [API key](https://www.pelion.com/docs/device-management/current/integrate-web-app/api-keys.html) is used from Mbed's default `CLOUD_SDK_API_KEY` environment variable, but you can override it by defining separate variable using following command-line command:
    - Linux: `export PELION_CLOUD_API_KEY=[api_key_here]`
    - Windows: `set PELION_CLOUD_API_KEY=[api_key_here]`
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

### Running a test set

To run a test set for Device Management Client, go to the `/tests` folder and use the command:

```bash
pytest dev-client-tests.py -v -log_cli=true --log-cli-level=INFO --html=results.html
```
When the test run starts, reset the board to trigger the bootstrap.

### Running a single test

To run a single test from the set, use the [`-k` argument](https://docs.pytest.org/en/latest/example/markers.html?highlight=keyword#using-k-expr-to-select-tests-based-on-their-name) to set the test name as a keyword:

```bash
pytest dev-client-tests.py -v -log_cli=true --log-cli-level=INFO --html=results.html -k test_03_get_resource
```

### Results output

Use the startup arguments to adjust the generated output:
- `-log-cli=true` enables the output logging directly into the console
- `--log-cli-level= DEBUG` adds more details
- `--html=results.html` generates an HTML report
- `--junitxml=junit.xml` provides output for CI systems, for example Jenkins

The library also writes a separate `client.log` file from the Device Management Client output.

### Customized test runs

There are many ways to configure the test runs. Refer to the [full pytest documentation](https://docs.pytest.org/en/latest/contents.html) for more information.

## Current tests

| Test name                       | Main functions                                   | Notes                        |
| ------------------------------- | ------------------------------------------------ | -----------------------------|
| `test_01_get_device_id`         | Verify that the device is registered.            |                              |
| `test_02_subscribe_resource`    | Verify that the device Resource gets subscribed. | Uses Resource `/3200/0/5501` |
| `test_03_get_resource`          | Verify that the device responds to GET.          | Uses Resource `/3201/0/5853` |
| `test_04_put_resource`          | Verify that the device responds to PUT.          | Uses Resource `/3201/0/5853` |
| `test_05_get_modified_resource` | Verify that the device gets the earlier PUT.     | Uses Resource `/3201/0/5853` |


## License

See the [license](https://github.com/ARMmbed/pelion-e2e-python-test-library/blob/master/LICENSE) agreement.
