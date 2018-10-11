# -*- coding: utf-8 -*-
"""
This script restarts monerod in case it got out-of-sync with the network.
More specifically, it restarts the daemon if local height is lower than height
pulled from several block explorers.

Caveat: Don't run this script while syncing/catching up, as it will continiously
restart the daemon.
"""
from __future__ import absolute_import, print_function
import logging.config
import json

import subprocess
from gevent.monkey import patch_all; patch_all()
import requests
import gevent
import urllib3

BLOCK_DIFF_RESTART_THRESHOLD = 2

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(levelname)-8s  %(message)s', disable_existing_loggers=True)
logging.getLogger('requests').setLevel(logging.WARNING)  # shut up requests
urllib3.disable_warnings()


def get_height_chainradar():
    # noinspection PyBroadException
    try:
        r = requests.get('https://chainradar.com/api/v1/bcn/status')
        j = r.json()
        height = j['height']
    except Exception:
        return None

    return height

def get_height_xmrchain():
    # noinspection PyBroadException
    try:
        r = requests.get('https://xmrchain.net/api/networkinfo', verify=False)
        j = r.json()
        height = j['data']['height']
    except Exception:
        return None

    return height

def get_height_moneroblocks():
    # noinspection PyBroadException
    try:
        r = requests.get('https://moneroblocks.info/api/get_stats/')
        j = r.json()
        height = j['height']
    except Exception:
        return None

    return height

def get_height_daemon():
    # noinspection PyBroadException
    try:
        request_data = {"jsonrpc": "2.0", "id": "test", "method": "get_info"}
        headers = {'Content-Type': 'application/json'}
        r = requests.post('http://127.0.0.1:18081/json_rpc', data=json.dumps(request_data), headers=headers)
        height = r.json()['result']['height']
    except Exception:
        return None

    return height


logging.info("Started daemon health check")

chainradar = gevent.spawn(get_height_chainradar)
xmrchain = gevent.spawn(get_height_xmrchain)
moneroblocks = gevent.spawn(get_height_moneroblocks)
daemon = gevent.spawn(get_height_daemon)

gevent.joinall([chainradar, xmrchain, moneroblocks, daemon])
other_heights = [chainradar.get(), xmrchain.get(), moneroblocks.get()]

logging.debug("Got {} network heights from other services".format(sum(x is not None for x in other_heights)))

network_height = max(other_heights)
daemon_height = daemon.get()

logging.debug("Heighest block known to another service: {}".format(network_height))
logging.debug("Heighest block known to our daemon: {}".format(daemon_height))

if network_height - daemon_height > BLOCK_DIFF_RESTART_THRESHOLD:
    logging.info("Height difference bigger than threshold, restarting monerod!")
    ret = subprocess.call(['supervisorctl', 'restart', 'monerod'])
    if ret == 0:
        logging.info("Monerod successfully restarted!")
    else:
        logging.warning("Monerod restart failed with return code {}".format(ret))
else:
    logging.info("All good!")

