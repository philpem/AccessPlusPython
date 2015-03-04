#!/usr/bin/python

import os
import sys
import glob
import hashlib

success=0
files=0

sums = open("sums.txt", "r")
for line in sums.readlines():
	md5 = line[:32]
	name = line[33:].strip().replace(" ", "\xa0")

	if name.find("/.") != -1:
		# Dot files are hidden by access.py
		continue

	if name == "./md5sums.txt":
		continue

	files = files + 1

	try:
		f = open(name, "rb")
	except:
		names = glob.glob(name + ",*")
		if len(names) > 0:
			try:
				f = open(names[0], "rb")
			except:
				f = None
				print "Failed to open", name
		else:
			f = None
			print "Can not find", name + ",*"

	if f:
		m = hashlib.md5()
		m.update(f.read())
		if m.hexdigest() != md5:
			print "Invalid MD5 for", name
		else:
			success = success + 1

		f.close()

print "%d/%d successful copies" % (success, files)
