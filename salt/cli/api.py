# -*- coding: utf-8 -*-
'''
    salt.cli.api
    ~~~~~~~~~~~~~

    Salt's api cli parser.

'''

# Import Python libs
from __future__ import absolute_import, print_function
import sys
import os.path
import logging

# Import Salt libs
import salt.utils.parsers as parsers
import salt.version
import salt.syspaths as syspaths

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


class SaltAPI(six.with_metaclass(parsers.OptionParserMeta,  # pylint: disable=W0232
        parsers.OptionParser, parsers.ConfigDirMixIn,
        parsers.LogLevelMixIn, parsers.PidfileMixin, parsers.DaemonMixIn,
        parsers.MergeConfigMixIn)):
    '''
    The cli parser object used to fire up the salt api system.
    '''

    VERSION = salt.version.__version__

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = os.path.join(syspaths.LOGS_DIR, 'api')

    def setup_config(self):
        return salt.config.api_config(self.get_config_file_path())

    def run(self):
        '''
        Run the api
        '''
        import salt.client.netapi
        self.parse_args()
        try:
            if self.config['verify_env']:
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith('tcp://') \
                        and not logfile.startswith('udp://') \
                        and not logfile.startswith('file://'):
                    # Logfile is not using Syslog, verify
                    salt.utils.verify.verify_files(
                        [logfile], self.config['user']
                    )
        except OSError as err:
            log.error(err)
            sys.exit(err.errno)

        self.setup_logfile_logger()
        client = salt.client.netapi.NetapiClient(self.config)
        self.daemonize_if_required()
        self.set_pidfile()
        client.run()
