# -*- coding: utf-8 -*-
'''
The client libs to communicate with the salt master when running raet
'''
from __future__ import print_function
from __future__ import absolute_import
import os
import logging

# Import salt libs
import salt.client
import salt.config
import salt.payload
import salt.transport
import salt.loader
import salt.utils
import salt.utils.args
import salt.utils.event
import salt.utils.minions
import salt.utils.verify
import salt.syspaths as syspaths
from salt.exceptions import (
	EauthAuthenticationError, SaltInvocationError, SaltReqTimeoutError
)

# Import third party libs
try:
	import zmq

	HAS_ZMQ = True
except ImportError:
	HAS_ZMQ = False

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
	import seco.range

	HAS_RANGE = True
except ImportError:
	pass

log = logging.getLogger(__name__)


class LocalClient(salt.client.LocalClient):
	'''
	The API LocalClient
	'''

	def __init__(self,
	             c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
	             mopts=None):

		salt.client.LocalClient.__init__(self, c_path, mopts)

	def _check_pub_data(self, pub_data):
		'''
		Common checks on the pub_data data structure returned from running pub
		'''
		if not pub_data:
			# Failed to autnenticate, this could be a bunch of things
			raise EauthAuthenticationError(
				'Failed to authenticate!  This is most likely because this '
				'user is not permitted to execute commands, but there is a '
				'small possibility that a disk error occurred (check '
				'disk/inode usage).'
			)

		# Failed to connect to the master and send the pub
		if 'jid' not in pub_data:
			print('restapi: jid is not find!')
			return {'success': 'false', 'message': 'jid is not find!'}
		if pub_data['jid'] == '0':
			print('restapi: Failed to connect to the Master, is the Salt Master running?')
			return {'success': 'false', 'message': 'Failed to connect to the Master, is the Salt Master running?'}

		# If we order masters (via a syndic), don't short circuit if no minions
		# are found
		if not self.opts.get('order_masters'):
			# Check for no minions
			if not pub_data['minions']:
				print('restapi: No minions matched the target. No command was sent, no jid was assigned.')
				return {'success': 'false',
						'message': 'No minions matched the target. No command was sent, no jid was assigned.'}

		return pub_data

	def cmd(
		self,
		tgt,
		fun,
		arg=(),
		timeout=None,
		expr_form='glob',
		ret='',
		jid='',
		kwarg=None,
		**kwargs):
		'''
		Synchronously execute a command on targeted minions

		The cmd method will execute and wait for the timeout period for all
		minions to reply, then it will return all minion data at once.

		.. code-block:: python

				>>> import salt.client
				>>> local = salt.client.LocalClient()
				>>> local.cmd('*', 'cmd.run', ['whoami'])
				{'jerry': 'root'}

		With extra keyword arguments for the command function to be run:

		.. code-block:: python

				local.cmd('*', 'test.arg', ['arg1', 'arg2'], kwarg={'foo': 'bar'})

		Compound commands can be used for multiple executions in a single
		publish. Function names and function arguments are provided in separate
		lists but the index values must correlate and an empty list must be
		used if no arguments are required.

		.. code-block:: python

				>>> local.cmd('*', [
								'grains.items',
								'sys.doc',
								'cmd.run',
						],
						[
								[],
								[],
								['uptime'],
						])

		:param tgt: Which minions to target for the execution. Default is shell
				glob. Modified by the ``expr_form`` option.
		:type tgt: string or list

		:param fun: The module and function to call on the specified minions of
				the form ``module.function``. For example ``test.ping`` or
				``grains.items``.

				Compound commands
						Multiple functions may be called in a single publish by
						passing a list of commands. This can dramatically lower
						overhead and speed up the application communicating with Salt.

						This requires that the ``arg`` param is a list of lists. The
						``fun`` list and the ``arg`` list must correlate by index
						meaning a function that does not take arguments must still have
						a corresponding empty list at the expected index.
		:type fun: string or list of strings

		:param arg: A list of arguments to pass to the remote function. If the
				function takes no arguments ``arg`` may be omitted except when
				executing a compound command.
		:type arg: list or list-of-lists

		:param timeout: Seconds to wait after the last minion returns but
				before all minions return.

		:param expr_form: The type of ``tgt``. Allowed values:

				* ``glob`` - Bash glob completion - Default
				* ``pcre`` - Perl style regular expression
				* ``list`` - Python list of hosts
				* ``grain`` - Match based on a grain comparison
				* ``grain_pcre`` - Grain comparison with a regex
				* ``pillar`` - Pillar data comparison
				* ``nodegroup`` - Match on nodegroup
				* ``range`` - Use a Range server for matching
				* ``compound`` - Pass a compound match string

		:param ret: The returner to use. The value passed can be single
				returner, or a comma delimited list of returners to call in order
				on the minions

		:param kwarg: A dictionary with keyword arguments for the function.

		:param kwargs: Optional keyword arguments.
				Authentication credentials may be passed when using
				:conf_master:`external_auth`.

				For example: ``local.cmd('*', 'test.ping', username='saltdev',
				password='saltdev', eauth='pam')``.
				Or: ``local.cmd('*', 'test.ping',
				token='5871821ea51754fdcea8153c1c745433')``

		:returns: A dictionary with the result of the execution, keyed by
				minion ID. A compound command will return a sub-dictionary keyed by
				function name.
		'''
		arg = salt.utils.args.condition_input(arg, kwarg)
		pub_data = self.run_job(tgt,
								fun,
								arg,
								expr_form,
		                        ret,
		                        timeout,
		                        jid,
		                        **kwargs)

		if not pub_data:
			return pub_data
		elif pub_data.has_key('success') and pub_data['success'] == 'false':
			pub_data['message'] += ' tgt: %s, fun: %s.' % (tgt, fun)
			log.error('restapi: %s' % pub_data['message'])
			return pub_data

		ret = {}
		for fn_ret in self.get_cli_event_returns(
			pub_data['jid'],
			pub_data['minions'],
			self._get_timeout(timeout),
			tgt,
			expr_form,
			**kwargs):

			if fn_ret:
				for mid, data in fn_ret.items():
					ret[mid] = data.get('ret', {})

		if not ret:
			ret = {'success': 'false', 'message': 'salt minion is stopped! tgt: %s' % tgt}

		return ret
