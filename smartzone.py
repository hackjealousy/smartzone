#!/usr/bin/env python

import sys
import time
import threading

from gnuradio import gr, uhd
from gnuradio.eng_option import eng_option
from optparse import OptionParser

import trunk_logger
from control_channel import control_channel
from audio_channel import audio_channel
from band_plan_800 import get_freq, get_chan


#
# Smartzone
#
#	Instantiate control_channel_demod block and point at given control channel.
#
#	Listen for messages in the queue:
#		Start a channel_demod block for each new frequency given.


class smartzone(gr.top_block):

	_GAIN = 0.90


	def __init__(self, options):
		gr.top_block.__init__(self, "SmartZone")

		self._save_dir = "./zonelog"

		self._center_freq = (options.center * 1e6) if options.center < 1e6 else (options.center)
		self._bandwidth = (options.bandwidth * 1e6) if options.bandwidth < 1e6 else (options.bandwidth)

		self._logger = trunk_logger.logger(options.log_file)
		self._cc_msg_q = gr.msg_queue(0)

		self._message_receiver = threading.Thread(target = self.message_receiver)
		self._message_receiver.start()

		#
		# We keep a dictionary keyed from the control channels being monitored.
		# Each entry of this dictionary is itself a dictionary with the following
		# keys:
		#	'sys_id':	system id, when known
		#	'cc_block':	the control channel signal processing block (to disable if needed)
		#
		self._control_channels = dict()
		self._control_channel_list = list()	# iterative list of monitored cc
		self._cc_lock = threading.Lock()

		#
		# We keep a dictionary keyed from the audio channels being monitored.
		# Each entry of this dictionary is itself a dictionary with the following
		# keys:
		#	'group_id':	the group id being broadcasted to on this channel
		#	'radio_ids':	a list of radio ids (talkers) with timestamp
		#	'audio_block':	the audio processing block (to disable on channel tear-down)
		#
		self._audio_channels = dict()
		self._audio_channel_list = list()	# iterative list of monitored audio channels
		self._ac_lock = threading.Lock()	# hold lock when accessing audio channels

		self.u = uhd.usrp_source(
			device_addr = "",
			stream_args = uhd.stream_args(
				cpu_format = "fc32",
				channels = range(1),
			),
		)
		self.u.set_samp_rate(self._bandwidth)
		self.u.set_center_freq(self._center_freq, 0)
		self.u.set_antenna(options.antenna, 0)

		gain_range = self.u.get_gain_range(0)
		gain = gain_range.start() + self._GAIN * (gain_range.stop() - gain_range.start())
		self.u.set_gain(gain)


	def control_channel_add(self, chan):

		self._cc_lock.acquire()
		if chan in self._control_channel_list:
			# we're already monitoring this control channel
			self._cc_lock.release()
			return

		# XXX group description csv
		cc = control_channel(self._bandwidth, get_freq(chan) * 1e6 - self._center_freq, queue = self._cc_msg_q, logger = self._logger, group_description_csv = "./SERS.groups.csv")
		self.lock()
		self.connect(self.u, cc)
		self.unlock()

		# remember this control channel
		self._control_channels[chan] = {'sys_id': -1, 'cc_block': cc}
		self._control_channel_list.append(chan)
		self._cc_lock.release()


	def audio_channel_add(self, args):

		(sys_id, chan, group_id, radio_id) = args
		print "sys_id: %x, freq: %f, group: %x, radio: %d" % (sys_id, get_freq(chan), group_id, radio_id)

		self._ac_lock.acquire()
		ab_to_remove = None
		if chan in self._audio_channel_list:
			c = self._audio_channels[chan]
			if c['group_id'] == group_id:
				c['radio_ids'].append([radio_id, time.time()]) # even if None
				self._ac_lock.release()
				return

			# group changed; that session must be over
			ab_to_remove = self._audio_channels[chan]['audio_block']
			del self._audio_channel_list[self._audio_channel_list.index(chan)]	# XXX write metadata about call
			del self._audio_channels[chan]

		# we have a new session
		ac = audio_channel(self._bandwidth, get_freq(chan) * 1e6 - self._center_freq, sys_id, chan, group_id, self._save_dir)

		print "stop flow graph"

		# XXX bug: python block requires stop
		self.stop()
		self.wait()
		self.lock()

		print "connecting"
		if ab_to_remove is not None:
			self.disconnect(ab_to_remove)
		self.connect(self.u, ac)

		print "starting"
		self.unlock()
		self.start()

		print "started"

		# remember it
		self._audio_channels[chan] = {'group_id': group_id, 'radio_ids': [[radio_id, time.time()],], 'audio_block': ac}
		self._audio_channel_list.append(chan)

		self._ac_lock.release()


	# 
	# Messages are sent from a control channel to us each time
	# a channel assignment is made.  The messages are the following:
	#
	#	analog audio:	type = 0, "sysid chan group_id <radio_id | -1>"
	#
	def message_receiver(self):
		while True:
			if not self._cc_msg_q.empty_p():
				msg = self._cc_msg_q.delete_head()
				if msg.type() == 0:
					self.audio_channel_add(map(int, msg.to_string().split(' ')))
					return
			time.sleep(0.001)
		return


def main():

	SERS_WEST_SIMULCAST = 868.3375	# XXX should have stored file with previous good values

	parser = OptionParser(option_class = eng_option, usage = "%prog: [options]")
	parser.add_option("-l", "--log-file", type = "string", default = None, help = "Log channel assignments to a file rather than stdout.")
	parser.add_option("-c", "--center", type = "float", default = 867.0, help = "Center of monitored frequencies in MHz.")
	parser.add_option("-b", "--bandwidth", type = "float", default = 5, help = "Monitoring bandwidth in MHz.")
	parser.add_option("-C", "--control-channel", type = "float", default = SERS_WEST_SIMULCAST, help = "Control channel in MHz. [default = %default]")
	parser.add_option("-A", "--antenna", type = "string", default = "RX2", help = "Select RX antenna where appropriate.")
	(options, args) = parser.parse_args()


	sz = smartzone(options)
	sz.control_channel_add(get_chan(options.control_channel))	# until we can scan for control channels
	sz.run()


if __name__ == "__main__":
	sys.exit(main())


# vim:ts=8:nowrap
