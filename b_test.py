#!/usr/bin/env python

import band_plan_800


def main():

	for c in range(1024):
		freq = band_plan_800.get_freq(c)
		chan = 0
		if freq is not None:
			chan = band_plan_800.get_chan(freq)
			if chan != c:
				print "%d -> %f -> %d" % (c, freq, chan)


	for i in range(1520):
		f = 851.0 + i * 0.0125
		chan = band_plan_800.get_chan(f)
		if chan is not None:
			freq = band_plan_800.get_freq(chan)
			if round(freq - f, 6) != 0:
				print "%f -> %d -> %f" % (f, chan, freq)


	return 0


if __name__ == '__main__':
	exit(main())
