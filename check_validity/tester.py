# import os
import repex.repex as rpx

CONFIG_YAML_FILE = "check_validity/tester.yaml"
VERSION = '3.1.0-m3'

variables = {
    'version': VERSION,
    'base_dir': 'check_validity'
}

rpx.iterate(CONFIG_YAML_FILE, variables, verbose=True)


# You can also run this from the command line instead:
# rpx execute -c check_validity/tester.yaml -t mytag -v --vars-file check_validity/vars.yaml --var base_dir=check_validity --var version=3.3.x  # NOQA