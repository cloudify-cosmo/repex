# import os
import repex.repex as rpx

CONFIG_YAML_FILE = "tester.yaml"
VERSION = '3.1.0-m3'

variables = {
    'version': VERSION,
    'base_dir': '.'
}

rpx.iterate(CONFIG_YAML_FILE, variables, verbose=True)
