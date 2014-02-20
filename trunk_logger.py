#!/usr/bin/env python

import time
from sys import stdout


LOG_ERROR	= 0
LOG_NORMAL	= 1
LOG_NOTICE	= 2
LOG_INFO	= 3
LOG_DEBUG	= 4

class logger:

	def __init__(self, log_filename = None, log_prio = LOG_NORMAL, log_include_date = True, log_history = False):
		self._prio = log_prio
		self._include_date = log_include_date
		self._logfile = (stdout) if log_filename is None else (open(log_filename, "a"))
		self._enable_history = log_history
		self._history = list()


	def __del__(self):
		if self._logfile is not None:
			self._logfile.close()


	def set_prio(p):
		self._prio = p


	def expire_log_history(self):
		now = time.time()
		n = list(self._history)
		for c in n:
			if now > (c[0] + 1):
				self._history = self._history[1:]
			else:
				return


	def remember_log(self, s):
		self.expire_log_history()
		for i in range(len(self._history)):
			if s == self._history[i][1]:
				self._history[i][0] = time.time()
				return True
		self._history.append([time.time(), s])
		return False


	def log(self, s, prio = LOG_NORMAL):
		if prio <= self._prio:
			if self._logfile is not None:
				if self._enable_history and self.remember_log(s):
					return
				if self._include_date:
					self._logfile.write("%s:   %s\n" % (time.asctime(), s))
				else:
					self._logfile.write("%s" % (s,))
				self._logfile.flush()


	def log_error(self, s):
		self.log("error: %s" % (s,), LOG_ERROR)


	def log_notice(self, s):
		self.log("notice: %s" % (s,), LOG_NOTICE)


	def log_info(self, s):
		self.log("info: %s" % (s,), LOG_INFO)


	def log_debug(self, s):
		self.log("debug: %s" % (s,), LOG_DEBUG)


