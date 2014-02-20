#!/usr/bin/env python

#
# This class decodes the control channel for Motorola SmartZone trunked
# radio networks.
#
# We assume that the standard 800MHz band plan is in use.
#

import operator
import numpy
from gnuradio import gr
from osw_handler import osw_handler
import trunk_logger


CONTROL_WORD_LEN = 76


class control_channel_sink(gr.sync_block):

	def __init__(self, logger, queue, group_description_csv = None):

		gr.sync_block.__init__(
			self,
			name = "SmartZone Control Channel Sink",
			in_sig = [numpy.uint8],
			out_sig = None
		)

		self.s = []
		self.s_tracking = False
		self.logger = logger

		self.osw_handler = osw_handler(self.logger, queue, group_description_csv = group_description_csv)

		self.errors = 0.0
		self.valid = 0.0


	def error_rate(self):
		return self.errors / (self.valid + self.errors)


	def list_to_uint(self, l):

		r = 0
		for b in l:
			r = 2 * r + (b ^ 1)
		return r


	def sync_word_found(self, b):

		return (b & 2) == 2


	def deinterleave(self, s):

		r = CONTROL_WORD_LEN / 4
		return [s[k + l * r] for k in range(r) for l in range(4)]


	def parity_encode(self, d):

		return map(operator.xor, d, [0,] + d[:-1])


	def parity_decode(self, d):

		data = list(d[::2])
		s = map(operator.xor, self.parity_encode(data), d[1::2])
		for i in range(len(s) - 1):
			if bool(s[i] & s[i + 1]):
				data[i] = data[i] ^ 1
		return data


	def check_crc(self, d):

		# calculate expected
		a = 0x0393
		o = 0x036e
		for b in d[:27]:
			if(bool(o & 1)):
				o = (o >> 1) ^ 0x0225
			else:
				o = (o >> 1)
			if bool(b):
				a = a ^ o

		# load given
		g = self.list_to_uint(d[27:37])

		if a != g:
			#self.logger.log_debug("bad crc (%x != %x)" % (a, g))
			return False

		return True


	def process_stream(self, s):

		if len(s) != CONTROL_WORD_LEN:
			print "error: process_control_word: incorrect length (%d != %d)" % (len(s), CONTROL_WORD_LEN)
			return

		# deinterleave; extract data from parity
		osw = self.parity_decode(self.deinterleave(s))

		# check crc
		if not self.check_crc(osw):
			self.errors += 1
			self.logger.log("CRC: %%%d" % (int(100 * self.error_rate()),))
			return

		self.valid += 1

		# process
		self.osw_handler.handle(osw)


	def work(self, input_items, output_items):

		ii = input_items[0]
		for b in ii:
			if not self.s_tracking:
				if not self.sync_word_found(b):
					continue
				self.s_tracking = True
			self.s += [b & 1,]
			if len(self.s) >= CONTROL_WORD_LEN:
				self.process_stream(self.s[:CONTROL_WORD_LEN])
				self.s = self.s[CONTROL_WORD_LEN:]
				self.s_tracking = False

		return len(input_items[0])

