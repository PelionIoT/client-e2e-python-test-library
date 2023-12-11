# Client E2E Python Test Library Changelog

## 0.4.0 2023-12-11
- Rename the library to client-e2e-python-test-library.
    - Rename `PELION_CLOUD_API_KEY` to `CLOUD_API_KEY`.
    - Rename `PELION_CLOUD_API_GW` to `CLOUD_API_GW`.
- Update `requests` to latest (2.31.0).

## 0.3.0 2023-01-16
- Izuma branding.

## 0.2.10 2021-03-04
- Update test doesn't depend on mbed bootloader anymore

## 0.2.9  2021-01-15
- Updated instructions
- Updated python dependencies

## 0.2.8  2020-12-15
- Update copyrights to Pelion

## 0.2.7  2020-09-18
- Manifest-tool 2.0.0 support.

## 0.2.6  2020-04-22
- Device resource paths changed to support any client-library using application.

## 0.2.5  2020-03-20
- Added fixture for multi device update campaign.
- Option to run test set without creating temporary API key.
- Breaking change: API key fixture name change and it returns only the key part.

## 0.2.4  2020-02-27
- Completed the Python 2 support.

## 0.2.3  2020-02-10
- Small update for subscription test.

## 0.2.2  2020-02-06
- Support for testing with linux binary.
- Subscription test updated.
- Set manifest-tool's default path to working directory
- Minor error situation improvements

## 0.2.1  2020-01-22
- Added pylint PR checker.

## 0.2.0  2020-01-22
- Added factory reset test case.
- Added update test case.
- Minor code syntax improvements.

## 0.1.4  2019-12-17
- Added an automatic reset option for the board.

## 0.1.3  2019-12-13
- Updated the WebSocket handler.

## 0.1.2  2019-12-12
- Refactored the test set.

## 0.1.1  2019-11-28
- Defined few default startup arguments for easier usability.
- Re-formatted logging.
- Added test result summary after the test run.

## 0.1.0  2019-11-05
- Initial release of Pelion E2E Test Library.
