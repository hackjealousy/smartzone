#!/usr/bin/env python


CHANNEL_SPACING		= float(0.025)
CHANNEL_BASE_FREQ	= [float(851.0125), float(866), float(867), float(868.975), float(867.425)]


def is_valid_channel(c):
	return ((0 <= c) and (c <= 0x2f7)) or ((0x32f <= c) and (c <= 0x33f)) or ((0x3c1 <= c) and (c <= 0x3fe)) or (c == 0x3be)


def get_freq(c):
	"""
	Return the frequency for channel c in the Standard 800MHz plan
	"""

	if c < 720:
		return CHANNEL_BASE_FREQ[0] + c * CHANNEL_SPACING		# 720 channels; x.y125 + 0.025 * a, a in range(4), 851.0125 <= x < 869.0125

	if c < 760:
		return CHANNEL_BASE_FREQ[1] + (c - 720) * CHANNEL_SPACING	# 40 channels; x.y000 + 0.025 * a, a in range(4), 866 <= x < 867

	if c < 815:
		# print "error: chan %d not found" % (c,)
		return None

	if c < 832:
		return CHANNEL_BASE_FREQ[2] + (c - 815) * CHANNEL_SPACING	# 16 channels; x.y750 + 0.025 * a, 867 <= x < 867.4250

	if c < 958:
		# print "error: chan %d not found" % (c,)
		return None

	if c == 958:
		return CHANNEL_BASE_FREQ[3]					# x == 868.9750

	if c < 961:
		# print "error: chan %d not found" % (c,)
		return None

	if c < 1023:
		return CHANNEL_BASE_FREQ[4] + (c - 961) * CHANNEL_SPACING	# 62 channels; 867.4250 + 0.025 * a, 867.4250 <= x < 868.9750

	# print "error: chan %d not found" % (c,)
	return None


def get_chan(freq):

	# normalize to MHz; round to 6 decimal digits
	if freq > 1e6:
		freq = freq / 1e6
	freq = round(freq, 6)

	s = str(round(freq - int(freq), 6))
	i = s.index('.')
	v = "0"
	if len(s) < i + 4 + 1:
		v = "0"
	else:
		v = s[i + 4]

	if v == "5":
		# this must be a frequency in the form, x.y125
		if not ((851.0125 <= freq) and (freq < 869.0125)):
			# print "error: freq %f has no corresponding channel" % (freq,)
			return None
		return int(round(round(freq - CHANNEL_BASE_FREQ[0], 6) / CHANNEL_SPACING))

	if (866 <= freq) and (freq < 867):
		return int(round(round(freq - CHANNEL_BASE_FREQ[1], 6) / CHANNEL_SPACING)) + 720

	if (867 <= freq) and (freq < 867.4250):
		return int(round(round(freq - CHANNEL_BASE_FREQ[2], 6) / CHANNEL_SPACING)) + 815

	if (867.4250 <= freq) and (freq < 868.9750):
		return int(round(round(freq - CHANNEL_BASE_FREQ[4], 6) / CHANNEL_SPACING)) + 961

	if round(freq - CHANNEL_BASE_FREQ[3], 6) == 0:
		return 958

	# print "error: freq %f has no corresponding channel" % (freq,)
	return None
