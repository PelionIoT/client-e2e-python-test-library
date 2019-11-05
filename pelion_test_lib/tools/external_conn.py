"""
Copyright 2019 ARM Limited
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging
import json

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class ExternalConnection:
    def __init__(self, importer=__import__):
        self.client = None
        self.resource = None
        self.__initialize_resource(importer)

    def __initialize_resource(self, importer):
        """
        Connect to external resource and flash it
        """
        try:
            with open('external_connection.json', 'r') as config_file:
                configs = json.load(config_file)
        except IOError:
            error_msg = 'Could not load the external connection configs'
            log.error(error_msg)
            raise Exception(error_msg)

        external_module = configs['module']
        host = configs['host']
        port = configs['port']
        user = configs['user']
        password = configs['password']
        resource_type = configs['resource_type']
        platform_name = configs['platform_name']
        resource_tags = configs['resource_tags']
        binary = configs['binary']
        baudrate = configs['baudrate']
        expiration_time = configs.get('expiration_time', 1200)
        allocation_timeout = configs.get('allocation_timeout', 500)
        local_allocation = configs.get('local_allocation', False)

        try:
            self.remote_module = importer(external_module)
        except ImportError as error:
            log.error('Unable to load external "{}" module!'.format(external_module))
            log.error(str(error))
            self.remote_module = None
            raise error

        self.client = self.remote_module.create(host=host, port=port, logger=log, user=user, passwd=password)

        description = {'resource_type': resource_type,
                       'platform_name': platform_name,
                       'tags': resource_tags}
        self.resource = self.client.allocate(description, expiration_time, allocation_timeout, local_allocation)
        if self.resource:
            self.resource.open_connection(self.remote_module.SerialParameters(baudrate=baudrate))
            self.resource.on_release('erase')
            self.flash(binary, force_flash=True)
        else:
            self.close()
            error_msg = 'Could not allocate external resource'
            log.error(error_msg)
            assert False, error_msg

    def readline(self):
        """
        Read line
        :return: One line from serial stream
        """
        try:
            if self.resource:
                output = self.resource.readline()
                return output
            else:
                raise Exception('External resource does not exist')
        except Exception as ex:
            log.debug('External connection read error: {}'.format(ex))
            return None

    def write(self, data):
        """
        Write data
        :param data: Data to send
        """
        try:
            if self.resource:
                self.resource.write(data)
            else:
                raise Exception('External resource does not exist')
        except Exception as ex:
            log.debug('External connection write error: {}'.format(ex))

    def reset(self):
        """
        Reset resource
        """
        try:
            if self.resource:
                self.resource.reset()
            else:
                raise Exception('External resource does not exist')
        except Exception as ex:
            log.debug('External connection reset error: {}'.format(ex))

    def flash(self, filename, force_flash=False):
        """
        Flash resource
        :param filename: Path to binary
        :param force_flash: Force flash True/False
        """
        try:
            if self.resource:
                self.resource.flash(filename, forceflash=force_flash)
            else:
                raise Exception('External resource does not exist')
        except Exception as ex:
            log.debug('External connection flash error: {}'.format(ex))

    def close(self):
        """
        Close connection
        """
        if self.resource:
            self.resource.release()
        if self.client:
            self.client.disconnect()
