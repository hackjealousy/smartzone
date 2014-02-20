#!/usr/bin/env python

import time
import os

from gnuradio import gr, blocks, filter, analog, audio
from gnuradio.filter import optfir, firdes


def create_directory(save_dir, sys_id):
	try:
		os.stat("%s/%x" % (save_dir, sys_id))
	except:
		try:
			os.mkdir(save_dir)
		except:
			pass
		os.mkdir("%s/%x" % (save_dir, sys_id))


def audio_name(group_id, chan):

	return "%x_%d_%.6f" % (group_id, chan, round(time.time(), 6))


class audio_channel(gr.hier_block2):


	def __init__(self, sample_rate, freq_offset, sys_id, chan, group_id, save_dir):

		gr.hier_block2.__init__(
			self,
			"SmartZone Audio Channel",
			gr.io_signature(1, 1, gr.sizeof_gr_complex),		# input signature
			gr.io_signature(0, 0, 0)				# output signature
		)

		# audio constants
		self._audio_sample_rate	= 8000
		self._audio_passband	= 3.6e3
		self._audio_stopband	= 4e3
		self._audio_gain	= 1.0

		# fm constants
		self._deviation		= 2.5e3
		self._fm_passband	= self._audio_stopband + self._deviation
		self._fm_stopband	= self._fm_passband + 8e3			# 3 * audio_bw

		# fm channel values
		desired_channel_rate	= 40e3
		channel_decimation	= int(round(sample_rate / desired_channel_rate))
		channel_rate		= sample_rate / channel_decimation

		# audio channel values
		desired_audio_rate	= 8e3
		audio_decimation	= int(round(channel_rate / desired_audio_rate))
		audio_rate		= channel_rate / audio_decimation


		# translate desired fm audio frequency to baseband; decimate to channel rate
		channel_taps		= optfir.low_pass(1, sample_rate, self._fm_passband, self._fm_stopband, 0.1, 60)
		channel_filter		= filter.freq_xlating_fir_filter_ccf(channel_decimation, optfir.low_pass(1, sample_rate, self._fm_passband, self._fm_stopband, 0.1, 60), freq_offset, sample_rate)

		# power squelch
		squelch			= analog.pwr_squelch_cc(-50, alpha = 1, ramp = 0, gate = True)

		# fm demodulation
		audio_demod = analog.fm_demod_cf(channel_rate, audio_decimation, self._deviation, self._audio_passband, self._audio_stopband, self._audio_gain, 75e-6)

		# remove sub-audible data  XXX demodulate
		sa_filter = filter.fir_filter_fff(1, firdes.band_pass(1, audio_rate, 400, 3900, 100, filter.firdes.WIN_HANN))

		# audio output
		
		# ensure directory exists
		create_directory(save_dir, sys_id)

		# asink = audio.sink(audio_rate)
		wavfile_sink = blocks.wavfile_sink("%s/%x/%s" % (save_dir, sys_id, audio_name(group_id, chan)), 1, int(round(audio_rate)), 8)

		self.connect(self, channel_filter, squelch, audio_demod, sa_filter, wavfile_sink)


# vim:ts=8:nowrap
