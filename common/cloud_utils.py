# Copyright 2021 Google LLC..
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import googleapiclient
from typing import Dict, Text, Any
import time
import logging

# Number of seconds to wait before re-checking for operation status.
_WAIT_FOR_OPERATION_SLEEP_SECONDS = 5


def wait_for_operation(operation_client: googleapiclient.discovery.Resource,
                       operation: Dict[Text, Any],
                       wait: int = _WAIT_FOR_OPERATION_SLEEP_SECONDS) -> None:
  """Waits for the completion of operation.

  This method retrieves operation resource and checks for its status. If the
  operation is not completed, then the operation is re-checked after
  `wait` seconds.

  Args:
    operation_client: Client with methods for interacting with the operation
      APIs built with googleapiclient.discovery.build method.
    operation: Resource representing long running operation.

  Raises:
    Error: If the operation is not successfully completed.
  """
  while True:
    updated_operation = operation_client.get(name=operation['name']).execute()
    if updated_operation.get('done'):
      logging.info(f'Operation {operation["name"]} successfully completed.')
      return
    if updated_operation.get('error'):
      logging.info(
          f'Operation {operation["name"]} failed to complete successfully.')
      raise Exception(
          f'Operation {operation["name"]} not completed. Error Details: '
          f'{updated_operation["error"]}')
    logging.info(
        f'Operation {operation["name"]} still in progress. Sleeping for '
        f'{wait} seconds before retrying.')
    time.sleep(wait)
