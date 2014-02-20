#!/usr/bin/env python


def load_csv(csv_filename):

	r = list()
	with open(csv_filename, "rb") as f:
		for l in f:
			r.append(l[:-1].split(','))		# the last character of l is expected to be '\n'
	return r

