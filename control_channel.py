#!/usr/bin/env python

import math

from gnuradio import analog, digital, gr, filter
from gnuradio.filter import firdes

from control_channel_sink import control_channel_sink


class control_channel(gr.hier_block2):

	def __init__(self, sample_rate, freq_offset, queue, logger = None, group_description_csv = None):

		gr.hier_block2.__init__(
			self,
			"SmartZone Control Channel",
			gr.io_signature(1, 1, gr.sizeof_gr_complex),		# input signature
			gr.io_signature(0, 0, 0)				# output signature
		)

		self._CC_DEVIATION	= 4e3		# observed

		self._symbol_rate	= 3600.0	# control channel rate is 3.6kb/s
		self._oversample	= 4		# XXX reduce
		
		# get close to the desired sample rate with decimation
		channel_decimation = int(sample_rate / (self._oversample * self._symbol_rate)) & ~1
		channel_rate = sample_rate / channel_decimation
		samples_per_symbol = channel_rate / self._symbol_rate

		# channel_bw = self._CC_DEVIATION + self._symbol_rate # from pager source
		channel_bw = 3 * self._symbol_rate

		# taps = firdes.low_pass(1, sample_rate, int(3.0 * self._symbol_rate), int(3.0 * self._symbol_rate / 10.0), firdes.WIN_HAMMING)
		channel_taps = firdes.low_pass(1, sample_rate, channel_bw, channel_bw / 10.0, firdes.WIN_HAMMING)
		channel_filter = filter.freq_xlating_fir_filter_ccf(channel_decimation, channel_taps, freq_offset, sample_rate)

		#quad_demod = analog.quadrature_demod_cf(1.0)
		quad_demod = analog.quadrature_demod_cf(channel_rate / (2 * math.pi * self._CC_DEVIATION))

		clock = digital.clock_recovery_mm_ff(omega = samples_per_symbol, gain_omega = 0.001, mu = 0, gain_mu = 0.001, omega_relative_limit = 0.005)
		slicer = digital.binary_slicer_fb()
		digital_correlate = digital.correlate_access_code_bb("10101100", 0)
		cc_sink = control_channel_sink(logger, queue, group_description_csv)

		self.connect(self, channel_filter, quad_demod, clock, slicer, digital_correlate, cc_sink)


# vim:ts=8
