#!/usr/bin/env python

#
# Maintain a database of calls:
#	calls[group_id]['chan']
#	calls[group_id]['id']		(talker id, if known)
#
# Spawn monitor block when new calls come in.
#

import time

from gnuradio.gr import message as message
import osw_handler


class message_handler:

	_TIMEOUT = 1

	def __init__(self, queue):
		self._queue = queue
		self._call_history = list()
		self._sys_id = -1
		self._sys_channel = -1


	def clean_call_history(self):
		n = list()
		now = time.time()
		for h in self._call_history:
			if now < h[3] + self._TIMEOUT:
				n.append(h)
		self._call_history = n


	def start_call(self, group_id, chan, radio_id = None):
		if self._sys_id < 0:
			return False

		call_found = False
		new_history = list()
		for h in self._call_history:
			if time.time() < h[3] + self._TIMEOUT:
				new_history.append(h)
				if [group_id, chan, radio_id] == h[:3]:
					h[3] = time.time()
					call_found = True
		self._call_history = new_history
		if call_found:
			return False
		self._call_history.append([group_id, chan, radio_id, time.time()])
		msg = message().make_from_string("%d %d %d %d" % (self._sys_id, chan, group_id, (radio_id) if radio_id is not None else (-1)))
		msg.set_type(0)
		self._queue.insert_tail(msg)
		return True


	def set_sysid(self, sys_id, chan):
		self._sys_id = sys_id
		self._sys_channel = chan

