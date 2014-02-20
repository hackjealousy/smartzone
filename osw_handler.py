#!/usr/bin/env python

import time
from load_csv import load_csv
from message_handler import message_handler
from band_plan_800 import is_valid_channel, get_freq


# Known OSW commands
class OSW_CMD:
	BACKGROUND_IDLE		= 0x02f8
	FIRST_CODED_PC		= 0x0304
	FIRST_NORMAL		= 0x0308
	EXTENDED_FCN		= 0x030b                      
	AFFIL_FCN		= 0x030d
	TY2_AFFILIATION		= 0x0310
	TY2_MESSAGE		= 0x0311
	TY2_CALL_ALERT		= 0x0319
	FIRST_ASTRO		= 0x0321
	SYSTEM_CLOCK		= 0x0322
	SCAN_MARKER		= 0x032b
	EMERG_ANNC		= 0x032e
	AMSS_ID_MIN		= 0x0360
	AMSS_ID_MAX		= 0x039f
	CW_ID			= 0x03a0
	SYS_NETSTAT		= 0x03bf
	SYS_STATUS		= 0x03c0


# Readable strings
#
# GROUP_TYPE[0] = "Normal Talkgroup", but that was redundant
GROUP_TYPES	= [ "", "All Talkgroup", "Emergency", "Talkgroup Patch to Another", "Emergency Patch", "Emergency Multi-group", "Not Assigned",
		   "Multi-select (initiated by dispatcher)", "DES Encryption Talkgroup", "DES All Talkgroup", "DES Emergency", "DES Talkgroup Patch", "DES Emergency Patch",
		   "DES Emergency Multi-group", "Not Assigned", "DES Multi-select" ]
TONE_NAMES	= [ "105.88", "76.76", "83.72", "90", "97.3", "116.3", "128.57", "138.46" ]
BAND_LIST	= ["800", "Unknown (1)", "800 (2)", "821", "900", "Unknown (5)", "Unknown (6)", "Unknown (7)"]


def get_equipment_name(n):
	if (0x30 <= n) and (n <= 0x4b):
		return "RIB"
	if (0x60 <= n) and (n <= 0x7b):
		return "TIB"
	return "other equipment"


#
#	Class definition
#

class osw_handler:

	def __init__(self, logger, queue, group_description_csv = None):

		self.osw_list = list()
		self.logger = logger
		self.message_handler = message_handler(queue)
		
		self._site_id = -1
		self._sys_id = -1
		self._sys_freq = 0.0
		self._sys_channel = -1
		self._tone = None
		self._neighbors = list()
		self._affiliated_map = dict()
		self._logsrc_count = dict()

		self.group_map = None
		if group_description_csv is not None:
			self.group_map = dict()
			l = load_csv(group_description_csv)
			for r in l[1:]:
				if len(r) >= 2:
					self.group_map[int(r[1], 16)] = r


	def alpha_tag(self, gid):
		if self.group_map is None:
			return None
		if gid in self.group_map:
			return self.group_map[gid][3]
		return None


	def _list_to_uint(self, l):
		r = 0
		for b in l:
			r = 2 * r + (b ^ 1)
		return r


	def parse_raw_osw(self, osw):

		# 0 - 15: address; 16: group; 17 - 26: command; 27 - 36: crc; 37: spare
		return {
			'id'	: self._list_to_uint(osw[:16]) ^ 0x33c7,
			'g'	: osw[16] ^ 1,
			'cmd'	: self._list_to_uint(osw[17:27]) ^ 0x032a,
			'crc'	: self._list_to_uint(osw[27:37])
		}


	def handle(self, osw):
		"""
		Main entry point for the osw_handler.  It parses lists of bits as OSW packets.
		"""
		self.process_osw(self.parse_raw_osw(osw))


#
#	OSW history functions
#

	def len(self):
		return len(self.osw_list)

	
	def push(self, osw):
		self.osw_list = [osw,] + self.osw_list

	
	def pop(self):
		return self.osw_list.pop()


	def replace(self, osw):
		self.osw_list.append(osw)


#
# Log functions
#

	def fillto(self, n, s = None):

		if s is None:
			return " " * n
		if len(s) >= n:
			return s[:n]
		return s + " " * (n - len(s))


	def log(self, command = None, source = None, source_display_count = False, target = None, target_is_group = None, channel = None, text = None, raw = None):
		"""
		Write a formatted log entry.

			Command (5 spaces) | Source (9 spaces) | Target (18 spaces) | Frequency (12 spaces) | Text
		"""

		cmd = ""
		if command is not None:
			cmd += command
		cmd = self.fillto(5, cmd)

		src = ""
		if source is not None:
			if source not in self._logsrc_count:
				self._logsrc_count[source] = 0
			self._logsrc_count[source] += 1
			if source_display_count:
				src = "%4x (%d)" % (source, self._logsrc_count[source])
			else:
				src = "%4x" % (source,)
		src = self.fillto(9, src)

		tgt = ""
		txt = ""
		if target is not None:
			if target_is_group:
				txt = GROUP_TYPES[target & 0xf]
				t = self.alpha_tag((target & 0xfff0) >> 4)
				if t is not None:
					tgt = "%4x  %s" % (target, t)
				else:
					tgt = "%4x  G" % (target,)
			else:
				tgt = "%4x" % (target,)
		tgt = self.fillto(18, tgt)

		freq = ""
		if channel is not None:
			freq += "%3.4f MHz" % (get_freq(channel),)
		freq = self.fillto(12, freq)

		if text is not None:
			if txt != "":
				txt += "; "
			txt += text

		if raw is not None:
			txt += self.osw_str(raw)

		txt = self.fillto(40, txt)

		self.logger.log(cmd + " | " + src + " | " + tgt + " | " + freq + " | " + txt)


	def osw_str(self, osw):
		if type(osw) == type(list):
			os = ""
			for s in osw:
				os += "(%4.4x, %d, %4.4x) " % (s['id'], s['g'], s['cmd'])
			return os
		return "(%4.4x, %d, %4.4x)" % (osw['id'], osw['g'], osw['cmd'])


	def log_osw(self, oswl, text = None):
		for s in oswl:
			s = "%s%s" % ((text + ": ") if text is not None else (""), self.osw_str(s))
			self.log(command = "UNKN", text = s)
		return


#
#	Functions to handle various Type II messages
#
	def unhandled(self, osw, text = None):
		self.log_osw(osw, text)


	def ack_msg(self, osw1, osw2):
		self.log(command = "ACKM", target = osw1['id'], text = "status: %f" % (osw2['id'] & 0xf))


	def ack_status(self, osw1, osw2):
		self.log(command = "ACKS", target = osw1['id'], text = "status: %f" % (osw2['id'] & 0xf))


	def unknown(self, oswl, text):
		self.unhandled(oswl, text)


	def unknown_ack(self, osw1, osw2):
		self.log(command = "ACK?", target = osw1['id'], text = "status: %x" % (osw2['id'] & 0xf))


	def site_id(self, osw):
		si = self._site_id = osw['cmd'] - OSW_CMD.AMSS_ID_MIN
		if self._site_id != si:
			self._site_id = si
			self.log(command = "SITEID", source = osw['cmd'] - OSW_CMD.AMSS_ID_MIN, text = "id = %x" % (osw['id'],))


	def site_idle(self, osw):
		# self.log(command = "IDLE")
		return


	def sys_netstat(self, osw):
		return


	def sys_status(self, osw):
		if (osw['id'] >> 13) & 7 == 1:
			t = TONE_NAMES[(osw['id'] >> 5) & 7]
			if t != self._tone:
				self._tone = t;
				self.log(command = "SYSSTAT", text = "tone = %s" % (self._tone,))


	def scan_marker(self, osw):
		self.log(command = "SYSID", source = osw['id'], text = "Scan Marker")


	def diag(self, osw):
		if (osw['id'] & 0xe000) == 0xe000:
			self.log(command = "DIAG", channel = osw['id'] & 0x3ff, text = "CW ID")
			return

		if (osw['id'] & 0xf00) == 0xa00:
			self.log(command = "DIAG", text = "%s(%x) Enabled" % (self.get_equipment_name(osw['id'] & 0xff), osw['id']))
			return

		if (osw['id'] & 0xf00) == 0xb00:
			self.log(command = "DIAG", text = "%s(%x) Disabled" % (self.get_equipment_name(osw['id'] & 0xff), osw['id']))
			return

		if (osw['id'] & 0xf00) == 0xc00:
			self.log(command = "DIAG", text = "%s(%x) Malfunction" % (self.get_equipment_name(osw['id'] & 0xff), osw['id']))
			return

		self.log(command = "DIAG", text = "code (%x) not known" % (osw['id'],))


	def call(self, oswl):
		if len(oswl) == 1:
			# single-osw case
			(osw,) = oswl
			if osw['id'] == 0x1ff2: # no idea what this is
				return
			if self.message_handler.start_call(osw['id'], osw['cmd']):
				self.log(command = "CALL", target = osw['id'], target_is_group = osw['g'], channel = osw['cmd'])
			return

		# dual-osw case
		(osw1, osw2) = oswl
		if self.message_handler.start_call(osw2['id'], osw2['cmd'], osw1['id']):
			self.log(command = "CALL", source = osw1['id'], source_display_count = True, target = osw2['id'], target_is_group = osw2['g'], channel = osw2['cmd'])


	def sys_id(self, osw1, osw2):
		if (self._sys_id != osw1['id']) or ((osw2['id'] & 0x3ff) != self._sys_channel):
			self._sys_id = osw1['id']
			self._sys_channel = osw2['id'] & 0x3ff
			self.message_handler.set_sysid(self._sys_id, self._sys_channel)
			self.log(command = "SYSID", channel = self._sys_channel, source = self._sys_id)


	def peer_id(self, osw1, osw2):
		self.unhandled([osw1, osw2], text = "peer id")


	def msc(self, osw1, osw2):
		self.unhandled([osw1, osw2], text = "msc")


	def unaffiliate(self, osw1, osw2):
		radio_id = osw1['id']
		if radio_id in self._affiliated_map:
			group_id = self._affiliated_map[radio_id]['group_id']
			# self.log(command = "UNAFF", source = radio_id, target = group_id, target_is_group = True);
			del self._affiliated_map[radio_id]

	
	def affiliate(self, osw1, osw2):
		radio_id = osw1['id']
		group_id = osw2['id'] & 0xfff0
		if radio_id not in self._affiliated_map:
			self._affiliated_map[radio_id] = dict()
			self._affiliated_map[radio_id]['group_id'] = -1
			self._affiliated_map[radio_id]['count'] = 1

		if self._affiliated_map[radio_id]['group_id'] != group_id:
			self._affiliated_map[radio_id]['group_id'] = group_id
			self._affiliated_map[radio_id]['count'] += 1
			# self.log(command = "AFF", source = osw1['id'], target = group_id, target_is_group = True, text = "aff num: %d; group flag: %x" % (self._affiliated_map[radio_id]['count'], osw2['id'] & 0xf))


	def call_alert(self, osw1, osw2):
		self.log(command = "ALERT", source = osw1['id'], source_display_count = True, target = osw2['id'], target_is_group = osw2['g'])


	def system_clock(self, osw1, osw2):
		tt1 = osw1['id']
		tt2 = osw2['id']
		self.log(command = "SYSCLK", text = "%2.2d/%2.2d/%2.2d %2.2d:%2.2d" % ((tt1 >> 5) & 0xf, tt1 & 0x1f, tt1 >> 9, (tt2 >> 8) & 0x1f, tt2 & 0xff))


	def emergency_announcement(self, osw1, osw2):
		self.log(command = "EANN", source = osw1['id'], target = osw2['id'])


	def neighbor(self, osw1, osw2, osw3):
		if (osw3['id'] & 0x3ff) in self._neighbors:
			# self.log(text = "NEIGH known: %3.4f" % (get_freq(osw3['id'] & 0x3ff),))
			return
		else:
			self._neighbors.append(osw3['id'] & 0x3ff)
		txt = "Band %d" % ((osw2['id'] >> 7) & 7,)
		if ((osw2['id'] >> 5) & 1):
			txt += "; VOC"
		if ((osw2['id'] >> 4) & 1) == 0:
			txt += "; Unknown"
		if ((osw2['id'] >> 3) & 1):
			txt += "; Astro"
		if ((osw2['id'] >> 2) & 1):
			txt += "; Analog"
		if ((osw2['id'] >> 1) & 1):
			txt += "; Encryption"
		if (osw2['id'] & 1) == 0:
			txt += "; Active"

		txt = ""
		for n in self._neighbors:
			txt += "%3.4f " % (get_freq(n),)
		self.log(command = "NEIGHBOR", source = osw1['id'], target = ((osw2['id'] >> 10) & 0x3f), channel = (osw3['id'] & 0x3ff), text = txt)


	def affil_fcn(self, osw1, osw2):
		self.unknown([osw1, osw2], text = "affil_fcn")


	def patch(self, osw1, osw2):
		# self.unknown([osw1, osw2], text = "patch")
		return


	def call_astro(self, osw1, osw2):
		self.unknown([osw1, osw2], text = "astro")


	def call_coded_pc(self, osw1, osw2):
		self.unknown([osw1, osw2], text = "coded pc")


#
#	Main processing function
#


	def process_osw(self, osw):

		# check for idle
		if osw['cmd'] == OSW_CMD.BACKGROUND_IDLE:
			self.site_idle(osw)
			return

		# check for site id
		if (OSW_CMD.AMSS_ID_MIN <= osw['cmd']) and (osw['cmd'] <= OSW_CMD.AMSS_ID_MAX):
			self.site_id(osw)
			return

		# add the new message to the list
		self.push(osw)

		# and then grab the first message
		osw1 = self.pop()

		# the commands and channels are theoretically non-intersecting.
		if is_valid_channel(osw1['cmd']):
			self.call([osw1,])
			return

		if osw1['cmd'] == OSW_CMD.SYS_NETSTAT:
			self.sys_netstat(osw1)
			return

		if osw1['cmd'] == OSW_CMD.SYS_STATUS:
			self.sys_status(osw1)
			return

		if osw1['cmd'] == OSW_CMD.SCAN_MARKER:
			self.scan_marker(osw1)
			return

		# dual sequences
		if osw1['cmd'] == OSW_CMD.FIRST_NORMAL:

			# this is a dual sequence, but we don't have the second packet yet
			if self.len() < 1:
				self.replace(osw1)
				return

			osw2 = self.pop()
			if is_valid_channel(osw2['cmd']):
				self.call([osw1, osw2])
				return

			if osw2['cmd'] == OSW_CMD.TY2_AFFILIATION:
				self.affiliate(osw1, osw2)
				return

			if osw2['cmd'] == OSW_CMD.TY2_MESSAGE:
				self.message(osw1, osw2)
				return

			if osw2['cmd'] == OSW_CMD.TY2_CALL_ALERT:
				self.call_alert(self, osw1, osw2)
				return

			if osw2['cmd'] == OSW_CMD.SYSTEM_CLOCK:
				self.system_clock(osw1, osw2)
				return

			if osw2['cmd'] == OSW_CMD.EMERG_ANNC:
				self.emergency_announcement(osw1, osw2)
				return

			if osw2['cmd'] == OSW_CMD.AFFIL_FCN:
				self.affil_fcn(osw1, osw2)
				return

			if (0x340 <= osw2['cmd']) and (osw2['cmd'] <= 0x350) and (osw2['cmd'] not in [0x34b, 0x34d, 0x34f]):
				self.patch(osw1, osw2)
				return

			if osw2['cmd'] == OSW_CMD.EXTENDED_FCN:

				if (osw2['id'] & 0xfff0) == 0x2610:
					self.unaffiliate(osw1, osw2)
					return

				if (osw2['id'] & 0xfff0) == 0x26e0:
					self.ack_status(osw1, osw2)
					return

				if (osw2['id'] & 0xfff0) == 0x26f0:
					self.ack_msg(osw1, osw2)
					return

				if (osw2['id'] & 0xff00) == 0x2c00:
					self.unknown_ack(osw1, osw2)
					return

				if (osw2['id'] & 0xfc00) == 0x2800:
					self.sys_id(osw1, osw2)
					return

				if (osw2['id'] & 0xfc00) == 0x6000:
					self.peer_id(osw1, osw2)
					return

				if osw2['id'] == 0x2021:
					self.msc(osw1, osw2)
					return

				self.unhandled([osw1, osw2], text = "ext fcn")
				return

			if osw2['cmd'] == 0x320:
				if self.len() < 1:
					self.replace(osw2)
					self.replace(osw1)
					return

				osw3 = self.pop()
				if osw3['cmd'] == OSW_CMD.EXTENDED_FCN:
					self.neighbor(osw1, osw2, osw3)
					return

				self.unhandled([osw1, osw2, osw3], text = "3-seq")

			self.unhandled([osw1, osw2], "2-seq")


		if osw1['cmd'] == OSW_CMD.FIRST_ASTRO:
			if self.len() < 1:
				self.replace(osw1)
				return

			osw2 = self.pop()
			self.call_astro(osw1, osw2)
			return

		if osw1['cmd'] == OSW_CMD.FIRST_CODED_PC:
			if self.len() < 1:
				self.replace(osw1)
				return

			osw2 = self.pop()
			self.call_coded_pc(osw1, osw2)
			return

		self.unhandled([osw1,])

# vim:ts=8:nowrap
